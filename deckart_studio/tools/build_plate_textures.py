"""Crop head/body plate textures from M15 frame PNGs for Full Art overlays.

Run: .venv\\Scripts\\python.exe -m deckart_studio.tools.build_plate_textures
"""
import json
import sys
from pathlib import Path

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QImage

from deckart_studio.app_paths import resource_root
from deckart_studio.cardmaker.plate_geometry import CANVAS_WIDTH

ASSET_ROOT = resource_root() / "assets" / "cardmaker"

M15_ROOT = ASSET_ROOT / "templates" / "m15"
TEXTURES_ROOT = ASSET_ROOT / "textures"

HEAD_RECT = QRect(38, 34, 673, 64)
BODY_RECT = QRect(38, 690, 673, 262)

TEXTURE_SOURCES = [
    ("granite", "Granite", "artifact"),
    ("linen", "White linen", "white"),
    ("arcane", "Arcane blue", "blue"),
    ("void", "Void black", "black"),
    ("ember", "Ember red", "red"),
    ("grove", "Grove green", "green"),
    ("gilded", "Gilded gold", "gold"),
    ("colorless", "Colorless steel", "colorless"),
]


def build() -> None:
    TEXTURES_ROOT.mkdir(parents=True, exist_ok=True)
    catalog = [{"id": "smooth", "label": "Smooth gradient", "head": None, "body": None}]
    for texture_id, label, color_id in TEXTURE_SOURCES:
        frame_path = M15_ROOT / color_id / "frame.png"
        if not frame_path.exists():
            print("skip missing", frame_path)
            continue
        frame = QImage(str(frame_path))
        scale = frame.width() / CANVAS_WIDTH
        head = crop_scaled(frame, HEAD_RECT, scale)
        body = crop_scaled(frame, BODY_RECT, scale)
        head_name = f"{texture_id}-head.png"
        body_name = f"{texture_id}-body.png"
        head.save(str(TEXTURES_ROOT / head_name))
        body.save(str(TEXTURES_ROOT / body_name))
        catalog.append({"id": texture_id, "label": label, "head": head_name, "body": body_name})
        print("wrote", texture_id, head.size(), body.size())
    (TEXTURES_ROOT / "textures.json").write_text(json.dumps({"textures": catalog}, indent=2), encoding="utf-8")
    print("catalog:", len(catalog), "textures")


def crop_scaled(frame: QImage, target: QRect, scale: float) -> QImage:
    source = QRect(
        int(target.x() * scale),
        int(target.y() * scale),
        max(1, int(target.width() * scale)),
        max(1, int(target.height() * scale)),
    )
    cropped = frame.copy(source)
    if cropped.width() == target.width() and cropped.height() == target.height():
        return cropped
    return cropped.scaled(target.width(), target.height())


if __name__ == "__main__":
    application = QGuiApplication(sys.argv)
    build()
