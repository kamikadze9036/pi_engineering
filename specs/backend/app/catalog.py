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
    DefinitionSpec("REGRIND_PERCENT", "Recyklovaný materiál", "Základní údaje", "%"),
    DefinitionSpec("DRYING_TEMPERATURE", "Teplota sušení", "Základní údaje", "°C"),
    DefinitionSpec("DRYING_TIME", "Čas sušení", "Základní údaje", "h"),
    DefinitionSpec("MACHINE_PROGRAM", "Program vstřikolisu", "Základní údaje", value_type="TEXT"),
    DefinitionSpec("ROBOT", "Robot", "Základní údaje", value_type="BOOLEAN"),
    DefinitionSpec("ROBOT_PROGRAM", "Program robota", "Základní údaje", value_type="TEXT"),

    DefinitionSpec("CLAMPING_FORCE", "Uzavírací síla", "Zavření, otevření, výstřik", "kN"),
    DefinitionSpec("CLOSING_POSITION", "Dráha zavírání formy", "Zavření, otevření, výstřik", "mm", positions=PROFILE_6),
    DefinitionSpec("CLOSING_SPEED", "Rychlost zavření", "Zavření, otevření, výstřik", "%", positions=PROFILE_6),
    DefinitionSpec("MOLD_PROTECTION_POSITION", "Dráha ochrany formy", "Zavření, otevření, výstřik", "mm", positions=PROFILE_6),
    DefinitionSpec("MOLD_PROTECTION_FORCE", "Síla ochrany formy", "Zavření, otevření, výstřik", "%", positions=PROFILE_6),
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
