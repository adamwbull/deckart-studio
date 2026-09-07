"""Build full-card plate texture sheets so title, type, and text share one aligned pattern.

Run: .venv\\Scripts\\python.exe -m deckart_studio.tools.build_plate_textures
"""
import json
import random
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen

from deckart_studio.app_paths import resource_root
from deckart_studio.cardmaker.plate_geometry import CANVAS_HEIGHT, CANVAS_WIDTH

TEXTURES_ROOT = resource_root() / "assets" / "cardmaker" / "textures"
TEXTURE_SPECS = [
    ("stone", "Stone", QColor(186, 184, 178), QColor(148, 146, 140), QColor(214, 212, 206), 11),
    ("granite", "Granite", QColor(168, 166, 162), QColor(110, 108, 104), QColor(208, 206, 202), 17),
    ("parchment", "Parchment", QColor(214, 204, 184), QColor(176, 160, 132), QColor(236, 228, 210), 13),
    ("linen", "Linen", QColor(206, 200, 190), QColor(172, 166, 156), QColor(230, 226, 218), 19),
    ("slate", "Slate", QColor(92, 96, 102), QColor(58, 62, 68), QColor(132, 136, 142), 23),
    ("frost", "Frost", QColor(176, 190, 206), QColor(128, 150, 176), QColor(220, 228, 236), 29),
    ("ember", "Ember", QColor(176, 132, 118), QColor(132, 86, 74), QColor(214, 176, 156), 31),
    ("grove", "Grove", QColor(150, 164, 142), QColor(102, 122, 96), QColor(196, 206, 178), 37),
    ("gilded", "Gilded", QColor(196, 176, 128), QColor(148, 124, 78), QColor(230, 214, 168), 41),
]


def build() -> None:
    TEXTURES_ROOT.mkdir(parents=True, exist_ok=True)
    remove_legacy_crops()
    catalog = [{"id": "smooth", "label": "Smooth", "sheet": None}]
    for texture_id, label, base, dark, light, seed in TEXTURE_SPECS:
        sheet = stone_sheet(CANVAS_WIDTH, CANVAS_HEIGHT, base, dark, light, seed)
        if texture_id == "linen":
            weave_over(sheet, dark, light, seed)
        filename = f"{texture_id}.png"
        sheet.save(str(TEXTURES_ROOT / filename))
        catalog.append({"id": texture_id, "label": label, "sheet": filename})
        print("wrote", texture_id, sheet.size())
    (TEXTURES_ROOT / "textures.json").write_text(json.dumps({"textures": catalog}, indent=2), encoding="utf-8")
    print("catalog:", len(catalog), "textures")


def remove_legacy_crops() -> None:
    for path in TEXTURES_ROOT.glob("*-head.png"):
        path.unlink()
    for path in TEXTURES_ROOT.glob("*-body.png"):
        path.unlink()


def stone_sheet(width: int, height: int, base: QColor, dark: QColor, light: QColor, seed: int) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(base)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    rng = random.Random(seed)
    paint_mottle(painter, width, height, base, dark, light, rng)
    paint_veins(painter, width, height, dark, rng)
    painter.end()
    return image


def paint_mottle(painter: QPainter, width: int, height: int, base: QColor, dark: QColor,
                 light: QColor, rng: random.Random) -> None:
    for _ in range(420):
        blend = light if rng.random() < 0.55 else dark
        color = mix_color(base, blend, rng.uniform(0.08, 0.28))
        color.setAlpha(rng.randint(18, 46))
        painter.setBrush(color)
        painter.drawEllipse(
            int(rng.randint(-50, width)),
            int(rng.randint(-50, height)),
            int(rng.randint(50, 200)),
            int(rng.randint(28, 110)),
        )


def paint_veins(painter: QPainter, width: int, height: int, dark: QColor, rng: random.Random) -> None:
    for _ in range(16):
        color = QColor(dark)
        color.setAlpha(rng.randint(18, 36))
        painter.setPen(QPen(color, rng.uniform(0.8, 1.6)))
        path = QPainterPath()
        x, y = rng.uniform(0, width), rng.uniform(0, height)
        path.moveTo(x, y)
        for _step in range(7):
            x += rng.uniform(-90, 90)
            y += rng.uniform(-50, 50)
            path.lineTo(x, y)
        painter.drawPath(path)


def weave_over(image: QImage, dark: QColor, light: QColor, seed: int) -> None:
    painter = QPainter(image)
    step = 4
    for x in range(0, image.width(), step):
        color = QColor(dark if x // step % 2 == 0 else light)
        color.setAlpha(18)
        painter.setPen(QPen(color, 1))
        painter.drawLine(x, 0, x, image.height())
    for y in range(0, image.height(), step):
        color = QColor(dark if y // step % 2 == 0 else light)
        color.setAlpha(14)
        painter.setPen(QPen(color, 1))
        painter.drawLine(0, y, image.width(), y)
    painter.end()


def mix_color(left: QColor, right: QColor, amount: float) -> QColor:
    return QColor(
        int(left.red() + (right.red() - left.red()) * amount),
        int(left.green() + (right.green() - left.green()) * amount),
        int(left.blue() + (right.blue() - left.blue()) * amount),
    )


if __name__ == "__main__":
    application = QGuiApplication(sys.argv)
    build()
