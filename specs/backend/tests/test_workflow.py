import os
from pathlib import Path

os.environ.setdefault("SPECS_DEMO_MODE", "true")
os.environ.setdefault("SPECS_SESSION_SECRET", "test-session-secret-12345678901234567890")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import ParameterDefinition, PdfTemplate, User
from app.security import hash_password


def test_end_to_end_revision_workflow(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECS_PDF_STORAGE", str(tmp_path / "pdf"))
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        db.add_all([
            User(username="inzenyr", first_name="Eva", last_name="Inženýrka",
                 email="e@example.invalid", password_hash=hash_password("test-password-123"), role="ENGINEER"),
            User(username="schvalovatel", first_name="Pavel", last_name="Schvalovatel",
                 email="p@example.invalid", password_hash=hash_password("test-password-123"), role="APPROVER"),
            User(username="admin", first_name="Anna", last_name="Administrátorka",
                 email="a@example.invalid", password_hash=hash_password("test-password-123"), role="ADMIN"),
        ])
        db.flush()
        definition = ParameterDefinition(code="CYCLE_TIME", name="Doba cyklu",
                                         category="Specifický časový limit", value_type="NUMERIC",
                                         unit="s", position_kind="NONE", sort_order=1)
        db.add(definition)
        db.add(PdfTemplate(version="v1", title="OPERAČNÍ NÁVODKA",
                           settings={"accent_color": "#153AA8", "section_color": "#E2E4E7",
                                     "show_english_subtitle": True},
                           is_active=True, created_by=3))

    def test_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as engineer:
            login = engineer.post("/api/v1/auth/login", json={"username": "inzenyr", "password": "test-password-123"})
            assert login.status_code == 200
            csrf = {"X-CSRF-Token": login.json()["csrf"]}
            no_csrf = engineer.post("/api/v1/specs", json={"machine_ref": "P-DEMO-01", "tool_ref": "MO-DEMO-01"})
            assert no_csrf.status_code == 403
            created = engineer.post("/api/v1/specs", json={"machine_ref": "P-DEMO-01", "tool_ref": "MO-DEMO-01"}, headers=csrf)
            assert created.status_code == 201
            spec_id = created.json()["id"]
            revision_id = created.json()["revisions"][0]["id"]
            saved = engineer.put(f"/api/v1/revisions/{revision_id}/draft", headers=csrf,
                                 json={"row_version": 1, "product_name": "Testovací výrobek",
                                       "change_reason": "První nastavení", "parameters": [
                                           {"definition_id": 1, "numeric_target": "41", "numeric_min": "38", "numeric_max": "44"}]})
            assert saved.status_code == 200
            assert saved.json()["parameters"][0]["numeric_target"] == "41"
            submitted = engineer.post(f"/api/v1/revisions/{revision_id}/submit", headers=csrf,
                                      json={"row_version": saved.json()["row_version"]})
            assert submitted.status_code == 200
            assert engineer.post(f"/api/v1/revisions/{revision_id}/approve", headers=csrf,
                                 json={"row_version": submitted.json()["row_version"]}).status_code == 403

        with TestClient(app) as reviewer:
            login = reviewer.post("/api/v1/auth/login", json={"username": "schvalovatel", "password": "test-password-123"})
            csrf = {"X-CSRF-Token": login.json()["csrf"]}
            approved = reviewer.post(f"/api/v1/revisions/{revision_id}/approve", headers=csrf,
                                     json={"row_version": submitted.json()["row_version"]})
            assert approved.status_code == 200
            assert approved.json()["status"] == "APPROVED"
            assert reviewer.put(f"/api/v1/revisions/{revision_id}/draft", headers=csrf,
                                json={"row_version": approved.json()["row_version"]}).status_code == 403
            assert reviewer.get(f"/api/v1/revisions/{revision_id}/pdf").status_code == 404
            pdf = reviewer.post(f"/api/v1/revisions/{revision_id}/pdf/issue", headers=csrf)
            assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
            assert reviewer.get(f"/api/v1/specs/{spec_id}/current/pdf").content == pdf.content
            assert reviewer.get(f"/api/v1/specs/{spec_id}/current").json()["id"] == revision_id
            assert reviewer.get(f"/api/v1/revisions/{revision_id}/audit").json()[0]["action"] == "pdf_issued"
            assert list((tmp_path / "pdf").rglob("*.pdf"))
            assert reviewer.post(f"/api/v1/specs/{spec_id}/revisions", headers=csrf).status_code == 403
        with TestClient(app) as engineer:
            login = engineer.post("/api/v1/auth/login", json={"username": "inzenyr", "password": "test-password-123"})
            csrf = {"X-CSRF-Token": login.json()["csrf"]}
            template = engineer.post("/api/v1/process-templates", headers=csrf,
                                     json={"revision_id": revision_id, "name": "Ověřený cyklus 41 s",
                                           "description": "Výchozí ověřený proces"})
            assert template.status_code == 201
            assert template.json()["parameter_count"] == 1
            templates = engineer.get("/api/v1/process-templates").json()
            assert templates[0]["name"] == "Ověřený cyklus 41 s"
            from_template = engineer.post("/api/v1/specs", headers=csrf,
                                          json={"machine_ref": "P-DEMO-02", "tool_ref": "MO-DEMO-02",
                                                "template_id": template.json()["id"]})
            assert from_template.status_code == 201
            template_revision = from_template.json()["revisions"][0]
            assert template_revision["product_name"] == "Testovací výrobek"
            assert template_revision["parameters"][0]["numeric_target"] == "41.0000"
            assert engineer.put(f"/api/v1/revisions/{revision_id}/draft", headers=csrf,
                                json={"row_version": approved.json()["row_version"]}).status_code == 409
            copied = engineer.post(f"/api/v1/specs/{spec_id}/revisions", headers=csrf)
            assert copied.status_code == 201
            assert copied.json()["parameters"][0]["numeric_target"] == "41.0000"
            assert engineer.get(f"/api/v1/specs/{spec_id}/current").json()["id"] == revision_id
        with TestClient(app) as administrator:
            login = administrator.post("/api/v1/auth/login", json={"username": "admin", "password": "test-password-123"})
            csrf = {"X-CSRF-Token": login.json()["csrf"]}
            new_template = administrator.post("/api/v1/pdf-templates", headers=csrf,
                                              json={"title": "PŘEDPIS A NÁVODKA", "accent_color": "#123456",
                                                    "section_color": "#EEEEEE", "show_english_subtitle": False})
            assert new_template.status_code == 201
            assert new_template.json()["version"] == "v2"
            assert administrator.get("/api/v1/pdf-templates/current").json()["version"] == "v2"
            assert administrator.get(f"/api/v1/revisions/{revision_id}/pdf").content == pdf.content
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_engineer_issues_directly_without_approver(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECS_PDF_STORAGE", str(tmp_path / "pdf"))
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        db.add(User(username="inzenyr", first_name="Eva", last_name="Inženýrka",
                    email="e2@example.invalid", password_hash=hash_password("test-password-123"), role="ENGINEER"))
        db.add(ParameterDefinition(code="CYCLE_TIME", name="Doba cyklu", category="Specifický časový limit",
                                   value_type="NUMERIC", unit="s", position_kind="NONE", sort_order=1))
        db.add(PdfTemplate(version="v1", title="OPERAČNÍ NÁVODKA",
                           settings={"accent_color": "#153AA8", "section_color": "#E2E4E7",
                                     "show_english_subtitle": True}, is_active=True, created_by=1))

    def test_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as engineer:
            login = engineer.post("/api/v1/auth/login", json={"username": "inzenyr", "password": "test-password-123"})
            csrf = {"X-CSRF-Token": login.json()["csrf"]}
            created = engineer.post("/api/v1/specs", json={"machine_ref": "P-DEMO-01", "tool_ref": "MO-DEMO-01"}, headers=csrf)
            revision_id = created.json()["revisions"][0]["id"]
            saved = engineer.put(f"/api/v1/revisions/{revision_id}/draft", headers=csrf,
                                 json={"row_version": 1, "product_name": "Testovací výrobek",
                                       "change_reason": "První nastavení", "parameters": [
                                           {"definition_id": 1, "numeric_target": "41", "unit": "min"}]})
            assert saved.json()["parameters"][0]["unit"] == "min"
            preview = engineer.get(f"/api/v1/revisions/{revision_id}/pdf/preview")
            assert preview.status_code == 200 and preview.content.startswith(b"%PDF")
            issued = engineer.post(f"/api/v1/revisions/{revision_id}/issue", headers=csrf,
                                   json={"row_version": saved.json()["row_version"]})
            assert issued.status_code == 200
            assert issued.json()["status"] == "APPROVED"
            assert issued.json()["approved_by"] == 1
            pdf = engineer.post(f"/api/v1/revisions/{revision_id}/pdf/issue", headers=csrf)
            assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_bug_report_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECS_PDF_STORAGE", str(tmp_path / "pdf"))
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        db.add_all([
            User(username="inzenyr", first_name="Eva", last_name="Inženýrka",
                 email="e3@example.invalid", password_hash=hash_password("test-password-123"), role="ENGINEER"),
            User(username="admin", first_name="Anna", last_name="Administrátorka",
                 email="a3@example.invalid", password_hash=hash_password("test-password-123"), role="ADMIN"),
        ])

    def test_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as engineer:
            login = engineer.post("/api/v1/auth/login", json={"username": "inzenyr", "password": "test-password-123"})
            csrf = {"X-CSRF-Token": login.json()["csrf"]}
            reported = engineer.post("/api/v1/bug-reports", headers=csrf,
                                     json={"message": "Tlačítko Vydat nic neudělá na Firefoxu.", "page": "Předpis #1"})
            assert reported.status_code == 201
            assert reported.json()["status"] == "OPEN"
            assert engineer.patch(f"/api/v1/bug-reports/{reported.json()['id']}", headers=csrf,
                                  json={"status": "DONE"}).status_code == 403
        with TestClient(app) as administrator:
            login = administrator.post("/api/v1/auth/login", json={"username": "admin", "password": "test-password-123"})
            csrf = {"X-CSRF-Token": login.json()["csrf"]}
            listed = administrator.get("/api/v1/bug-reports")
            assert listed.status_code == 200 and len(listed.json()) == 1
            resolved = administrator.patch(f"/api/v1/bug-reports/{listed.json()[0]['id']}", headers=csrf,
                                           json={"status": "DONE"})
            assert resolved.status_code == 200 and resolved.json()["status"] == "DONE"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
