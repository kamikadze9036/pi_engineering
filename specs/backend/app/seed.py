"""Idempotent bootstrap of the first administrator and MVP parameter catalogue."""
import os

from sqlalchemy import select

from .catalog import DEFINITIONS, REFERENCE_U10_3045
from .database import SessionLocal
from .models import ParameterDefinition, PdfTemplate, ProcessTemplate, User
from .security import hash_password, verify_password


def run() -> None:
    admin_password = os.getenv("SPECS_ADMIN_PASSWORD")
    if not admin_password or len(admin_password) < 12:
        raise RuntimeError("SPECS_ADMIN_PASSWORD musí mít alespoň 12 znaků.")
    demo = os.getenv("SPECS_DEMO_MODE", "false").lower() == "true"
    bootstrap_test_users = os.getenv("SPECS_BOOTSTRAP_TEST_USERS", "false").lower() == "true"
    with SessionLocal.begin() as db:
        admin = db.scalar(select(User).where(User.username == "admin"))
        if not admin:
            admin = User(username="admin", first_name="Administrátor", last_name="Předpisů",
                         email="admin@example.invalid", password_hash=hash_password(admin_password), role="ADMIN")
            db.add(admin)
            db.flush()
        elif not verify_password(admin_password, admin.password_hash):
            admin.password_hash = hash_password(admin_password)
        if demo or bootstrap_test_users:
            demo_password = os.getenv("SPECS_DEMO_PASSWORD", "demo123456789")
            for username, first, role in (("inzenyr", "Inženýr", "ENGINEER"), ("schvalovatel", "Schvalovatel", "APPROVER")):
                account = db.scalar(select(User).where(User.username == username))
                if not account:
                    db.add(User(username=username, first_name=first, last_name="Demo",
                                email=f"{username}@example.invalid", password_hash=hash_password(demo_password), role=role))
                else:
                    account.is_active = True
                    if not verify_password(demo_password, account.password_hash):
                        account.password_hash = hash_password(demo_password)
        else:
            for username in ("inzenyr", "schvalovatel"):
                account = db.scalar(select(User).where(User.username == username))
                if account and account.email.endswith("@example.invalid"):
                    account.is_active = False
        existing = {item.code: item for item in db.scalars(select(ParameterDefinition)).all()}
        catalogue_codes = {item.code for item in DEFINITIONS}
        for code, definition in existing.items():
            if code not in catalogue_codes:
                definition.is_active = False
        for order, spec in enumerate(DEFINITIONS, start=1):
            definition = existing.get(spec.code)
            if not definition:
                definition = ParameterDefinition(code=spec.code)
                db.add(definition)
            definition.name = spec.name
            definition.category = spec.category
            definition.value_type = spec.value_type
            definition.unit = spec.unit
            definition.position_kind = spec.position_kind
            definition.sort_order = order
            definition.is_active = True
        if not db.scalar(select(PdfTemplate).where(PdfTemplate.is_active.is_(True))):
            db.add(PdfTemplate(version="v1", title="OPERAČNÍ NÁVODKA",
                               settings={"accent_color": "#153AA8", "section_color": "#E2E4E7",
                                         "show_english_subtitle": True},
                               is_active=True, created_by=admin.id))
        system_templates = (
            ("ENGEL CC100/200/300 – prázdná návodka",
             "Kompletní sada polí podle firemní návodky bez předvyplněných procesních hodnot.",
             {"product_name": "", "material_name": "", "process_note": "", "parameters": []}),
            ("ENGEL U10 / 3045 – ověřený vzor",
             "Výchozí hodnoty přepsané z dodané schválené návodky U10 / 3045.",
             REFERENCE_U10_3045),
        )
        for name, description, payload in system_templates:
            if not db.scalar(select(ProcessTemplate).where(ProcessTemplate.name == name)):
                db.add(ProcessTemplate(name=name, description=description, payload=payload,
                                       is_system=True, is_active=True, created_by=admin.id))


if __name__ == "__main__":
    run()
