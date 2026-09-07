import json
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QRect
from PySide6.QtGui import QImage

TEMPLATE_FILENAME = "template.json"


@dataclass
class FrameColor:
    id: str
    label: str
    frame: Path
    pt_box: Path | None
    legendary: Path | None


@dataclass
class CardTemplate:
    """One frame family (e.g. Modern) with its colors, masks, and text layout in canvas coordinates."""

    id: str
    name: str
    folder: Path
    canvas_width: int
    canvas_height: int
    frame_mask: Path | None
    colors: dict[str, FrameColor]
    layout: dict
    legendary_supported: bool = True
    style: str = "framed"
    _art_window: QRect | None = field(default=None, repr=False)

    def is_clear(self) -> bool:
        return self.style == "clear"

    def is_fullart(self) -> bool:
        return self.style == "fullart"

    @staticmethod
    def load(folder: Path) -> "CardTemplate":
        raw = json.loads((folder / TEMPLATE_FILENAME).read_text(encoding="utf-8"))
        canvas = raw.get("canvas", [749, 1044])
        return CardTemplate(
            id=raw.get("id", folder.name),
            name=raw.get("name", folder.name),
            folder=folder,
            canvas_width=int(canvas[0]),
            canvas_height=int(canvas[1]),
            frame_mask=optional_asset(folder, raw.get("frame_mask")),
            colors={color_id: frame_color(folder, color_id, entry) for color_id, entry in raw.get("colors", {}).items()},
            layout=raw.get("layout", {}),
            legendary_supported=bool(raw.get("legendary_supported", True)),
            style=raw.get("style", "framed"),
            _art_window=explicit_art_window(raw.get("art_window")),
        )

    def color(self, color_id: str) -> FrameColor:
        if color_id in self.colors:
            return self.colors[color_id]
        return next(iter(self.colors.values()))

    def color_ids(self) -> list[str]:
        return list(self.colors.keys())

    def art_window(self) -> QRect:
        if self._art_window is None:
            self._art_window = self._measure_art_window()
        return self._art_window

    def _measure_art_window(self) -> QRect:
        source = self.frame_mask or next(iter(self.colors.values())).frame
        window = transparent_bounding_box(QImage(str(source)), upper_fraction=0.65)
        return scale_rect(window, QImage(str(source)).size().width(), self.canvas_width)


def explicit_art_window(values: list | None) -> QRect | None:
    if not values or len(values) != 4:
        return None
    return QRect(*(int(value) for value in values))


def optional_asset(folder: Path, relative: str | None) -> Path | None:
    if not relative:
        return None
    path = folder / relative
    return path if path.exists() else None


def frame_color(folder: Path, color_id: str, entry: dict) -> FrameColor:
    return FrameColor(
        id=color_id,
        label=entry.get("label", color_id),
        frame=folder / entry["frame"],
        pt_box=optional_asset(folder, entry.get("pt")),
        legendary=optional_asset(folder, entry.get("legendary")),
    )


TRANSPARENT_ALPHA_LIMIT = 10
CORNER_INSET_FRACTION = 0.06


def transparent_bounding_box(image: QImage, upper_fraction: float) -> QRect:
    """Bounding box of transparent pixels inside the card border on the upper part of a frame: the art window."""
    alpha = image.convertToFormat(QImage.Format.Format_Alpha8)
    buffer = alpha.constBits()
    width, stride = alpha.width(), alpha.bytesPerLine()
    inset = int(width * CORNER_INSET_FRACTION)
    min_x, min_y, max_x, max_y = width, alpha.height(), -1, -1
    for y in range(inset, int(alpha.height() * upper_fraction)):
        row = bytes(buffer[y * stride + inset: y * stride + width - inset])
        columns = [x + inset for x, value in enumerate(row) if value < TRANSPARENT_ALPHA_LIMIT]
        if columns:
            min_x, max_x = min(min_x, columns[0]), max(max_x, columns[-1])
            min_y, max_y = min(min_y, y), max(max_y, y)
    if max_x < 0:
        return fallback_art_window(image)
    return QRect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)


def fallback_art_window(image: QImage) -> QRect:
    return QRect(int(image.width() * 0.08), int(image.height() * 0.11), int(image.width() * 0.84), int(image.height() * 0.44))


def scale_rect(rect: QRect, source_width: int, target_width: int) -> QRect:
    factor = target_width / source_width
    return QRect(round(rect.x() * factor), round(rect.y() * factor), round(rect.width() * factor), round(rect.height() * factor))


def discover_templates(templates_root: Path) -> list[CardTemplate]:
    templates = [CardTemplate.load(folder) for folder in sorted(Path(templates_root).iterdir())
                 if (folder / TEMPLATE_FILENAME).exists()]
    return templates
