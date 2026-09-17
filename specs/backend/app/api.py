"""MVP API: immutable approved revisions, audit and read-only MES references."""
import hashlib
import json
import os
import secrets
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .catalog import BY_CODE
from .mes import MesCatalog, MesUnavailable
from .models import Assignment, AuditEntry, BugReport, Material, ParameterDefinition, ParameterValue, PdfDocument, PdfTemplate, ProcessTemplate, Revision, Spec, User, utc_now
from .pdf import generate_pdf
from .security import administrator, approver, current_user, verify_password, writer


router = APIRouter(prefix="/api/v1")
mes = MesCatalog()


class LoginInput(BaseModel):
    username: str
    password: str


class CreateSpecInput(BaseModel):
    machine_ref: str = Field(min_length=1)
    tool_ref: str = Field(min_length=1)
    template_id: int | None = None


class ParameterInput(BaseModel):
    definition_id: int
    position_key: str = ""
    position_label: str = ""
    numeric_target: Decimal | None = None
    numeric_min: Decimal | None = None
    numeric_max: Decimal | None = None
    text_value: str | None = None
    boolean_value: bool | None = None
    note: str = ""
    unit: str | None = None


class DraftInput(BaseModel):
    row_version: int
    product_name: str = ""
    material_name: str = ""
    process_note: str = ""
    change_reason: str = ""
    parameters: list[ParameterInput] = Field(default_factory=list)


class VersionInput(BaseModel):
    row_version: int


class BugReportInput(BaseModel):
    message: str = Field(min_length=3, max_length=4000)
    page: str = Field(default="", max_length=255)


class BugReportStatusInput(BaseModel):
    status: str = Field(pattern=r"^(OPEN|DONE)$")


class MaterialInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class MaterialSyncInput(BaseModel):
    names: list[str] = Field(default_factory=list)


class ReturnInput(VersionInput):
    reason: str = Field(min_length=3)


