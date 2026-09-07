from dataclasses import dataclass

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainterPath

DEFAULT_PLATE_STYLE = "bars"


@dataclass(frozen=True)
class PlateStyle:
    id: str
    label: str
    dark: bool


PLATE_STYLES = (
    PlateStyle("bars", "Classic bars", False),
    PlateStyle("mantle", "Cabinet mantle", True),
    PlateStyle("banner", "Banner", True),
    PlateStyle("plaque", "Carved plaque", True),
    PlateStyle("arch", "Arch", True),
    PlateStyle("inlay", "Inlay frame", False),
)


FRAME_TINTS = {
    "white": QColor(232, 220, 186),
    "whiteLand": QColor(220, 205, 160),
    "blue": QColor(62, 102, 168),
    "blueLand": QColor(72, 118, 168),
    "black": QColor(48, 42, 50),
    "blackLand": QColor(44, 40, 46),
    "red": QColor(168, 58, 48),
    "redLand": QColor(160, 68, 46),
    "green": QColor(52, 108, 58),
    "greenLand": QColor(64, 112, 52),
    "gold": QColor(188, 148, 52),
    "goldLand": QColor(176, 140, 50),
    "colorless": QColor(154, 150, 146),
    "colorlessLand": QColor(142, 136, 126),
    "artifact": QColor(132, 138, 144),
    "vehicle": QColor(96, 72, 50),
    "oldArtifact": QColor(132, 138, 144),
    "oldGold": QColor(188, 148, 52),
    "oldGoldLand": QColor(176, 140, 50),
}


def plate_style(style_id: str) -> PlateStyle:
    for style in PLATE_STYLES:
        if style.id == style_id:
            return style
    return PLATE_STYLES[0]


def plate_style_list() -> tuple[PlateStyle, ...]:
    return PLATE_STYLES


def tint_for_frame_color(color_id: str) -> QColor:
    return QColor(FRAME_TINTS.get(color_id, FRAME_TINTS["colorless"]))


def style_path(style_id: str, kind: str, rect: QRectF) -> QPainterPath:
    builders = PATH_BUILDERS.get(style_id, PATH_BUILDERS[DEFAULT_PLATE_STYLE])
    return builders.get(kind, rounded_bar)(rect)


def style_layers(style_id: str, kind: str, rect: QRectF) -> list[QPainterPath]:
    if style_id == "mantle" and kind == "title":
        return [mantle_cornice(rect), rounded_bar(rect)]
    return [style_path(style_id, kind, rect)]


def rounded_rect_path(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def rounded_bar(rect: QRectF) -> QPainterPath:
    return rounded_rect_path(rect, 10.0)


def inlay_bar(rect: QRectF) -> QPainterPath:
    return rounded_rect_path(rect.adjusted(3, 2, -3, -2), 8.0)


def mantle_title(rect: QRectF) -> QPainterPath:
    return rounded_bar(rect)


def mantle_cornice(rect: QRectF) -> QPainterPath:
    cap = QRectF(rect.left() + 6, rect.top() - 8, rect.width() - 12, 12)
    return rounded_rect_path(cap, 4.0)


def mantle_band(rect: QRectF) -> QPainterPath:
    return rounded_bar(rect)


def chamfered_bar(rect: QRectF, cut: float = 14.0) -> QPainterPath:
    rise = cut * 0.55
    path = QPainterPath()
    path.moveTo(rect.left() + cut, rect.top())
    path.lineTo(rect.right() - cut, rect.top())
    path.lineTo(rect.right(), rect.top() + rise)
    path.lineTo(rect.right(), rect.bottom() - rise)
    path.lineTo(rect.right() - cut, rect.bottom())
    path.lineTo(rect.left() + cut, rect.bottom())
    path.lineTo(rect.left(), rect.bottom() - rise)
    path.lineTo(rect.left(), rect.top() + rise)
    path.closeSubpath()
    return path


def flared_bar(rect: QRectF, flare: float = 20.0) -> QPainterPath:
    mid_y = rect.center().y()
    path = QPainterPath()
    path.moveTo(rect.left() - flare, mid_y)
    path.quadTo(rect.left() + 4, rect.top() - 3, rect.left() + 30, rect.top())
    path.lineTo(rect.right() - 30, rect.top())
    path.quadTo(rect.right() - 4, rect.top() - 3, rect.right() + flare, mid_y)
    path.quadTo(rect.right() - 4, rect.bottom() + 3, rect.right() - 30, rect.bottom())
    path.lineTo(rect.left() + 30, rect.bottom())
    path.quadTo(rect.left() + 4, rect.bottom() + 3, rect.left() - flare, mid_y)
    path.closeSubpath()
    return path


def banner_bar(rect: QRectF) -> QPainterPath:
    tip = 22.0
    path = QPainterPath()
    path.moveTo(rect.left(), rect.top())
    path.lineTo(rect.right(), rect.top())
    path.lineTo(rect.right() + tip, rect.center().y())
    path.lineTo(rect.right(), rect.bottom())
    path.lineTo(rect.left(), rect.bottom())
    path.lineTo(rect.left() - tip, rect.center().y())
    path.closeSubpath()
    return path


def banner_text(rect: QRectF) -> QPainterPath:
    return rounded_rect_path(rect, 8.0)


def plaque_bar(rect: QRectF) -> QPainterPath:
    step = 11.0
    path = QPainterPath()
    path.moveTo(rect.left() + step, rect.top())
    path.lineTo(rect.right() - step, rect.top())
    path.lineTo(rect.right(), rect.top() + step)
    path.lineTo(rect.right(), rect.bottom() - step)
    path.lineTo(rect.right() - step, rect.bottom())
    path.lineTo(rect.left() + step, rect.bottom())
    path.lineTo(rect.left(), rect.bottom() - step)
    path.lineTo(rect.left(), rect.top() + step)
    path.closeSubpath()
    return path


def plaque_text(rect: QRectF) -> QPainterPath:
    return plaque_bar(rect.adjusted(0, 0, 0, 0))


def arch_title(rect: QRectF) -> QPainterPath:
    return single_arch(rect, 14.0)


def arch_band(rect: QRectF) -> QPainterPath:
    return single_arch(rect, 8.0)


def single_arch(rect: QRectF, rise: float) -> QPainterPath:
    left, right = rect.left(), rect.right()
    top, bottom = rect.top(), rect.bottom()
    path = QPainterPath()
    path.moveTo(left + 10, bottom)
    path.lineTo(right - 10, bottom)
    path.quadTo(right, bottom, right, bottom - 10)
    path.lineTo(right, top + 18)
    path.quadTo(rect.center().x(), top - rise, left, top + 18)
    path.lineTo(left, bottom - 10)
    path.quadTo(left, bottom, left + 10, bottom)
    path.closeSubpath()
    return path


PATH_BUILDERS = {
    "bars": {"title": rounded_bar, "subtitle": rounded_bar, "type": rounded_bar, "text": rounded_bar},
    "mantle": {"title": mantle_title, "subtitle": mantle_band, "type": mantle_band, "text": rounded_bar},
    "banner": {"title": banner_bar, "subtitle": banner_bar, "type": banner_bar, "text": banner_text},
    "plaque": {"title": plaque_bar, "subtitle": plaque_bar, "type": plaque_bar, "text": plaque_text},
    "arch": {"title": arch_title, "subtitle": arch_band, "type": arch_band, "text": rounded_bar},
    "inlay": {"title": inlay_bar, "subtitle": inlay_bar, "type": inlay_bar, "text": inlay_bar},
}
