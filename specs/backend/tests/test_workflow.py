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
        ])
        db.flush()
        definition = ParameterDefinition(code="CYCLE_TIME", name="Doba cyklu",
                                         category="Specifický časový limit", value_type="NUMERIC",
                                         unit="s", position_kind="NONE", sort_order=1)
        db.add(definition)
        db.add(PdfTemplate(version="v1", title="OPERAČNÍ NÁVODKA",
                           settings={"accent_color": "#153AA8", "section_color": "#E2E4E7",
                                     "show_english_subtitle": True},
                           is_active=True, created_by=1))

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
            assert engineer.put(f"/api/v1/revisions/{revision_id}/draft", headers=csrf,
                                json={"row_version": approved.json()["row_version"]}).status_code == 409
            copied = engineer.post(f"/api/v1/specs/{spec_id}/revisions", headers=csrf)
            assert copied.status_code == 201
            assert copied.json()["parameters"][0]["numeric_target"] == "41.0000"
            assert engineer.get(f"/api/v1/specs/{spec_id}/current").json()["id"] == revision_id
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
