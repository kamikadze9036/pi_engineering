"""First PDF layout inspired by the uploaded ENGEL operation sheet.

The source example is much denser than this MVP and has machine-specific fields.
Layout settings are read from a versioned template; issued PDFs are archived.
"""
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


LEFT = ["Zavření, otevření, výstřik", "Hydraulické jádro", "Poznámky"]
RIGHT = ["Teplota formy", "Teplota horkých vtoků", "Teplota válce",
         "Vstřikování, dávka, jednotka", "Specifický časový limit", "Kontrola"]
ENGLISH = {
    "Zavření, otevření, výstřik": "CLOSING, OPENING, EJECTION",
    "Hydraulické jádro": "HYDRAULIC CORE",
    "Poznámky": "REMARKS",
    "Teplota formy": "MOULD TEMPERATURE",
    "Teplota horkých vtoků": "HOT RUNNER TEMPERATURE",
    "Teplota válce": "CYLINDER TEMPERATURE",
    "Vstřikování, dávka, jednotka": "INJECTION, DOSING, UNIT",
    "Specifický časový limit": "SPECIFIED TIME OUT",
    "Kontrola": "CONTROL",
}
ALIASES = {
    "Dotlak": "Vstřikování, dávka, jednotka",
    "Vstřikování": "Vstřikování, dávka, jednotka",
    "Temperace nástroje": "Teplota formy",
    "Teploty válce": "Teplota válce",
    "Časy": "Specifický časový limit",
}


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


def display_value(item) -> str:
    if item.definition_type == "NUMERIC":
        value = fmt_number(item.numeric_target)
        if item.numeric_min is not None or item.numeric_max is not None:
            value += f"  [{fmt_number(item.numeric_min) or '-'} až {fmt_number(item.numeric_max) or '-'}]"
        return f"{value} {item.unit}".strip()
    if item.definition_type == "BOOLEAN":
        return "Ano" if item.boolean_value else "Ne"
    return item.text_value or ""


def entries_for(revision: Revision, categories: list[str]):
    grouped = defaultdict(list)
    for item in revision.parameters:
        grouped[ALIASES.get(item.definition_category, item.definition_category)].append(item)
    entries = []
    for category in categories:
        if not grouped[category]:
            continue
        entries.append(("heading", category))
        for item in grouped[category]:
            entries.append(("row", item))
    return entries


def wrap_lines(value: str, font: str, size: float, max_width: float) -> list[str]:
    lines = []
    line = ""
    for word in str(value).split():
        candidate = f"{line} {word}".strip()
        if line and pdfmetrics.stringWidth(candidate, font, size) > max_width:
            lines.append(line)
            line = word
        else:
            line = candidate
        if pdfmetrics.stringWidth(line, font, size) > max_width:
            fragment = ""
            for char in line:
                if fragment and pdfmetrics.stringWidth(fragment + char, font, size) > max_width:
                    lines.append(fragment)
                    fragment = char
                else:
                    fragment += char
            line = fragment
    if line or not lines:
        lines.append(line)
    return lines


def row_layout(item, font: str, bold: str):
    label = item.definition_name
    if item.position_label or item.position_key:
        label += f" - {item.position_label or item.position_key}"
    labels = wrap_lines(label, font, 7, 142)
    main = (f"{fmt_number(item.numeric_target)} {item.unit}".strip() if item.definition_type == "NUMERIC"
            else display_value(item))
    values = wrap_lines(main, bold, 8, 118)
    tolerance = ""
    if item.definition_type == "NUMERIC" and (item.numeric_min is not None or item.numeric_max is not None):
        tolerance = f"min {fmt_number(item.numeric_min) or '-'}  max {fmt_number(item.numeric_max) or '-'}"
    notes = wrap_lines(item.note, font, 6, 265) if item.note else []
    main_lines = max(len(labels), len(values))
    height = 16 + main_lines * 10 + (10 if tolerance else 0) + len(notes) * 9
    return labels, values, tolerance, notes, max(25, height)


def split_pages(entries, font: str, bold: str, capacity: float = 520):
    pages = [[]]
    used = 0
    heading = None
    for entry in entries:
        height = row_layout(entry[1], font, bold)[-1] if entry[0] == "row" else 29
        if used + height > capacity:
            pages.append([])
            used = 0
            if entry[0] == "row" and heading:
                pages[-1].append(("heading", heading))
                used += 29
        pages[-1].append(entry)
        used += height
        if entry[0] == "heading":
            heading = entry[1]
    return pages


def draw_text(c, x, y, text, max_width, font, size=8, color=colors.black):
    c.setFont(font, size)
    c.setFillColor(color)
    value = str(text)
    while value and pdfmetrics.stringWidth(value, font, size) > max_width:
        value = value[:-2]
    if value != str(text):
        value += "…"
    c.drawString(x, y, value)


