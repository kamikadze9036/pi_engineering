"""Canonical fields and positions of the supplied ENGEL operation sheet.

The database keeps definitions separately so approved revisions can snapshot
their labels.  This module is the editable blueprint for new revisions and for
the data-entry form; blank positions are deliberately allowed in the sheet.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DefinitionSpec:
    code: str
    name: str
    category: str
    unit: str = ""
    value_type: str = "NUMERIC"
    positions: tuple[tuple[str, str], ...] = ()

    @property
    def position_kind(self) -> str:
        return "SEQUENCE" if self.positions else "NONE"


def numbered(count: int) -> tuple[tuple[str, str], ...]:
    return tuple((str(value), str(value)) for value in range(1, count + 1))


PROFILE_6 = numbered(6)
PROFILE_5 = numbered(5)
PROFILE_8 = numbered(8)
PROFILE_9 = numbered(9)
CORES_4 = tuple((str(value), f"Jádro {value}") for value in range(1, 5))


DEFINITIONS: tuple[DefinitionSpec, ...] = (
    DefinitionSpec("CUSTOMER", "Zákazník", "Základní údaje", value_type="TEXT"),
    DefinitionSpec("SAP_REFERENCE", "Číslo výrobku (SAP)", "Základní údaje", value_type="TEXT"),
    DefinitionSpec("PART_VARIANT", "Varianta výrobku (LH/RH)", "Základní údaje", value_type="TEXT"),
    DefinitionSpec("CAVITIES", "Počet kavit", "Základní údaje", value_type="TEXT"),
    DefinitionSpec("TECHNICIAN_NAME", "Jméno technika", "Základní údaje", value_type="TEXT"),
    DefinitionSpec("SCREW_DIAMETER", "Průměr šroubu", "Základní údaje", "mm"),
    DefinitionSpec("NOZZLE_DIAMETER", "Průměr trysky", "Základní údaje", "mm"),
    DefinitionSpec("RAW_MATERIAL", "Vstupní materiál", "Základní údaje", value_type="TEXT"),
    DefinitionSpec("COLORANT", "Barvivo", "Základní údaje", value_type="TEXT"),
    DefinitionSpec("REGRIND_PERCENT", "Recyklovaný materiál", "Základní údaje", "%"),
    DefinitionSpec("DRYING_TEMPERATURE", "Teplota sušení", "Základní údaje", "°C"),
    DefinitionSpec("DRYING_TIME", "Čas sušení", "Základní údaje", "h"),
    DefinitionSpec("MACHINE_PROGRAM", "Program vstřikolisu", "Základní údaje", value_type="TEXT"),
    DefinitionSpec("ROBOT", "Robot", "Základní údaje", value_type="BOOLEAN"),
    DefinitionSpec("ROBOT_PROGRAM", "Program robota", "Základní údaje", value_type="TEXT"),

    DefinitionSpec("CLAMPING_FORCE", "Uzavírací síla", "Zavření, otevření, výstřik", "kN"),
    DefinitionSpec("CLOSING_POSITION", "Dráha zavírání formy", "Zavření, otevření, výstřik", "mm", positions=PROFILE_6),
    DefinitionSpec("CLOSING_SPEED", "Rychlost zavření", "Zavření, otevření, výstřik", "%", positions=PROFILE_6),
    DefinitionSpec("MOLD_PROTECTION_POSITION", "Dráha zavírání formy", "Zavření, otevření, výstřik", "mm", positions=PROFILE_6),
    DefinitionSpec("MOLD_PROTECTION_FORCE", "Síla zavírání formy", "Zavření, otevření, výstřik", "%", positions=PROFILE_6),
    DefinitionSpec("MOLD_PROTECTION_STROKE", "Dráha ochrany formy", "Zavření, otevření, výstřik", "mm"),
    DefinitionSpec("MOLD_PROTECTION_TIME", "Doba kontroly ochrany formy", "Zavření, otevření, výstřik", "s"),
    DefinitionSpec("HIGH_SPEED_LOCKING", "Rychloposuv uzavřen", "Zavření, otevření, výstřik", "mm"),
    DefinitionSpec("OPENING_POSITION", "Dráha otevírání formy", "Zavření, otevření, výstřik", "mm", positions=PROFILE_6),
    DefinitionSpec("OPENING_SPEED", "Rychlost otevření", "Zavření, otevření, výstřik", "%", positions=PROFILE_6),
    DefinitionSpec("OPENING_STROKE", "Dráha otevření", "Zavření, otevření, výstřik", "mm"),
    DefinitionSpec("EJECTOR_START_POSITION", "Pozice vyhazovačů", "Vyhazovače", "mm"),
    DefinitionSpec("EJECTOR_CONTROLLED_POSITION", "Kontrolovaná pozice", "Vyhazovače", "mm"),
    DefinitionSpec("EJECTOR_REAL_STROKE", "Reálná délka vyhazovačů", "Vyhazovače", "mm"),
    DefinitionSpec("EJECTOR_TIME", "Čas vyhazovačů", "Vyhazovače", "s"),
    DefinitionSpec("EJECTOR_PRIORITY_OUT", "Priorita ven", "Vyhazovače", ""),
    DefinitionSpec("EJECTOR_PRIORITY_IN", "Priorita dovnitř", "Vyhazovače", ""),
    DefinitionSpec("EJECTOR_SPEED_OUT", "Rychlost vyhazovače ven", "Vyhazovače", "%", positions=(('1', '1'), ('2', '2'))),
    DefinitionSpec("EJECTOR_SPEED_IN", "Rychlost vyhazovače dovnitř", "Vyhazovače", "%", positions=(('1', '1'), ('2', '2'))),
    DefinitionSpec("EJECTOR_PRESSURE_OUT", "Tlak vyhazovače ven", "Vyhazovače", "%", positions=(('1', '1'), ('2', '2'))),
    DefinitionSpec("EJECTOR_PRESSURE_IN", "Tlak vyhazovače dovnitř", "Vyhazovače", "%", positions=(('1', '1'), ('2', '2'))),

    DefinitionSpec("CORE_NUMBER", "Číslo jádra", "Hydraulické jádro", value_type="TEXT", positions=CORES_4),
    DefinitionSpec("CORE_TITLE", "Název jádra", "Hydraulické jádro", value_type="TEXT", positions=CORES_4),
    DefinitionSpec("CORE_PRIORITY_OUT", "Priorita vyjeto", "Hydraulické jádro", positions=CORES_4),
    DefinitionSpec("CORE_PRIORITY_IN", "Priorita najeto", "Hydraulické jádro", positions=CORES_4),
    DefinitionSpec("CORE_POSITION_OUT", "Pozice vyjeto", "Hydraulické jádro", "mm", positions=CORES_4),
    DefinitionSpec("CORE_POSITION_IN", "Pozice najeto", "Hydraulické jádro", "mm", positions=CORES_4),
    DefinitionSpec("CORE_SPEED_OUT", "Rychlost vyjeto", "Hydraulické jádro", "%", positions=CORES_4),
    DefinitionSpec("CORE_SPEED_IN", "Rychlost najeto", "Hydraulické jádro", "%", positions=CORES_4),
    DefinitionSpec("CORE_PRESSURE_OUT", "Tlak vyjeto", "Hydraulické jádro", "%", positions=CORES_4),
    DefinitionSpec("CORE_PRESSURE_IN", "Tlak najeto", "Hydraulické jádro", "%", positions=CORES_4),

    DefinitionSpec("MOLD_TEMPERATURE", "Teplota formy", "Teplota formy", "°C", positions=(("MOVING", "Pohyblivá strana"), ("FIXED", "Pevná strana"))),
    DefinitionSpec("MOLD_COOLING", "Chlazení formy", "Teplota formy", value_type="TEXT", positions=(("MOVING", "Pohyblivá strana"), ("FIXED", "Pevná strana"))),
    DefinitionSpec("HOT_RUNNER_TEMPERATURE", "Teplota horkého vtoku", "Teplota horkých vtoků", "°C", positions=numbered(30)),
    DefinitionSpec("BARREL_TEMPERATURE", "Teplota válce", "Teplota válce", "°C", positions=(("NOZZLE", "Tryska"),) + numbered(8) + (("HOPPER", "Násypka"),)),

    DefinitionSpec("SEQ_OPEN_INJECTION", "Otevření vstřiku", "Sekvence", "cm³", positions=PROFILE_8),
    DefinitionSpec("SEQ_CLOSE_INJECTION", "Uzavření vstřiku", "Sekvence", positions=PROFILE_8),
    DefinitionSpec("SEQ_OPEN_HOLDING", "Otevření dotlaku", "Sekvence", positions=PROFILE_8),
    DefinitionSpec("SEQ_CLOSE_HOLDING", "Uzavření dotlaku", "Sekvence", positions=PROFILE_8),

    DefinitionSpec("BOOSTING_PRESSURE", "Zvýšený specifický vstřikovací tlak", "Vstřikování, dávka, jednotka", value_type="BOOLEAN"),
    DefinitionSpec("INJECTION_POSITION", "Pozice vstřiku", "Vstřikování, dávka, jednotka", "mm", positions=PROFILE_9),
    DefinitionSpec("INJECTION_SPEED", "Rychlost vstřiku", "Vstřikování, dávka, jednotka", "mm/s", positions=PROFILE_9),
    DefinitionSpec("MAX_INJECTION_PRESSURE", "Limit tlaku", "Vstřikování, dávka, jednotka", "bar"),
    DefinitionSpec("TRANSFER_PRESSURE", "Tlak při přepnutí", "Vstřikování, dávka, jednotka", "bar"),
    DefinitionSpec("PEAK_PRESSURE", "Vrchol tlaku", "Vstřikování, dávka, jednotka", "bar"),
    DefinitionSpec("TRANSFER_POSITION", "Pozice přepnutí", "Vstřikování, dávka, jednotka", "mm"),
    DefinitionSpec("CUSHION", "Polštář", "Vstřikování, dávka, jednotka", "mm"),
    DefinitionSpec("HOLDING_TIME_PROFILE", "Čas dotlaku", "Vstřikování, dávka, jednotka", "s", positions=PROFILE_9),
    DefinitionSpec("HOLDING_PRESSURE", "Dotlak", "Vstřikování, dávka, jednotka", "bar", positions=PROFILE_9),
    DefinitionSpec("DOSING_STROKE", "Zdvih dávkování", "Vstřikování, dávka, jednotka", "mm"),
    DefinitionSpec("DECOMP_BEFORE", "Dekomprese před dávkou", "Vstřikování, dávka, jednotka", "mm"),
    DefinitionSpec("DECOMP_AFTER", "Dekomprese po dávce", "Vstřikování, dávka, jednotka", "mm"),
    DefinitionSpec("DECOMP_SPEED", "Rychlost dekomprese", "Vstřikování, dávka, jednotka", "%"),
    DefinitionSpec("DOSING_SPEED", "Rychlost dávky", "Vstřikování, dávka, jednotka", "%", positions=PROFILE_5),
    DefinitionSpec("DOSING_TIME", "Čas dávky", "Vstřikování, dávka, jednotka", "s"),
    DefinitionSpec("BACK_PRESSURE", "Zpětný tlak", "Vstřikování, dávka, jednotka", "bar", positions=PROFILE_5),

    DefinitionSpec("INJECTION_TIME", "Doba vstřikování", "Specifický časový limit", "s"),
    DefinitionSpec("HOLDING_TIME", "Čas dotlaku", "Specifický časový limit", "s"),
    DefinitionSpec("COOLING_TIME", "Doba chlazení", "Specifický časový limit", "s"),
    DefinitionSpec("CYCLE_TIME", "Doba cyklu", "Specifický časový limit", "s"),
    DefinitionSpec("CUSHION_TOLERANCE", "Tolerance polštáře", "Kontrola", "mm"),
    DefinitionSpec("INJECTION_TIME_TOLERANCE", "Tolerance vstřikování", "Kontrola", "s"),
    DefinitionSpec("DOSING_TIME_LIMIT", "Limit dávky", "Kontrola", "s"),
    DefinitionSpec("SHOT_WEIGHT", "Váha vstřiku s vtokem", "Kontrola", "g"),
    DefinitionSpec("SPRUE_WEIGHT", "Hmotnost vtoku", "Kontrola", "g"),
    DefinitionSpec("STARTUP_PIECES", "Počet rozjezdových kusů", "Kontrola", "ks"),
    DefinitionSpec("SPECIAL_NOTE", "Poznámky", "Poznámky", value_type="TEXT"),
)


BY_CODE = {item.code: item for item in DEFINITIONS}


def _number(code: str, value, position: str = "", minimum=None, maximum=None) -> dict:
    return {"definition_code": code, "position_key": position,
            "position_label": dict(BY_CODE[code].positions).get(position, position),
            "numeric_target": str(value),
            "numeric_min": str(minimum) if minimum is not None else None,
            "numeric_max": str(maximum) if maximum is not None else None,
            "text_value": None, "boolean_value": None, "note": ""}


def _text(code: str, value: str, position: str = "") -> dict:
    return {"definition_code": code, "position_key": position,
            "position_label": dict(BY_CODE[code].positions).get(position, position),
            "numeric_target": None, "numeric_min": None, "numeric_max": None,
            "text_value": value, "boolean_value": None, "note": ""}


def _boolean(code: str, value: bool) -> dict:
    return {"definition_code": code, "position_key": "", "position_label": "",
            "numeric_target": None, "numeric_min": None, "numeric_max": None,
            "text_value": None, "boolean_value": value, "note": ""}


def _profile(code: str, values: tuple) -> list[dict]:
    return [_number(code, value, str(index)) for index, value in enumerate(values, start=1)]


# Values transcribed from the supplied, already approved U10 / 3045 sheet.  The
# template is a starting point only; creating a draft never changes this data.
REFERENCE_U10_3045 = {
    "product_name": "Blende B-Säule oben schwarz",
    "material_name": "Finalloy SMV-66 HM black",
    "process_note": "UZAV. TRYSKA: HYDRAULICKY\nPohyblivá strana: studená voda",
    "parameters": [
        _text("CUSTOMER", "MATI"), _text("SAP_REFERENCE", "SEE BOM"),
        _text("PART_VARIANT", "LH/RH"), _text("CAVITIES", "1+1"),
        _text("TECHNICIAN_NAME", "J. Kubec"), _number("SCREW_DIAMETER", 105),
        _text("RAW_MATERIAL", "Finalloy SMV-66 HM black (SAP: PPM0254)"),
        _number("REGRIND_PERCENT", 0), _number("DRYING_TEMPERATURE", 60),
        _number("DRYING_TIME", 2), _text("MACHINE_PROGRAM", "3045_:_B Säule oben U10"),
        _boolean("ROBOT", True), _text("ROBOT_PROGRAM", "PRG17 - 3045B SÄULE OBEN U10"),
        _number("CLAMPING_FORCE", 3500),
        *_profile("CLOSING_POSITION", (800, 600, 300, 190, 30, 0.5)),
        *_profile("CLOSING_SPEED", (30, 70, 70, 20, 12, 12)),
        *_profile("MOLD_PROTECTION_POSITION", (800, 250, 200, 190, 10, 0.5)),
        *_profile("MOLD_PROTECTION_FORCE", (60, 60, 60, 30, 25, 30)),
        _number("MOLD_PROTECTION_STROKE", 130), _number("MOLD_PROTECTION_TIME", 3),
        _number("HIGH_SPEED_LOCKING", 0.5),
        *_profile("OPENING_POSITION", (800, 600, 220, 190, 150, 0)),
        *_profile("OPENING_SPEED", (30, 70, 70, 45, 15, 15)),
        _number("OPENING_STROKE", 800), _number("EJECTOR_START_POSITION", 88),
        _number("EJECTOR_CONTROLLED_POSITION", 205), _number("EJECTOR_REAL_STROKE", 117),
        _number("EJECTOR_PRIORITY_OUT", 1), _number("EJECTOR_PRIORITY_IN", 1),
        _number("EJECTOR_SPEED_OUT", 45, "1"), _number("EJECTOR_SPEED_IN", 40, "1"),
        _number("EJECTOR_PRESSURE_OUT", 35, "1"), _number("EJECTOR_PRESSURE_IN", 20, "1"),
        _number("MOLD_TEMPERATURE", 35, "MOVING"), _number("MOLD_TEMPERATURE", 35, "FIXED"),
        _text("MOLD_COOLING", "Studená voda", "MOVING"),
        _text("MOLD_COOLING", "Studená voda", "FIXED"),
        _number("HOT_RUNNER_TEMPERATURE", 225, "1"),
        _number("HOT_RUNNER_TEMPERATURE", 225, "2"),
        _number("HOT_RUNNER_TEMPERATURE", 225, "3"),
        _number("BARREL_TEMPERATURE", 245, "NOZZLE"),
        _number("BARREL_TEMPERATURE", 240, "1"), _number("BARREL_TEMPERATURE", 235, "2"),
        _number("BARREL_TEMPERATURE", 225, "3"), _number("BARREL_TEMPERATURE", 215, "4"),
        _number("BARREL_TEMPERATURE", 205, "5"), _number("BARREL_TEMPERATURE", 70, "HOPPER"),
        _boolean("BOOSTING_PRESSURE", False), _number("INJECTION_SPEED", 30, "1"),
        _number("MAX_INJECTION_PRESSURE", 100), _number("TRANSFER_PRESSURE", 56.1),
        _number("PEAK_PRESSURE", 56.1), _number("TRANSFER_POSITION", 30),
        _number("CUSHION", 19.5), _number("HOLDING_TIME_PROFILE", 7, "1"),
        _number("HOLDING_PRESSURE", 20, "1"), _number("DOSING_STROKE", 125),
        _number("DECOMP_AFTER", 5), _number("DECOMP_SPEED", 5),
        _number("DOSING_SPEED", 80, "1"), _number("DOSING_TIME", 10.7),
        _number("BACK_PRESSURE", 10, "1"), _number("INJECTION_TIME", 3.48),
        _number("HOLDING_TIME", 7), _number("COOLING_TIME", 14.5), _number("CYCLE_TIME", 41),
        _number("CUSHION_TOLERANCE", 19.5, minimum=14.5, maximum=21.5),
        _number("INJECTION_TIME_TOLERANCE", 3.48, minimum=3.2, maximum=3.8),
        _number("DOSING_TIME_LIMIT", 14.4), _number("SHOT_WEIGHT", 455.07),
        _number("SPRUE_WEIGHT", 20.67), _number("STARTUP_PIECES", 1),
        _text("SPECIAL_NOTE", "UZAV. TRYSKA: HYDRAULICKY\nPohyblivá strana: studená voda"),
    ],
}
