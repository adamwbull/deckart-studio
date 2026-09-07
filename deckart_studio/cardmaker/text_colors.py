from PySide6.QtGui import QColor

from deckart_studio.cardmaker.card_design import CardDesign
from deckart_studio.cardmaker.card_template import CardTemplate
from deckart_studio.cardmaker.fullart_styles import plate_style

INK = "#141414"
PAPER = "#F4F1EA"
WHITE = "#FFFFFF"

TEXT_ROLES = ("title", "subtitle", "type", "rules", "pt", "artist", "legal")


def default_text_colors(template_style: str, plate_style_id: str) -> dict[str, str]:
    if template_style == "clear":
        return {role: WHITE for role in TEXT_ROLES}
    footer = WHITE
    body = PAPER if template_style == "fullart" and plate_style(plate_style_id).dark else INK
    return {
        "title": body,
        "subtitle": body,
        "type": body,
        "rules": body,
        "pt": INK,
        "artist": footer,
        "legal": footer,
    }


def default_hex_for(template: CardTemplate, design: CardDesign, role: str) -> str:
    return default_text_colors(template.style, design.plate_style_id)[role]


def resolved_text_color(design: CardDesign, template: CardTemplate, role: str) -> QColor:
    stored = getattr(design, f"{role}_color")
    color = QColor(stored) if stored else QColor()
    if color.isValid():
        return color
    return QColor(default_hex_for(template, design, role))


def hex_for_swatch(design: CardDesign, template: CardTemplate, role: str) -> str:
    return resolved_text_color(design, template, role).name()