def draw_header(c, revision: Revision, template: PdfTemplate, font: str, bold: str,
                author_name: str, approver_name: str, page: int, pages: int):
    width, height = letter
    accent = colors.HexColor(template.settings.get("accent_color", "#153AA8"))
    c.setStrokeColor(colors.black)
    c.rect(22, 42, width - 44, height - 64)
    c.line(22, 661, width - 22, 661)
    c.setFont(bold, 12)
    c.drawCentredString(width / 2, 755, template.title)
    if template.settings.get("show_english_subtitle", True):
        c.setFillColor(accent)
        c.setFont(font, 8)
        c.drawCentredString(width / 2, 740, "INJECTION ADJUSTMENT SHEET")
    c.setFillColor(colors.black)
    c.setFont(font, 8)
    c.drawRightString(width - 30, 755, f"Strana {page}/{pages}")
    c.drawRightString(width - 30, 740, f"Revize {revision.revision_number}")
    top = {item.definition_code: display_value(item) for item in revision.parameters
           if item.definition_category == "Základní údaje"}
    draw_text(c, 31, 724, f"Zákazník: {top.get('CUSTOMER', '-')}", 155, font, 8)
    draw_text(c, 190, 724, f"Výrobek: {revision.product_name}", 250, bold, 9, accent)
    draw_text(c, 446, 724, f"SAP: {top.get('SAP_REFERENCE', '-')}", 130, font, 8)
    draw_text(c, 31, 708, f"Technik: {top.get('TECHNICIAN_NAME', '-')}", 160, font)
    draw_text(c, 198, 708, f"Lis: {revision.mes_machine_code}  {revision.mes_machine_name}", 255, bold, 8, accent)
    draw_text(c, 463, 708, f"Šroub: {top.get('SCREW_DIAMETER', '-')}", 110, font)
    draw_text(c, 31, 692, f"Materiál: {top.get('RAW_MATERIAL', revision.material_name or '-')}", 310, font)
    draw_text(c, 352, 692, f"Sušení: {top.get('DRYING_TEMPERATURE', '-')} / {top.get('DRYING_TIME', '-')}", 225, font)
    draw_text(c, 31, 676, f"Program: {top.get('MACHINE_PROGRAM', '-')}", 300, font)
    draw_text(c, 340, 676, f"Forma: {revision.mes_tool_code}  {revision.mes_tool_name}", 235, font)
    c.setFont(font, 7)
    c.drawString(30, 58, f"Autor: {author_name}")
    c.drawString(222, 58, f"Schválil: {approver_name}")
    c.drawRightString(width - 30, 58, revision.approved_at.strftime("%d.%m.%Y") if revision.approved_at else "")
    c.line(22, 78, width - 22, 78)


def draw_column(c, entries, x, template, font, bold):
    accent = colors.HexColor(template.settings.get("accent_color", "#153AA8"))
    section = colors.HexColor(template.settings.get("section_color", "#E2E4E7"))
    y = 654
    for kind, value in entries:
        if kind == "heading":
            c.setFillColor(section)
            c.rect(x, y - 22, 276, 24, fill=1, stroke=1)
            draw_text(c, x + 5, y - 9, value.upper(), 265, bold, 8)
            if template.settings.get("show_english_subtitle", True):
                draw_text(c, x + 5, y - 19, ENGLISH.get(value, ""), 265, font, 6, accent)
            y -= 29
            continue
        item = value
        labels, values, tolerance, notes, height = row_layout(item, font, bold)
        c.setStrokeColor(colors.HexColor("#B7B7B7"))
        c.rect(x, y - height + 5, 276, height - 2)
        c.setFillColor(colors.black)
        c.setFont(font, 7)
        for index, line in enumerate(labels):
            c.drawString(x + 5, y - 10 - index * 10, line)
        c.setFillColor(accent)
        c.setFont(bold, 8)
        for index, line in enumerate(values):
            c.drawString(x + 152, y - 10 - index * 10, line)
        lower = max(len(labels), len(values))
        if tolerance:
            c.setFillColor(colors.black)
            c.setFont(font, 6)
            c.drawString(x + 152, y - 10 - lower * 10, tolerance)
        for index, line in enumerate(notes):
            c.setFillColor(colors.black)
            c.setFont(font, 6)
            c.drawString(x + 5, y - 10 - lower * 10 - (10 if tolerance else 0) - index * 9, line)
        y -= height
    return y


def generate_pdf(revision: Revision, template: PdfTemplate,
                 author_name: str, approver_name: str) -> bytes:
    font, bold = register_fonts()
    categories = {ALIASES.get(item.definition_category, item.definition_category) for item in revision.parameters}
    extras = sorted(categories - set(LEFT) - set(RIGHT) - {"Základní údaje"})
    left_pages = split_pages(entries_for(revision, LEFT), font, bold, capacity=515)
    right_pages = split_pages(entries_for(revision, RIGHT + extras), font, bold, capacity=515)
    count = max(len(left_pages), len(right_pages))
    stream = io.BytesIO()
    c = canvas.Canvas(stream, pagesize=letter)
    c.setTitle(f"Operační návodka - revize {revision.revision_number}")
    for index in range(count):
        draw_header(c, revision, template, font, bold, author_name, approver_name, index + 1, count)
        if index < len(left_pages):
            draw_column(c, left_pages[index], 26, template, font, bold)
        if index < len(right_pages):
            draw_column(c, right_pages[index], 310, template, font, bold)
        c.showPage()
    c.save()
    return stream.getvalue()
