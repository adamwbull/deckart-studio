"""Generate the Clear Art template: full-bleed art with no plates, just outlined text later painted by the renderer.

Run from the project root:  .venv\\Scripts\\python.exe -m deckart_studio.tools.build_clearart_template
"""
import json
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage

from deckart_studio.cardmaker.asset_library import ASSET_ROOT

SOURCE_TEMPLATE = ASSET_ROOT / "templates" / "m15"
TARGET_TEMPLATE = ASSET_ROOT / "templates" / "clearart"
CANVAS_WIDTH, CANVAS_HEIGHT = 749, 1044
LAYOUT = {
    "title": {"x": 48, "y": 42, "font": "Beleren Bold", "size": 40, "spacing": 0.15},
    "subtitle": {"x": 48, "y": 86, "font": "Beleren Bold", "size": 22, "spacing": 0.08},
    "mana": {"right_x": 701, "y": 44, "radius": 17.5, "step": 31},
    "type": {"x": 48, "y": 638, "font": "Beleren Bold", "size": 28, "spacing": 0.05},
    "text": {"x": 48, "y": 688, "width": 653, "height": 248, "font": "MPlantin", "max_size": 30, "min_size": 16},
    "pt": {"box": [575, 924, 137, 75], "text_center_x": 680, "text_y": 948, "font": "Beleren Bold", "size": 42},
    "artist": {"x": 48, "y": 992, "font": "Matrix Bold Small Caps", "size": 22, "color": "white"},
    "legal": {"x": 48, "y": 1014, "font": "MPlantin", "size": 16, "color": "white"},
}


def build() -> None:
    source = json.loads((SOURCE_TEMPLATE / "template.json").read_text(encoding="utf-8"))
    if TARGET_TEMPLATE.exists():
        shutil.rmtree(TARGET_TEMPLATE)
    TARGET_TEMPLATE.mkdir(parents=True)
    transparent = QImage(CANVAS_WIDTH, CANVAS_HEIGHT, QImage.Format.Format_ARGB32_Premultiplied)
    transparent.fill(Qt.GlobalColor.transparent)
    transparent.save(str(TARGET_TEMPLATE / "frame.png"))
    colors = {color_id: {"label": entry["label"], "frame": "frame.png"} for color_id, entry in source["colors"].items()}
    (TARGET_TEMPLATE / "template.json").write_text(json.dumps(clearart_template_json(colors), indent=2), encoding="utf-8")
    print("clearart template written with", len(colors), "colors")


def clearart_template_json(colors: dict) -> dict:
    return {
        "id": "clearart",
        "name": "Clear Art",
        "style": "clear",
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
