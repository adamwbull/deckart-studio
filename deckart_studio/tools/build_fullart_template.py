"""Generate the Full Art template: art covers the whole card; slim tinted plates float over it for name/type/rules.

Plate colors are sampled from the M15 frames so every M15 color has a Full Art twin.
Run from the project root:  .venv\\Scripts\\python.exe -m deckart_studio.tools.build_fullart_template
"""
import json
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPen

from deckart_studio.cardmaker.asset_library import ASSET_ROOT

SOURCE_TEMPLATE = ASSET_ROOT / "templates" / "m15"
TARGET_TEMPLATE = ASSET_ROOT / "templates" / "fullart"
CANVAS_WIDTH, CANVAS_HEIGHT = 749, 1044
PLATE_LEFT, PLATE_RIGHT = 38, 711
TITLE_PLATE = QRectF(PLATE_LEFT, 34, PLATE_RIGHT - PLATE_LEFT, 64)
TYPE_PLATE = QRectF(PLATE_LEFT, 632, PLATE_RIGHT - PLATE_LEFT, 50)
TEXT_PLATE = QRectF(PLATE_LEFT, 690, PLATE_RIGHT - PLATE_LEFT, 262)
BOTTOM_FADE_TOP = 955
TITLE_BAR_SAMPLE = QPointF(0.5, 40 / 523)
TEXT_BOX_SAMPLE = QPointF(0.5, 400 / 523)
BAR_OPACITY = 0.94
TEXT_BOX_OPACITY = 0.90
SHADOW_ALPHA = 120
LAYOUT = {
    "title": {"x": 58, "y": 44, "font": "Beleren Bold", "size": 38, "spacing": 0.15},
    "mana": {"right_x": 697, "y": 48, "radius": 17.5, "step": 39},
    "type": {"x": 58, "y": 641, "font": "Beleren Bold", "size": 30, "spacing": 0.05},
    "text": {"x": 56, "y": 700, "width": 637, "height": 244, "font": "MPlantin", "max_size": 30, "min_size": 16},
    "pt": {"box": [575, 924, 137, 75], "text_center_x": 649, "text_y": 931, "font": "Beleren Bold", "size": 39},
    "artist": {"x": 106, "y": 990, "font": "Matrix Bold Small Caps", "size": 24, "color": "white", "brush": [80, 995]},
    "legal": {"x": 48, "y": 1012, "font": "MPlantin", "size": 17, "color": "white"},
}


def build() -> None:
    source = json.loads((SOURCE_TEMPLATE / "template.json").read_text(encoding="utf-8"))
    if TARGET_TEMPLATE.exists():
        shutil.rmtree(TARGET_TEMPLATE)
    TARGET_TEMPLATE.mkdir(parents=True)
    colors = {color_id: build_color(color_id, entry) for color_id, entry in source["colors"].items()}
    (TARGET_TEMPLATE / "template.json").write_text(json.dumps(fullart_template_json(colors), indent=2), encoding="utf-8")
    print("fullart template written with", len(colors), "colors")


def build_color(color_id: str, entry: dict) -> dict:
    color_dir = TARGET_TEMPLATE / color_id
    color_dir.mkdir(parents=True, exist_ok=True)
    source_frame = QImage(str(SOURCE_TEMPLATE / entry["frame"]))
    bar_color = sample(source_frame, TITLE_BAR_SAMPLE)
    box_color = sample(source_frame, TEXT_BOX_SAMPLE)
    fullart_frame(bar_color, box_color).save(str(color_dir / "frame.png"))
    shutil.copy2(SOURCE_TEMPLATE / entry["pt"], color_dir / "pt.png")
    return {"label": entry["label"], "frame": f"{color_id}/frame.png", "pt": f"{color_id}/pt.png"}


def sample(image: QImage, relative_point: QPointF) -> QColor:
    return image.pixelColor(int(relative_point.x() * (image.width() - 1)), int(relative_point.y() * (image.height() - 1)))


def fullart_frame(bar_color: QColor, box_color: QColor) -> QImage:
    frame = QImage(CANVAS_WIDTH, CANVAS_HEIGHT, QImage.Format.Format_ARGB32_Premultiplied)
    frame.fill(Qt.GlobalColor.transparent)
    painter = QPainter(frame)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw_bottom_fade(painter)
    draw_plate(painter, TITLE_PLATE, bar_color, radius=16, opacity=BAR_OPACITY)
    draw_plate(painter, TYPE_PLATE, bar_color, radius=12, opacity=BAR_OPACITY)
    draw_plate(painter, TEXT_PLATE, box_color, radius=14, opacity=TEXT_BOX_OPACITY)
    painter.end()
    return frame


def draw_bottom_fade(painter: QPainter) -> None:
    gradient = QLinearGradient(0, BOTTOM_FADE_TOP, 0, CANVAS_HEIGHT)
    gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
    gradient.setColorAt(1.0, QColor(0, 0, 0, 210))
    painter.fillRect(QRectF(0, BOTTOM_FADE_TOP, CANVAS_WIDTH, CANVAS_HEIGHT - BOTTOM_FADE_TOP), gradient)


def draw_plate(painter: QPainter, rect: QRectF, base: QColor, radius: float, opacity: float) -> None:
    draw_plate_shadow(painter, rect, radius)
    painter.setPen(QPen(with_alpha(base.darker(180), opacity), 3))
    painter.setBrush(plate_gradient(rect, base, opacity))
    painter.drawRoundedRect(rect, radius, radius)
    painter.setPen(QPen(QColor(255, 255, 255, 80), 1.5))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), radius - 2, radius - 2)


def draw_plate_shadow(painter: QPainter, rect: QRectF, radius: float) -> None:
    painter.setPen(Qt.PenStyle.NoPen)
    for spread, alpha in ((6, SHADOW_ALPHA // 4), (3, SHADOW_ALPHA // 2), (0, SHADOW_ALPHA)):
        painter.setBrush(QColor(0, 0, 0, alpha))
        painter.drawRoundedRect(rect.adjusted(-spread, -spread, spread, spread).translated(0, 4), radius + spread, radius + spread)


def plate_gradient(rect: QRectF, base: QColor, opacity: float) -> QLinearGradient:
    gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    gradient.setColorAt(0.0, with_alpha(base.lighter(118), opacity))
    gradient.setColorAt(1.0, with_alpha(base.darker(106), opacity))
    return gradient


def with_alpha(color: QColor, opacity: float) -> QColor:
    result = QColor(color)
    result.setAlphaF(opacity)
    return result


def fullart_template_json(colors: dict) -> dict:
    return {
        "id": "fullart",
        "name": "Full Art",
        "canvas": [CANVAS_WIDTH, CANVAS_HEIGHT],
        "frame_mask": None,
        "art_window": [0, 0, CANVAS_WIDTH, CANVAS_HEIGHT],
        "colors": colors,
        "layout": LAYOUT,
        "legendary_supported": False,
    }


if __name__ == "__main__":
    application = QGuiApplication(sys.argv)
    build()
