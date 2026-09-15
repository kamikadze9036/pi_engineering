"""Idempotent bootstrap of the first administrator and MVP parameter catalogue."""
import os

from sqlalchemy import select

from .database import SessionLocal
from .models import ParameterDefinition, PdfTemplate, User
from .security import hash_password


DEFINITIONS = [
    # code, name, category, unit, position_kind, value_type
    ("CUSTOMER", "Zákazník", "Základní údaje", "", "NONE", "TEXT"),
    ("SAP_REFERENCE", "Číslo výrobku (SAP)", "Základní údaje", "", "NONE", "TEXT"),
    ("CAVITIES", "Počet kavit", "Základní údaje", "", "NONE", "TEXT"),
    ("TECHNICIAN_NAME", "Jméno technika", "Základní údaje", "", "NONE", "TEXT"),
    ("SCREW_DIAMETER", "Průměr šroubu", "Základní údaje", "mm", "NONE", "NUMERIC"),
    ("RAW_MATERIAL", "Vstupní materiál", "Základní údaje", "", "NONE", "TEXT"),
    ("DRYING_TEMPERATURE", "Teplota sušení", "Základní údaje", "°C", "NONE", "NUMERIC"),
    ("DRYING_TIME", "Čas sušení", "Základní údaje", "h", "NONE", "NUMERIC"),
    ("MACHINE_PROGRAM", "Program vstřikolisu", "Základní údaje", "", "NONE", "TEXT"),
    ("ROBOT_PROGRAM", "Program robota", "Základní údaje", "", "NONE", "TEXT"),
    ("CLAMPING_FORCE", "Uzavírací síla", "Zavření, otevření, výstřik", "kN", "NONE", "NUMERIC"),
    ("CLOSING_POSITION", "Dráha zavírání formy", "Zavření, otevření, výstřik", "mm", "SEQUENCE", "NUMERIC"),
    ("CLOSING_SPEED", "Rychlost zavírání formy", "Zavření, otevření, výstřik", "%", "SEQUENCE", "NUMERIC"),
    ("OPENING_POSITION", "Dráha otevírání formy", "Zavření, otevření, výstřik", "mm", "SEQUENCE", "NUMERIC"),
    ("OPENING_SPEED", "Rychlost otevření", "Zavření, otevření, výstřik", "%", "SEQUENCE", "NUMERIC"),
    ("EJECTOR_STROKE", "Zdvih vyhazovačů", "Zavření, otevření, výstřik", "mm", "NONE", "NUMERIC"),
    ("CORE_NOTE", "Hydraulické jádro", "Hydraulické jádro", "", "NONE", "TEXT"),
    ("MOLD_TEMPERATURE", "Teplota formy", "Teplota formy", "°C", "LABEL", "NUMERIC"),
    ("HOT_RUNNER_TEMPERATURE", "Teplota horkého vtoku", "Teplota horkých vtoků", "°C", "SEQUENCE", "NUMERIC"),
    ("BARREL_TEMPERATURE", "Teplota válce", "Teplota válce", "°C", "LABEL", "NUMERIC"),
    ("NOZZLE_TEMPERATURE", "Teplota trysky", "Teplota válce", "°C", "NONE", "NUMERIC"),
    ("INJECTION_SPEED", "Rychlost vstřikování", "Vstřikování, dávka, jednotka", "mm/s", "SEQUENCE", "NUMERIC"),
    ("MAX_INJECTION_PRESSURE", "Limit tlaku", "Vstřikování, dávka, jednotka", "bar", "NONE", "NUMERIC"),
    ("TRANSFER_POSITION", "Poloha přepnutí", "Vstřikování, dávka, jednotka", "mm", "NONE", "NUMERIC"),
    ("TRANSFER_PRESSURE", "Tlak při přepnutí", "Vstřikování, dávka, jednotka", "bar", "NONE", "NUMERIC"),
    ("CUSHION", "Polštář", "Vstřikování, dávka, jednotka", "mm", "NONE", "NUMERIC"),
    ("HOLDING_PRESSURE", "Dotlak", "Vstřikování, dávka, jednotka", "bar", "SEQUENCE", "NUMERIC"),
    ("HOLDING_TIME", "Čas dotlaku", "Vstřikování, dávka, jednotka", "s", "SEQUENCE", "NUMERIC"),
    ("DOSING_STROKE", "Zdvih dávkování", "Vstřikování, dávka, jednotka", "mm", "NONE", "NUMERIC"),
    ("DECOMPRESSION", "Dekomprese", "Vstřikování, dávka, jednotka", "mm", "LABEL", "NUMERIC"),
    ("DOSING_SPEED", "Rychlost dávky", "Vstřikování, dávka, jednotka", "%", "SEQUENCE", "NUMERIC"),
    ("BACK_PRESSURE", "Protitlak", "Vstřikování, dávka, jednotka", "bar", "SEQUENCE", "NUMERIC"),
    ("INJECTION_TIME", "Doba vstřikování", "Specifický časový limit", "s", "NONE", "NUMERIC"),
    ("COOLING_TIME", "Doba chlazení", "Specifický časový limit", "s", "NONE", "NUMERIC"),
    ("CYCLE_TIME", "Doba cyklu", "Specifický časový limit", "s", "NONE", "NUMERIC"),
    ("SHOT_WEIGHT", "Váha vstřiku s vtokem", "Kontrola", "g", "NONE", "NUMERIC"),
    ("SPRUE_WEIGHT", "Hmotnost vtoku", "Kontrola", "g", "NONE", "NUMERIC"),
    ("STARTUP_PIECES", "Počet rozjezdových kusů", "Kontrola", "ks", "NONE", "NUMERIC"),
    ("SPECIAL_NOTE", "Specifická poznámka", "Poznámky", "", "NONE", "TEXT"),
]