class TemplateInput(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    accent_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    section_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    show_english_subtitle: bool = True


class ProcessTemplateInput(BaseModel):
    revision_id: int
    name: str = Field(min_length=3, max_length=255)
    description: str = Field(default="", max_length=1000)


def fail(status: int, message: str) -> None:
    raise HTTPException(status_code=status, detail=message)


def as_json(value: dict) -> dict:
    return json.loads(json.dumps(value, default=str, ensure_ascii=False))


def audit(db: Session, user: User, entity_type: str, entity_id: int, action: str,
          before: dict | None = None, after: dict | None = None, reason: str = "") -> None:
    db.add(AuditEntry(actor_id=user.id, entity_type=entity_type, entity_id=entity_id,
                      action=action, before_data=as_json(before) if before else None,
                      after_data=as_json(after) if after else None, reason=reason))


def get_revision(db: Session, revision_id: int) -> Revision:
    revision = db.get(Revision, revision_id)
    if not revision:
        fail(404, "Revize neexistuje.")
    return revision


def get_revision_locked(db: Session, revision_id: int) -> Revision:
    revision = db.scalar(select(Revision).where(Revision.id == revision_id).with_for_update())
    if not revision:
        fail(404, "Revize neexistuje.")
    return revision


def check_author(revision: Revision, user: User) -> None:
    if revision.created_by != user.id and user.role != "ADMIN":
        fail(403, "Draft může upravit a odeslat jeho autor nebo administrátor.")


def check_version(revision: Revision, version: int) -> None:
    if revision.row_version != version:
        fail(409, "Revize se mezitím změnila. Načtěte ji znovu.")


def parameter_data(item: ParameterValue) -> dict:
    return {
        "definition_id": item.definition_id, "definition_code": item.definition_code,
        "definition_name": item.definition_name, "definition_category": item.definition_category,
        "definition_type": item.definition_type, "position_key": item.position_key,
        "position_label": item.position_label, "numeric_target": str(item.numeric_target) if item.numeric_target is not None else None,
        "numeric_min": str(item.numeric_min) if item.numeric_min is not None else None,
        "numeric_max": str(item.numeric_max) if item.numeric_max is not None else None,
        "text_value": item.text_value, "boolean_value": item.boolean_value,
        "unit": item.unit, "note": item.note,
    }


def revision_data(revision: Revision) -> dict:
    return {
        "id": revision.id, "process_spec_id": revision.process_spec_id,
        "revision_number": revision.revision_number, "status": revision.status,
        "row_version": revision.row_version, "product_name": revision.product_name,
        "material_name": revision.material_name, "process_note": revision.process_note,
        "change_reason": revision.change_reason, "created_by": revision.created_by,
        "created_at": revision.created_at.isoformat(),
        "approved_by": revision.approved_by,
        "approved_at": revision.approved_at.isoformat() if revision.approved_at else None,
        "mes_machine_code": revision.mes_machine_code, "mes_machine_name": revision.mes_machine_name,
        "mes_tool_code": revision.mes_tool_code, "mes_tool_name": revision.mes_tool_name,
        "parameters": [parameter_data(item) for item in revision.parameters],
    }


def process_template_data(template: ProcessTemplate) -> dict:
    return {
        "id": template.id, "name": template.name, "description": template.description,
        "source_revision_id": template.source_revision_id, "is_system": template.is_system,
        "parameter_count": len(template.payload.get("parameters", [])),
    }


def template_payload_from_revision(revision: Revision) -> dict:
    parameters = []
    for item in revision.parameters:
        parameters.append({
            "definition_code": item.definition_code, "position_key": item.position_key,
            "position_label": item.position_label,
            "numeric_target": str(item.numeric_target) if item.numeric_target is not None else None,
            "numeric_min": str(item.numeric_min) if item.numeric_min is not None else None,
            "numeric_max": str(item.numeric_max) if item.numeric_max is not None else None,
            "text_value": item.text_value, "boolean_value": item.boolean_value,
            "note": item.note,
        })
    return {"product_name": revision.product_name, "material_name": revision.material_name,
            "process_note": revision.process_note, "parameters": parameters}


def apply_process_template(db: Session, revision: Revision, template: ProcessTemplate) -> None:
    payload = template.payload or {}
    revision.product_name = str(payload.get("product_name") or "")
    revision.material_name = str(payload.get("material_name") or "")
    revision.process_note = str(payload.get("process_note") or "")
    revision.change_reason = f"Založeno ze vzoru: {template.name}"
    definitions = {item.code: item for item in db.scalars(
        select(ParameterDefinition).where(ParameterDefinition.is_active.is_(True))).all()}
    seen = set()
    for sort_order, item in enumerate(payload.get("parameters", []), start=1):
        definition = definitions.get(item.get("definition_code"))
        if not definition:
            continue
        position_key = str(item.get("position_key") or "")
        key = (definition.id, position_key)
        if key in seen:
            continue
        seen.add(key)
        db.add(ParameterValue(
            revision_id=revision.id, definition_id=definition.id,
            position_key=position_key, position_label=str(item.get("position_label") or ""),
            sort_order=sort_order, numeric_target=item.get("numeric_target"),
            numeric_min=item.get("numeric_min"), numeric_max=item.get("numeric_max"),
            text_value=item.get("text_value"), boolean_value=item.get("boolean_value"),
            note=str(item.get("note") or ""), unit=definition.unit,
            definition_code=definition.code, definition_name=definition.name,
            definition_category=definition.category, definition_type=definition.value_type))


def spec_data(db: Session, spec: Spec) -> dict:
    revisions = db.scalars(select(Revision).where(Revision.process_spec_id == spec.id).order_by(Revision.revision_number.desc())).all()
    assignment = spec.assignment
    return {
        "id": spec.id, "machine_ref": assignment.mes_machine_ref,
        "tool_ref": assignment.mes_tool_ref, "lifecycle": spec.lifecycle,
        "current_approved_revision_id": spec.current_approved_revision_id,
        "revisions": [revision_data(item) for item in revisions],
    }


def mes_item(kind: str, ref: str) -> dict:
    try:
        item = mes.get(kind, ref)
    except MesUnavailable as exc:
        fail(503, str(exc))
    if not item:
        fail(422, f"Reference {ref} v MES neexistuje.")
    return item


@router.post("/auth/login")
def login(data: LoginInput, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username.strip().lower()))
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        fail(401, "Nesprávné přihlášení.")
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["csrf"] = secrets.token_urlsafe(32)
    return {"id": user.id, "username": user.username, "role": user.role,
            "name": f"{user.first_name} {user.last_name}", "csrf": request.session["csrf"]}


