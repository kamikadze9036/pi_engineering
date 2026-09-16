"""Single-sheet ENGEL operation instruction based on the supplied company form."""
import io
import os
from collections import defaultdict
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .models import PdfTemplate, Revision


PAGE_W, PAGE_H = letter
BLACK = colors.HexColor("#171717")
GRID = colors.HexColor("#575757")


def register_fonts() -> tuple[str, str]:
    regular = os.getenv("SPECS_PDF_FONT", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    bold = os.getenv("SPECS_PDF_FONT_BOLD", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    if not os.path.exists(regular):
        regular = "/System/Library/Fonts/Supplemental/Arial.ttf"
        bold = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    if not os.path.exists(regular) or not os.path.exists(bold):
        raise RuntimeError("Chybí TrueType font pro české znaky v PDF.")
    if "SpecsRegular" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("SpecsRegular", regular))
        pdfmetrics.registerFont(TTFont("SpecsBold", bold))
    return "SpecsRegular", "SpecsBold"


def fmt_number(number: Decimal | None) -> str:
    if number is None:
        return ""
    return format(number.normalize(), "f").replace(".", ",")


class SheetValues:
    def __init__(self, revision: Revision):
        self.items = defaultdict(dict)
        for item in revision.parameters:
            self.items[item.definition_code][item.position_key or ""] = item

    def item(self, code: str, position: str = ""):
        return self.items.get(code, {}).get(position)

    def raw(self, code: str, position: str = "", blank: str = "·") -> str:
        item = self.item(code, position)
        if not item:
            return blank
        if item.definition_type == "NUMERIC":
            return fmt_number(item.numeric_target) or blank
        if item.definition_type == "BOOLEAN":
            return "ANO" if item.boolean_value else "NE"
        return item.text_value or blank

    def bounds(self, code: str, position: str = "") -> tuple[str, str]:
        item = self.item(code, position)
        return (fmt_number(item.numeric_min) if item else "",
                fmt_number(item.numeric_max) if item else "")


class Sheet:
    def __init__(self, c: canvas.Canvas, template: PdfTemplate, font: str, bold: str):
        self.c, self.template, self.font, self.bold = c, template, font, bold
        self.accent = colors.HexColor(template.settings.get("accent_color", "#153AA8"))
        self.section = colors.HexColor(template.settings.get("section_color", "#E2E4E7"))
        self.english = template.settings.get("show_english_subtitle", True)
        c.setLineWidth(.35)
        c.setStrokeColor(GRID)

    def fit(self, value: object, width: float, font: str, size: float) -> str:
        text = str(value or "")
        if pdfmetrics.stringWidth(text, font, size) <= width:
            return text
        while text and pdfmetrics.stringWidth(text + "…", font, size) > width:
            text = text[:-1]
        return text + "…"

    def text(self, x: float, y: float, value: object, width: float, size: float = 5.4,
             font: str | None = None, color=BLACK, align: str = "left") -> None:
        font = font or self.font
        value = self.fit(value, width, font, size)
        self.c.setFont(font, size)
        self.c.setFillColor(color)
        if align == "center":
            self.c.drawCentredString(x + width / 2, y, value)
        elif align == "right":
            self.c.drawRightString(x + width, y, value)
        else:
            self.c.drawString(x, y, value)

    def box(self, x: float, y_top: float, width: float, height: float, fill=None) -> None:
        if fill:
            self.c.setFillColor(fill)
            self.c.rect(x, y_top - height, width, height, fill=1, stroke=1)
        else:
            self.c.rect(x, y_top - height, width, height, fill=0, stroke=1)

    def section_header(self, x: float, y_top: float, width: float, cz: str, en: str) -> float:
        height = 15
        self.box(x, y_top, width, height, self.section)
        self.text(x + 3, y_top - 6, cz.upper(), width - 6, 6.2, self.bold, align="center")
        if self.english:
            self.text(x + 3, y_top - 12, en.upper(), width - 6, 4.2, self.font, align="center")
        return y_top - height

    def labelled_cell(self, x: float, y_top: float, width: float, height: float,
                      cz: str, en: str, value: str, unit: str = "") -> None:
        self.box(x, y_top, width, height)
        self.text(x + 3, y_top - 6, cz, width - 6, 4.6, self.bold)
        if self.english:
            self.text(x + 3, y_top - 11, en, width - 6, 3.6)
        rendered = f"{value} {unit}".strip()
        self.text(x + 3, y_top - height + 4, rendered, width - 6, 6.0, self.bold, self.accent, "right")

    def sequence(self, x: float, y_top: float, width: float, height: float,
                 cz: str, en: str, values: list[str], unit: str = "") -> float:
        label_w, unit_w = width * .32, 23
        value_w = (width - label_w - unit_w) / len(values)
        self.box(x, y_top, width, height)
        self.c.line(x + label_w, y_top, x + label_w, y_top - height)
        self.text(x + 3, y_top - 7, cz, label_w - 6, 4.4, self.bold)
        if self.english:
            self.text(x + 3, y_top - 12, en, label_w - 6, 3.4)
        for index, value in enumerate(values):
            cell_x = x + label_w + value_w * index
            if index:
                self.c.line(cell_x, y_top, cell_x, y_top - height)
            self.text(cell_x, y_top - 4.5, str(index + 1), value_w, 3.3, self.font, align="center")
            self.text(cell_x + 1, y_top - height + 4, value, value_w - 2, 5.2, self.bold,
                      self.accent, "center")
        self.c.line(x + width - unit_w, y_top, x + width - unit_w, y_top - height)
        self.text(x + width - unit_w, y_top - height + 4, unit, unit_w, 4.2, self.font, align="center")
        return y_top - height

    def pair_row(self, x: float, y_top: float, width: float, height: float,
                 items: list[tuple[str, str, str, str]]) -> float:
        cell = width / len(items)
        for index, (cz, en, value, unit) in enumerate(items):
            self.labelled_cell(x + index * cell, y_top, cell, height, cz, en, value, unit)
        return y_top - height


def positions(values: SheetValues, code: str, keys) -> list[str]:
    return [values.raw(code, str(key)) for key in keys]


def draw_header(sheet: Sheet, revision: Revision, values: SheetValues) -> float:
    x, width, y = 14, 584, 779
    sheet.box(x, y, width, 38)
    sheet.c.line(83, y, 83, y - 38)
    sheet.c.line(515, y, 515, y - 38)
    sheet.text(19, y - 17, "HESS", 58, 15, sheet.bold, colors.HexColor("#18345D"), "center")
    title = sheet.template.title
    if "ENGEL" not in title.upper():
        title += ": ENGEL (CC100/200/300)"
    sheet.text(88, y - 14, title, 422, 9.1, sheet.bold, align="center")
    if sheet.english:
        sheet.text(88, y - 27, "INJECTION ADJUSTMENT SHEET (TYPE): ENGEL (CC100/200/300)",
                   422, 5.2, sheet.font, sheet.accent, "center")
    sheet.text(519, y - 8, "Stránka / Page", 74, 4.2, sheet.bold)
    sheet.text(519, y - 17, "1 / 1", 74, 6, sheet.bold, sheet.accent, "right")
    sheet.text(519, y - 27, "Číslo DT / N° DT", 74, 4.2, sheet.bold)
    sheet.text(519, y - 35, f"{revision.process_spec_id:04d} / R{revision.revision_number}",
               74, 5.2, sheet.bold, sheet.accent, "right")
    y -= 38

    cells = [
        (120, "Zákazník", "Customer", values.raw("CUSTOMER")),
        (230, "Jméno výrobku", "Part name",
         f"{revision.product_name or '·'}  {values.raw('PART_VARIANT', blank='')}".strip()),
        (160, "Číslo výrobku (SAP)", "Reference (SAP)", values.raw("SAP_REFERENCE")),
        (74, "Počet kavit", "Nber of cavities", values.raw("CAVITIES")),
    ]
    cursor = x
    for cell_w, cz, en, value in cells:
        sheet.labelled_cell(cursor, y, cell_w, 29, cz, en, value)
        cursor += cell_w
    y -= 29
    cells = [
        (150, "Jméno technika", "Technician name", values.raw("TECHNICIAN_NAME")),
        (185, "Číslo lisu", "Press number", revision.mes_machine_code or "·"),
        (125, "Průměr šroubu", "Screw diameter", values.raw("SCREW_DIAMETER"), "mm"),
        (124, "Průměr trysky", "Nozzle diameter", values.raw("NOZZLE_DIAMETER"), "mm"),
    ]
    cursor = x
    for cell in cells:
        cell_w, cz, en, value, *unit = cell
        sheet.labelled_cell(cursor, y, cell_w, 28, cz, en, value, unit[0] if unit else "")
        cursor += cell_w
    y -= 28
    cells = [
        (260, "Vstupní materiál", "Raw material", values.raw("RAW_MATERIAL", blank=revision.material_name or "·")),
        (92, "Recyklovaný materiál", "Regrind material", values.raw("REGRIND_PERCENT"), "%"),
        (132, "Teplota sušení", "Drying temperature", values.raw("DRYING_TEMPERATURE"), "°C ±10°C"),
        (100, "Čas", "Time", values.raw("DRYING_TIME"), "h"),
    ]
    cursor = x
    for cell in cells:
        cell_w, cz, en, value, *unit = cell
        sheet.labelled_cell(cursor, y, cell_w, 28, cz, en, value, unit[0] if unit else "")
        cursor += cell_w
    y -= 28
    cells = [
        (280, "Program vstřikolisu", "Machine program", values.raw("MACHINE_PROGRAM")),
        (76, "Robot", "Robot", values.raw("ROBOT")),
        (228, "Program robota", "Robot program", values.raw("ROBOT_PROGRAM")),
    ]
    cursor = x
    for cell_w, cz, en, value in cells:
        sheet.labelled_cell(cursor, y, cell_w, 27, cz, en, value)
        cursor += cell_w
    return y - 27


def draw_left(sheet: Sheet, revision: Revision, values: SheetValues, y: float) -> None:
    x, width = 14, 284
    y = sheet.section_header(x, y, width, "Zavření, otevření, výstřik", "Closing, opening, ejection")
    y = sheet.pair_row(x, y, width, 15, [("Uzavírací síla", "Clamping force", values.raw("CLAMPING_FORCE"), "kN")])
    y = sheet.sequence(x, y, width, 18, "Dráha zavírání formy", "Closing stroke", positions(values, "CLOSING_POSITION", range(1, 7)), "mm")
    y = sheet.sequence(x, y, width, 18, "Rychlost zavření", "Closing speed", positions(values, "CLOSING_SPEED", range(1, 7)), "%")
    y = sheet.sequence(x, y, width, 18, "Dráha ochrany formy", "Mould protection stroke", positions(values, "MOLD_PROTECTION_POSITION", range(1, 7)), "mm")
    y = sheet.sequence(x, y, width, 18, "Síla ochrany formy", "Mould protection force", positions(values, "MOLD_PROTECTION_FORCE", range(1, 7)), "%")
    y = sheet.pair_row(x, y, width, 17, [
        ("Dráha ochrany formy", "Mould protection stroke", values.raw("MOLD_PROTECTION_STROKE"), "mm"),
        ("Doba kontroly", "Protection time", values.raw("MOLD_PROTECTION_TIME"), "s"),
        ("Rychloposuv uzavřen", "High speed locking", values.raw("HIGH_SPEED_LOCKING"), "mm"),
    ])
    y = sheet.sequence(x, y, width, 18, "Dráha otevírání formy", "Opening stroke profile", positions(values, "OPENING_POSITION", range(1, 7)), "mm")
    y = sheet.sequence(x, y, width, 18, "Rychlost otevření", "Opening speed", positions(values, "OPENING_SPEED", range(1, 7)), "%")
    y = sheet.pair_row(x, y, width, 16, [("Dráha otevření", "Opening stroke", values.raw("OPENING_STROKE"), "mm")])

    y = sheet.section_header(x, y, width, "Vyhazovače", "Ejector")
    y = sheet.pair_row(x, y, width, 18, [
        ("Pozice vyhazovačů", "Ejector pins outset", values.raw("EJECTOR_START_POSITION"), "mm"),
        ("Kontrolovaná pozice", "Position controlled", values.raw("EJECTOR_CONTROLLED_POSITION"), "mm"),
    ])
    y = sheet.pair_row(x, y, width, 18, [
        ("Reálná délka", "Real ejection stroke", values.raw("EJECTOR_REAL_STROKE"), "mm"),
        ("Čas", "Time", values.raw("EJECTOR_TIME"), "s"),
    ])
    y = sheet.pair_row(x, y, width, 17, [
        ("Priorita VEN", "Priority OUT", values.raw("EJECTOR_PRIORITY_OUT"), ""),
        ("Priorita DOVNITŘ", "Priority IN", values.raw("EJECTOR_PRIORITY_IN"), ""),
    ])
    y = sheet.sequence(x, y, width, 17, "Rychlost VEN / DOVNITŘ", "Ejector speed OUT / IN",
                       [values.raw("EJECTOR_SPEED_OUT", "1"), values.raw("EJECTOR_SPEED_OUT", "2"),
                        values.raw("EJECTOR_SPEED_IN", "1"), values.raw("EJECTOR_SPEED_IN", "2")], "%")
    y = sheet.sequence(x, y, width, 17, "Tlak VEN / DOVNITŘ", "Ejector pressure OUT / IN",
                       [values.raw("EJECTOR_PRESSURE_OUT", "1"), values.raw("EJECTOR_PRESSURE_OUT", "2"),
                        values.raw("EJECTOR_PRESSURE_IN", "1"), values.raw("EJECTOR_PRESSURE_IN", "2")], "%")

    y = sheet.section_header(x, y, width, "Hydraulické jádro", "Hydraulic core")
    label_w, cell_w = 69, (width - 69) / 4
    sheet.box(x, y, width, 14)
    sheet.text(x + 3, y - 9, "Jádro / Core", label_w - 6, 4.4, sheet.bold)
    for index in range(4):
        cell_x = x + label_w + cell_w * index
        sheet.c.line(cell_x, y, cell_x, y - 14)
        title = f"{values.raw('CORE_NUMBER', str(index + 1))} {values.raw('CORE_TITLE', str(index + 1), '')}".strip()
        sheet.text(cell_x + 1, y - 9, title, cell_w - 2, 4.4, sheet.bold, sheet.accent, "center")
    y -= 14
    core_rows = [
        ("Priorita OUT", "CORE_PRIORITY_OUT", ""), ("Priorita IN", "CORE_PRIORITY_IN", ""),
        ("Pozice OUT", "CORE_POSITION_OUT", "mm"), ("Pozice IN", "CORE_POSITION_IN", "mm"),
        ("Rychlost OUT", "CORE_SPEED_OUT", "%"), ("Rychlost IN", "CORE_SPEED_IN", "%"),
        ("Tlak OUT", "CORE_PRESSURE_OUT", "%"), ("Tlak IN", "CORE_PRESSURE_IN", "%"),
    ]
    for label, code, unit in core_rows:
        sheet.box(x, y, width, 11)
        sheet.text(x + 3, y - 7.5, label, label_w - 6, 4.0, sheet.font)
        for index in range(4):
            cell_x = x + label_w + cell_w * index
            sheet.c.line(cell_x, y, cell_x, y - 11)
            rendered = f"{values.raw(code, str(index + 1))} {unit}".strip()
            sheet.text(cell_x + 1, y - 7.5, rendered, cell_w - 2, 4.3, sheet.bold, sheet.accent, "center")
        y -= 11

    y = sheet.section_header(x, y, width, "Poznámky", "Remarks")
    sheet.box(x, y, width, y - 40)
    note = values.raw("SPECIAL_NOTE", blank=revision.process_note or "")
    lines = [line.strip() for line in note.splitlines() if line.strip()] or [" "]
    cursor = y - 10
    for line in lines[:7]:
        sheet.text(x + 5, cursor, line, width - 10, 5.2, sheet.bold)
        cursor -= 9


def draw_right(sheet: Sheet, values: SheetValues, y: float) -> None:
    x, width = 302, 296
    y = sheet.section_header(x, y, width, "Teplota formy", "Mould temperature")
    y = sheet.pair_row(x, y, width, 24, [
        ("Pohyblivá strana", "Moving side", values.raw("MOLD_TEMPERATURE", "MOVING"), "°C"),
        ("Pevná strana", "Fixed side", values.raw("MOLD_TEMPERATURE", "FIXED"), "°C"),
        ("Chlazení", "Cooling", f"{values.raw('MOLD_COOLING', 'MOVING')} / {values.raw('MOLD_COOLING', 'FIXED')}", ""),
    ])
    y = sheet.section_header(x, y, width, "Teplota horkých vtoků", "Hot runner tool temperature")
    for start in (1, 11, 21):
        y = sheet.sequence(x, y, width, 22, f"Zóny {start}–{start + 9}", "Zones",
                           positions(values, "HOT_RUNNER_TEMPERATURE", range(start, start + 10)), "°C")
    y = sheet.section_header(x, y, width, "Teplota válce", "Cylinder temperature")
    barrel_keys = ["NOZZLE"] + [str(i) for i in range(1, 9)] + ["HOPPER"]
    y = sheet.sequence(x, y, width, 24, "Tryska · 1–8 · Násypka", "Nozzle · zones · hopper",
                       positions(values, "BARREL_TEMPERATURE", barrel_keys), "°C")
    y = sheet.section_header(x, y, width, "Sekvence", "Sequential")
    for cz, en, code, unit in (
        ("Otevření vstřiku", "Opening injection", "SEQ_OPEN_INJECTION", "cm³"),
        ("Uzavření vstřiku", "Closing injection", "SEQ_CLOSE_INJECTION", ""),
        ("Otevření dotlaku", "Opening holding pressure", "SEQ_OPEN_HOLDING", ""),
        ("Uzavření dotlaku", "Closing holding pressure", "SEQ_CLOSE_HOLDING", ""),
    ):
        y = sheet.sequence(x, y, width, 16, cz, en, positions(values, code, range(1, 9)), unit)

    y = sheet.section_header(x, y, width, "Vstřikování, dávka, jednotka", "Injection, dosing, unit")
    y = sheet.pair_row(x, y, width, 16, [("Zvýšený specifický tlak", "Boosting pressure", values.raw("BOOSTING_PRESSURE"), "")])
    y = sheet.sequence(x, y, width, 17, "Pozice", "Position", positions(values, "INJECTION_POSITION", range(1, 10)), "mm")
    y = sheet.sequence(x, y, width, 17, "Rychlost vstřiku", "Injection speed", positions(values, "INJECTION_SPEED", range(1, 10)), "mm/s")
    y = sheet.pair_row(x, y, width, 18, [
        ("Limit tlaku", "Pressure limit", values.raw("MAX_INJECTION_PRESSURE"), "bar"),
        ("Tlak při přepnutí", "Switchover pressure", values.raw("TRANSFER_PRESSURE"), "bar"),
        ("Vrchol tlaku", "Pressure peak", values.raw("PEAK_PRESSURE"), "bar"),
    ])
    y = sheet.pair_row(x, y, width, 18, [
        ("Pozice přepnutí", "Switchover position", values.raw("TRANSFER_POSITION"), "mm"),
        ("Polštář", "Cushion", values.raw("CUSHION"), "mm"),
    ])
    y = sheet.sequence(x, y, width, 17, "Čas dotlaku", "Holding pressure time", positions(values, "HOLDING_TIME_PROFILE", range(1, 10)), "s")
    y = sheet.sequence(x, y, width, 17, "Dotlak", "Holding pressure", positions(values, "HOLDING_PRESSURE", range(1, 10)), "bar")
    y = sheet.pair_row(x, y, width, 18, [
        ("Zdvih dávkování", "Dosing stroke", values.raw("DOSING_STROKE"), "mm"),
        ("Dekomprese před", "Decomp. before dosing", values.raw("DECOMP_BEFORE"), "mm"),
        ("Dekomprese po", "After dosing", values.raw("DECOMP_AFTER"), "mm"),
        ("Rychlost dekompr.", "Decomp. speed", values.raw("DECOMP_SPEED"), "%"),
    ])
    y = sheet.sequence(x, y, width, 17, "Rychlost dávky", "Dosing speed", positions(values, "DOSING_SPEED", range(1, 6)), "%")
    y = sheet.sequence(x, y, width, 17, "Zpětný tlak", "Back pressure", positions(values, "BACK_PRESSURE", range(1, 6)), "bar")
    y = sheet.pair_row(x, y, width, 16, [("Čas dávky", "Dosing time", values.raw("DOSING_TIME"), "s")])

    y = sheet.section_header(x, y, width, "Specifický časový limit", "Specified time out")
    y = sheet.pair_row(x, y, width, 23, [
        ("Doba vstřikování", "Injection time", values.raw("INJECTION_TIME"), "s"),
        ("Čas dotlaku", "Holding pressure time", values.raw("HOLDING_TIME"), "s"),
        ("Doba chlazení", "Cooling time", values.raw("COOLING_TIME"), "s"),
        ("Doba cyklu", "Cycle time", values.raw("CYCLE_TIME"), "s"),
    ])
    y = sheet.section_header(x, y, width, "Kontrola", "Control")
    cushion_min, cushion_max = values.bounds("CUSHION_TOLERANCE")
    injection_min, injection_max = values.bounds("INJECTION_TIME_TOLERANCE")
    y = sheet.pair_row(x, y, width, 16, [
        ("Tolerance polštáře", "Cushion tolerance", f"{cushion_min or '·'} – {cushion_max or '·'}", "mm"),
        ("Tolerance vstřikování", "Injection tolerance", f"{injection_min or '·'} – {injection_max or '·'}", "s"),
        ("Limit dávky", "Dosing time limit", values.raw("DOSING_TIME_LIMIT"), "s"),
    ])
    y = sheet.pair_row(x, y, width, 17, [
        ("Váha vstřiku s vtokem", "Shot weight with sprue", values.raw("SHOT_WEIGHT"), "g"),
        ("Hmotnost vtoku", "Sprue weight", values.raw("SPRUE_WEIGHT"), "g"),
        ("Rozjezdové kusy", "Rejected shots", values.raw("STARTUP_PIECES"), "ks"),
    ])
    if y > 40:
        sheet.box(x, y, width, y - 40)


def draw_footer(sheet: Sheet, revision: Revision, author_name: str, approver_name: str) -> None:
    x, y, width, height = 14, 40, 584, 25
    sheet.box(x, y, width, height)
    sheet.text(x + 4, y - 7, "TOLERANCE HODNOT BEZ SPECIFIKOVANÝCH TOLERANCÍ JE ±10 %",
               310, 4.6, sheet.bold)
    sheet.text(x + 4, y - 17, "Autor / Technician", 70, 4.0)
    sheet.text(x + 75, y - 17, author_name, 120, 5.0, sheet.bold, sheet.accent)
    sheet.text(x + 205, y - 17, "Schválil / Approved", 83, 4.0)
    sheet.text(x + 288, y - 17, approver_name, 115, 5.0, sheet.bold, sheet.accent)
    date = revision.approved_at.strftime("%d.%m.%Y") if revision.approved_at else ""
    sheet.text(x + 410, y - 17, "Datum / Date", 58, 4.0)
    sheet.text(x + 468, y - 17, date, 108, 5.0, sheet.bold, sheet.accent)


def generate_pdf(revision: Revision, template: PdfTemplate,
                 author_name: str, approver_name: str) -> bytes:
    font, bold = register_fonts()
    stream = io.BytesIO()
    c = canvas.Canvas(stream, pagesize=letter)
    c.setTitle(f"Operační návodka - revize {revision.revision_number}")
    sheet = Sheet(c, template, font, bold)
    values = SheetValues(revision)
    body_top = draw_header(sheet, revision, values)
    draw_left(sheet, revision, values, body_top)
    draw_right(sheet, values, body_top)
    draw_footer(sheet, revision, author_name, approver_name)
    c.showPage()
    c.save()
    return stream.getvalue()