def run() -> None:
    admin_password = os.getenv("SPECS_ADMIN_PASSWORD")
    if not admin_password or len(admin_password) < 12:
        raise RuntimeError("SPECS_ADMIN_PASSWORD musí mít alespoň 12 znaků.")
    demo = os.getenv("SPECS_DEMO_MODE", "false").lower() == "true"
    with SessionLocal.begin() as db:
        admin = db.scalar(select(User).where(User.username == "admin"))
        if not admin:
            admin = User(username="admin", first_name="Administrátor", last_name="Předpisů",
                         email="admin@example.invalid", password_hash=hash_password(admin_password), role="ADMIN")
            db.add(admin)
            db.flush()
        if demo:
            demo_password = os.getenv("SPECS_DEMO_PASSWORD", "demo123456789")
            for username, first, role in (("inzenyr", "Inženýr", "ENGINEER"), ("schvalovatel", "Schvalovatel", "APPROVER")):
                if not db.scalar(select(User).where(User.username == username)):
                    db.add(User(username=username, first_name=first, last_name="Demo",
                                email=f"{username}@example.invalid", password_hash=hash_password(demo_password), role=role))
        existing = set(db.scalars(select(ParameterDefinition.code)).all())
        for order, (code, name, category, unit, position_kind, value_type) in enumerate(DEFINITIONS, start=1):
            if code not in existing:
                db.add(ParameterDefinition(code=code, name=name, category=category,
                                           value_type=value_type, unit=unit,
                                           position_kind=position_kind, sort_order=order))
        if not db.scalar(select(PdfTemplate).where(PdfTemplate.is_active.is_(True))):
            db.add(PdfTemplate(version="v1", title="OPERAČNÍ NÁVODKA",
                               settings={"accent_color": "#153AA8", "section_color": "#E2E4E7",
                                         "show_english_subtitle": True},
                               is_active=True, created_by=admin.id))


if __name__ == "__main__":
    run()