@router.post("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/auth/me")
def me(request: Request, user: User = Depends(current_user)):
    return {"id": user.id, "username": user.username, "role": user.role,
            "name": f"{user.first_name} {user.last_name}", "csrf": request.session["csrf"]}


@router.get("/mes/{kind}")
def search_mes(kind: str, q: str = "", _: User = Depends(current_user)):
    if kind not in ("machines", "tools"):
        fail(404, "Neznámý číselník.")
    try:
        return {"mode": "DEMO" if mes.demo else "MES_EXPORT", "items": mes.search(kind, q)}
    except MesUnavailable as exc:
        fail(503, str(exc))


@router.get("/parameter-definitions")
def definitions(db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.scalars(select(ParameterDefinition).where(ParameterDefinition.is_active.is_(True)).order_by(ParameterDefinition.sort_order)).all()
    return [{"id": item.id, "code": item.code, "name": item.name,
             "category": item.category, "value_type": item.value_type, "unit": item.unit,
             "position_kind": item.position_kind,
             "positions": [{"key": key, "label": label} for key, label in BY_CODE.get(item.code, ()).positions]
             if item.code in BY_CODE else []} for item in rows]


@router.get("/process-templates")
def process_templates(db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.scalars(select(ProcessTemplate).where(ProcessTemplate.is_active.is_(True))
                      .order_by(ProcessTemplate.is_system.desc(), ProcessTemplate.name)).all()
    return [process_template_data(item) for item in rows]


@router.post("/process-templates", status_code=201)
def create_process_template(data: ProcessTemplateInput, db: Session = Depends(get_db),
                            user: User = Depends(writer)):
    revision = get_revision(db, data.revision_id)
    spec = db.get(Spec, revision.process_spec_id)
    if revision.status != "APPROVED" or spec.current_approved_revision_id != revision.id:
        fail(409, "Vzor lze vytvořit pouze z aktuální schválené revize.")
    name = data.name.strip()
    if db.scalar(select(ProcessTemplate).where(ProcessTemplate.name == name)):
        fail(409, "Vzor s tímto názvem už existuje.")
    template = ProcessTemplate(name=name, description=data.description.strip(),
                               source_revision_id=revision.id,
                               payload=template_payload_from_revision(revision),
                               is_system=False, is_active=True, created_by=user.id)
    db.add(template)
    try:
        db.flush()
        audit(db, user, "process_template", template.id, "created",
              after={"name": template.name, "source_revision_id": revision.id})
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, "Vzor s tímto názvem už existuje.")
    return process_template_data(template)


@router.get("/specs")
def list_specs(db: Session = Depends(get_db), _: User = Depends(current_user)):
    specs = db.scalars(select(Spec).order_by(Spec.id.desc()).limit(100)).all()
    return [spec_data(db, item) for item in specs]


@router.post("/specs", status_code=201)
def create_spec(data: CreateSpecInput, db: Session = Depends(get_db), user: User = Depends(writer)):
    mes_item("machines", data.machine_ref)
    mes_item("tools", data.tool_ref)
    assignment = db.scalar(select(Assignment).where(Assignment.mes_machine_ref == data.machine_ref,
                                                   Assignment.mes_tool_ref == data.tool_ref))
    if assignment:
        existing = db.scalar(select(Spec).where(Spec.assignment_id == assignment.id))
        if existing:
            fail(409, "Předpis pro tuto kombinaci už existuje.")
    else:
        assignment = Assignment(mes_machine_ref=data.machine_ref, mes_tool_ref=data.tool_ref, created_by=user.id)
        db.add(assignment)
        db.flush()
    spec = Spec(assignment_id=assignment.id, created_by=user.id)
    db.add(spec)
    db.flush()
    revision = Revision(process_spec_id=spec.id, revision_number=1, status="DRAFT", created_by=user.id)
    db.add(revision)
    db.flush()
    template = None
    if data.template_id is not None:
        template = db.scalar(select(ProcessTemplate).where(ProcessTemplate.id == data.template_id,
                                                           ProcessTemplate.is_active.is_(True)))
        if not template:
            fail(422, "Vybraný výchozí vzor neexistuje nebo není aktivní.")
        apply_process_template(db, revision, template)
        db.flush()
    audit(db, user, "process_spec", spec.id, "created",
          after={"machine_ref": data.machine_ref, "tool_ref": data.tool_ref,
                 "template_id": template.id if template else None,
                 "template_name": template.name if template else None})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, "Předpis pro tuto kombinaci už existuje.")
    return spec_data(db, spec)


@router.get("/specs/{spec_id}")
def get_spec(spec_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    spec = db.get(Spec, spec_id)
    if not spec:
        fail(404, "Předpis neexistuje.")
    return spec_data(db, spec)


@router.get("/revisions/{revision_id}")
def get_revision_endpoint(revision_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return revision_data(get_revision(db, revision_id))


@router.put("/revisions/{revision_id}/draft")
def save_draft(revision_id: int, data: DraftInput, db: Session = Depends(get_db), user: User = Depends(writer)):
    revision = get_revision_locked(db, revision_id)
    if revision.status != "DRAFT":
        fail(409, "Upravit lze pouze rozpracovanou revizi.")
    check_author(revision, user)
    check_version(revision, data.row_version)
    before = revision_data(revision)
    definitions_by_id = {item.id: item for item in db.scalars(select(ParameterDefinition).where(ParameterDefinition.is_active.is_(True))).all()}
    seen = set()
    new_values = []
    for sort_order, item in enumerate(data.parameters, 1):
        definition = definitions_by_id.get(item.definition_id)
        if not definition:
            fail(422, "Parametr není v aktivním katalogu.")
        position_key = item.position_key.strip()
        if definition.position_kind == "NONE" and position_key:
            fail(422, f"Parametr {definition.name} nemá pozice.")
        if definition.position_kind != "NONE" and not position_key:
            fail(422, f"Parametr {definition.name} vyžaduje pozici.")
        key = (definition.id, position_key)
        if key in seen:
            fail(422, "Stejný parametr a pozice se opakují.")
        seen.add(key)
        if definition.value_type == "NUMERIC":
            if item.numeric_target is None or item.text_value is not None or item.boolean_value is not None:
                fail(422, f"Parametr {definition.name} vyžaduje číselnou cílovou hodnotu.")
            if item.numeric_min is not None and item.numeric_min > item.numeric_target:
                fail(422, "Minimum je větší než cílová hodnota.")
            if item.numeric_max is not None and item.numeric_max < item.numeric_target:
                fail(422, "Maximum je menší než cílová hodnota.")
        new_values.append(ParameterValue(
            revision_id=revision.id, definition_id=definition.id,
            position_key=position_key, position_label=item.position_label.strip(), sort_order=sort_order,
            numeric_target=item.numeric_target, numeric_min=item.numeric_min, numeric_max=item.numeric_max,
            text_value=item.text_value, boolean_value=item.boolean_value, note=item.note.strip(),
            unit=(item.unit or "").strip() or definition.unit, definition_code=definition.code, definition_name=definition.name,
            definition_category=definition.category, definition_type=definition.value_type))
    for old in list(revision.parameters):
        db.delete(old)
    db.flush()
    revision.product_name = data.product_name.strip()
    revision.material_name = data.material_name.strip()
    revision.process_note = data.process_note.strip()
    revision.change_reason = data.change_reason.strip()
    revision.row_version += 1
    revision.updated_at = utc_now()
    db.add_all(new_values)
    db.flush()
    db.expire(revision, ["parameters"])
    after = revision_data(revision)
    audit(db, user, "process_spec_revision", revision.id, "draft_saved", before=before, after=after,
          reason=data.change_reason)
    db.commit()
    return revision_data(revision)


@router.post("/revisions/{revision_id}/submit")
def submit(revision_id: int, data: VersionInput, db: Session = Depends(get_db), user: User = Depends(writer)):
    revision = get_revision_locked(db, revision_id)
    if revision.status != "DRAFT":
        fail(409, "Ke schválení lze poslat jen draft.")
    check_author(revision, user)
    check_version(revision, data.row_version)
    if not revision.product_name or not revision.change_reason or not revision.parameters:
        fail(422, "Vyplňte výrobek, důvod revize a alespoň jeden parametr.")
    revision.status = "IN_REVIEW"
    revision.submitted_at = utc_now()
    revision.row_version += 1
    audit(db, user, "process_spec_revision", revision.id, "submitted", after={"status": revision.status})
    db.commit()
    return revision_data(revision)


@router.post("/revisions/{revision_id}/return")
def return_draft(revision_id: int, data: ReturnInput, db: Session = Depends(get_db), user: User = Depends(approver)):
    revision = get_revision_locked(db, revision_id)
    if revision.status != "IN_REVIEW":
        fail(409, "Vrátit lze jen revizi ve schvalování.")
    check_version(revision, data.row_version)
    revision.status = "DRAFT"
    revision.row_version += 1
    audit(db, user, "process_spec_revision", revision.id, "returned", reason=data.reason,
          after={"status": revision.status})
    db.commit()
    return revision_data(revision)


@router.post("/revisions/{revision_id}/approve")
def approve(revision_id: int, data: VersionInput, db: Session = Depends(get_db), user: User = Depends(approver)):
    revision = get_revision_locked(db, revision_id)
    if revision.status != "IN_REVIEW":
        fail(409, "Schválit lze jen revizi ve schvalování.")
    check_version(revision, data.row_version)
    spec = db.get(Spec, revision.process_spec_id)
    if spec.lifecycle != "ACTIVE":
        fail(409, "Zastaralý předpis nelze schválit.")
    # The MES read happens before the PostgreSQL transaction commits. A stale or
    # missing export therefore never publishes an unverified new revision.
    machine = mes_item("machines", spec.assignment.mes_machine_ref)
    tool = mes_item("tools", spec.assignment.mes_tool_ref)
    revision.mes_machine_code, revision.mes_machine_name = machine["code"], machine["name"]
    revision.mes_tool_code, revision.mes_tool_name = tool["code"], tool["name"]
    revision.status = "APPROVED"
    revision.approved_by = user.id
    revision.approved_at = utc_now()
    revision.row_version += 1
    spec.current_approved_revision_id = revision.id
    audit(db, user, "process_spec_revision", revision.id, "approved",
          after={"status": revision.status, "revision_number": revision.revision_number})
    db.commit()
    return revision_data(revision)


@router.post("/revisions/{revision_id}/issue")
def issue(revision_id: int, data: VersionInput, db: Session = Depends(get_db), user: User = Depends(writer)):
    """Engineer-direct path: submit (if needed) and approve in one step, no separate approver."""
    revision = get_revision_locked(db, revision_id)
    if revision.status not in ("DRAFT", "IN_REVIEW"):
        fail(409, "Vydat lze jen rozpracovanou nebo odeslanou revizi.")
    check_author(revision, user)
    check_version(revision, data.row_version)
    if not revision.product_name or not revision.change_reason or not revision.parameters:
        fail(422, "Vyplňte výrobek, důvod revize a alespoň jeden parametr.")
    spec = db.get(Spec, revision.process_spec_id)
    if spec.lifecycle != "ACTIVE":
        fail(409, "Zastaralý předpis nelze vydat.")
    if revision.status == "DRAFT":
        revision.status = "IN_REVIEW"
        revision.submitted_at = utc_now()
        revision.row_version += 1
        audit(db, user, "process_spec_revision", revision.id, "submitted", after={"status": "IN_REVIEW"})
    # The MES read happens before the PostgreSQL transaction commits. A stale or
    # missing export therefore never publishes an unverified new revision.
    machine = mes_item("machines", spec.assignment.mes_machine_ref)
    tool = mes_item("tools", spec.assignment.mes_tool_ref)
    revision.mes_machine_code, revision.mes_machine_name = machine["code"], machine["name"]
    revision.mes_tool_code, revision.mes_tool_name = tool["code"], tool["name"]
    revision.status = "APPROVED"
    revision.approved_by = user.id
    revision.approved_at = utc_now()
    revision.row_version += 1
    spec.current_approved_revision_id = revision.id
    audit(db, user, "process_spec_revision", revision.id, "approved",
          after={"status": revision.status, "revision_number": revision.revision_number, "issued_by": "ENGINEER"})
    db.commit()
    return revision_data(revision)


@router.post("/specs/{spec_id}/revisions", status_code=201)
def create_revision(spec_id: int, db: Session = Depends(get_db), user: User = Depends(writer)):
    spec = db.get(Spec, spec_id)
    if not spec:
        fail(404, "Předpis neexistuje.")
    if spec.lifecycle != "ACTIVE" or not spec.current_approved_revision_id:
        fail(409, "Novou revizi lze založit pouze z platného předpisu.")
    open_revision = db.scalar(select(Revision).where(Revision.process_spec_id == spec.id,
                                                    Revision.status.in_(["DRAFT", "IN_REVIEW"])))
    if open_revision:
        fail(409, "Otevřená revize už existuje.")
    old = get_revision(db, spec.current_approved_revision_id)
    revision = Revision(process_spec_id=spec.id, revision_number=old.revision_number + 1,
                        status="DRAFT", product_name=old.product_name,
                        material_name=old.material_name, process_note=old.process_note,
                        created_by=user.id)
    db.add(revision)
    db.flush()
    for item in old.parameters:
        db.add(ParameterValue(revision_id=revision.id, definition_id=item.definition_id,
                              position_key=item.position_key, position_label=item.position_label,
                              sort_order=item.sort_order, numeric_target=item.numeric_target,
                              numeric_min=item.numeric_min, numeric_max=item.numeric_max,
                              text_value=item.text_value, boolean_value=item.boolean_value,
                              unit=item.unit, note=item.note, definition_code=item.definition_code,
                              definition_name=item.definition_name, definition_category=item.definition_category,
                              definition_type=item.definition_type))
    audit(db, user, "process_spec_revision", revision.id, "created_from_approved",
          after={"from_revision_id": old.id, "revision_number": revision.revision_number})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, "Souběžně vznikla jiná revize. Načtěte předpis znovu.")
    return revision_data(revision)


@router.get("/specs/{spec_id}/current")
def current(spec_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    spec = db.get(Spec, spec_id)
    if not spec:
        fail(404, "Předpis neexistuje.")
    if spec.lifecycle != "ACTIVE" or not spec.current_approved_revision_id:
        fail(404, "Předpis nemá platnou schválenou revizi.")
    return revision_data(get_revision(db, spec.current_approved_revision_id))


@router.get("/revisions/{revision_id}/audit")
def revision_audit(revision_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    get_revision(db, revision_id)
    entries = db.scalars(select(AuditEntry).where(AuditEntry.entity_type == "process_spec_revision",
                                                  AuditEntry.entity_id == revision_id).order_by(AuditEntry.id.desc())).all()
    return [{"id": item.id, "actor_id": item.actor_id, "action": item.action,
             "before": item.before_data, "after": item.after_data,
             "reason": item.reason, "created_at": item.created_at.isoformat()} for item in entries]


@router.get("/pdf-templates/current")
def current_template(db: Session = Depends(get_db), _: User = Depends(current_user)):
    template = db.scalar(select(PdfTemplate).where(PdfTemplate.is_active.is_(True)))
    if not template:
        fail(503, "PDF šablona není dostupná.")
    return {"version": template.version, "title": template.title, "settings": template.settings}


@router.post("/pdf-templates", status_code=201)
def publish_template(data: TemplateInput, db: Session = Depends(get_db), user: User = Depends(administrator)):
    active = db.scalar(select(PdfTemplate).where(PdfTemplate.is_active.is_(True)))
    if active:
        active.is_active = False
    last_id = db.scalar(select(PdfTemplate.id).order_by(PdfTemplate.id.desc()).limit(1)) or 0
    template = PdfTemplate(version=f"v{last_id + 1}", title=data.title.strip(),
                           settings={"accent_color": data.accent_color,
                                     "section_color": data.section_color,
                                     "show_english_subtitle": data.show_english_subtitle},
                           is_active=True, created_by=user.id)
    db.add(template)
    db.flush()
    audit(db, user, "pdf_template", template.id, "published", after={"version": template.version,
          "title": template.title, "settings": template.settings})
    db.commit()
    return {"version": template.version, "title": template.title, "settings": template.settings}


def pdf_for_revision(revision_id: int, db: Session, user: User, issue: bool = False) -> Response:
    revision = get_revision(db, revision_id)
    if revision.status != "APPROVED":
        fail(409, "PDF lze vydat pouze ze schválené revize.")
    root = Path(os.getenv("SPECS_PDF_STORAGE", "./pdf-output"))
    existing = db.scalar(select(PdfDocument).where(PdfDocument.revision_id == revision.id)
                         .order_by(PdfDocument.generated_at.asc()))
    if existing:
        path = root / existing.storage_key
        try:
            content = path.read_bytes()
        except OSError:
            fail(503, "Archivované PDF chybí. Obnovte PDF úložiště ze zálohy.")
        if hashlib.sha256(content).hexdigest() != existing.sha256:
            fail(503, "Archivované PDF neodpovídá uloženému otisku.")
    else:
        if not issue:
            fail(404, "PDF zatím nebylo vydáno. Nejprve použijte vydání PDF.")
        template = db.scalar(select(PdfTemplate).where(PdfTemplate.is_active.is_(True)))
        if not template:
            fail(503, "PDF šablona není dostupná.")
        author = db.get(User, revision.created_by)
        approver_user = db.get(User, revision.approved_by)
        content = generate_pdf(revision, template,
                               f"{author.first_name} {author.last_name}",
                               f"{approver_user.first_name} {approver_user.last_name}")
        key = f"spec-{revision.process_spec_id}/rev-{revision.revision_number}-{template.version}.pdf"
        path = root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(content)
        os.replace(temporary, path)
        db.add(PdfDocument(revision_id=revision.id, template_version=template.version,
                           storage_key=key, sha256=hashlib.sha256(content).hexdigest(),
                           generated_by=user.id))
        audit(db, user, "process_spec_revision", revision.id, "pdf_issued",
              after={"template_version": template.version, "sha256": hashlib.sha256(content).hexdigest()})
        db.commit()
    filename = f"operacni-navodka-spec-{revision.process_spec_id}-rev-{revision.revision_number}.pdf"
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


@router.get("/revisions/{revision_id}/pdf")
def revision_pdf(revision_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return pdf_for_revision(revision_id, db, user)


@router.get("/revisions/{revision_id}/pdf/preview")
def revision_pdf_preview(revision_id: int, db: Session = Depends(get_db), user: User = Depends(writer)):
    """On-the-fly PDF for a DRAFT/IN_REVIEW revision. Never archived, never counted as issued."""
    revision = get_revision(db, revision_id)
    if revision.status == "APPROVED":
        return pdf_for_revision(revision_id, db, user)
    template = db.scalar(select(PdfTemplate).where(PdfTemplate.is_active.is_(True)))
    if not template:
        fail(503, "PDF šablona není dostupná.")
    author = db.get(User, revision.created_by)
    content = generate_pdf(revision, template, f"{author.first_name} {author.last_name}", "NÁHLED – zatím nevydáno")
    filename = f"nahled-spec-{revision.process_spec_id}-rev-{revision.revision_number}.pdf"
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


@router.post("/revisions/{revision_id}/pdf/issue")
def issue_revision_pdf(revision_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return pdf_for_revision(revision_id, db, user, issue=True)


@router.get("/specs/{spec_id}/current/pdf")
def current_pdf(spec_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    spec = db.get(Spec, spec_id)
    if not spec or spec.lifecycle != "ACTIVE" or not spec.current_approved_revision_id:
        fail(404, "Předpis nemá platnou schválenou revizi.")
    return pdf_for_revision(spec.current_approved_revision_id, db, user)


def bug_report_data(item: BugReport) -> dict:
    return {"id": item.id, "reporter_id": item.reporter_id, "message": item.message,
            "page": item.page, "status": item.status, "created_at": item.created_at.isoformat(),
            "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None}


@router.get("/bug-reports")
def list_bug_reports(db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.scalars(select(BugReport).order_by(BugReport.status.asc(), BugReport.created_at.desc())).all()
    return [bug_report_data(item) for item in rows]


@router.post("/bug-reports", status_code=201)
def create_bug_report(data: BugReportInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    report = BugReport(reporter_id=user.id, message=data.message.strip(), page=data.page.strip())
    db.add(report)
    db.flush()
    audit(db, user, "bug_report", report.id, "reported")
    db.commit()
    return bug_report_data(report)


@router.patch("/bug-reports/{report_id}")
def update_bug_report(report_id: int, data: BugReportStatusInput, db: Session = Depends(get_db),
                      user: User = Depends(administrator)):
    report = db.get(BugReport, report_id)
    if not report:
        fail(404, "Hlášení neexistuje.")
    report.status = data.status
    report.resolved_at = utc_now() if data.status == "DONE" else None
    audit(db, user, "bug_report", report.id, "status_changed", after={"status": data.status})
    db.commit()
    return bug_report_data(report)


@router.get("/materials")
def list_materials(db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.scalars(select(Material).where(Material.is_active.is_(True)).order_by(Material.name)).all()
    return [{"id": item.id, "name": item.name} for item in rows]


@router.post("/materials", status_code=201)
def create_material(data: MaterialInput, db: Session = Depends(get_db), user: User = Depends(administrator)):
    name = data.name.strip()
    existing = db.scalar(select(Material).where(Material.name == name))
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.commit()
        else:
            fail(409, "Materiál s tímto názvem už existuje.")
        return {"id": existing.id, "name": existing.name}
    material = Material(name=name, is_active=True, created_by=user.id)
    db.add(material)
    db.flush()
    audit(db, user, "material", material.id, "created", after={"name": name})
    db.commit()
    return {"id": material.id, "name": material.name}


@router.delete("/materials/{material_id}", status_code=204)
def delete_material(material_id: int, db: Session = Depends(get_db), user: User = Depends(administrator)):
    material = db.get(Material, material_id)
    if not material:
        fail(404, "Materiál neexistuje.")
    material.is_active = False
    audit(db, user, "material", material.id, "deactivated")
    db.commit()
    return Response(status_code=204)


@router.post("/materials/sync")
def sync_materials(data: MaterialSyncInput, db: Session = Depends(get_db), user: User = Depends(administrator)):
    """Additive sync from Cyklades GP_CONSOF (scripts/sync_materials.py). Never removes
    materials the admin added by hand or that Cyklades no longer lists."""
    existing = {item.name: item for item in db.scalars(select(Material)).all()}
    added, reactivated = 0, 0
    for raw_name in data.names:
        name = raw_name.strip()
        if not name:
            continue
        current = existing.get(name)
        if not current:
            db.add(Material(name=name, is_active=True, created_by=user.id))
            existing[name] = None
            added += 1
        elif not current.is_active:
            current.is_active = True
            reactivated += 1
    audit(db, user, "material", 0, "synced", after={"added": added, "reactivated": reactivated, "source_count": len(data.names)})
    db.commit()
    return {"added": added, "reactivated": reactivated}
