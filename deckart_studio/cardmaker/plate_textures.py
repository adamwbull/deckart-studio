import json
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QImage

from deckart_studio.app_paths import resource_root

TEXTURES_ROOT = resource_root() / "assets" / "cardmaker" / "textures"
CATALOG_FILE = TEXTURES_ROOT / "textures.json"


@dataclass(frozen=True)
class PlateTexture:
    id: str
    label: str
    head: Path | None
    body: Path | None

    def is_smooth(self) -> bool:
        return self.head is None and self.body is None


class PlateTextureLibrary:
    def __init__(self, root: Path = TEXTURES_ROOT):
        self.root = Path(root)
        self.textures: dict[str, PlateTexture] = {}
        self._image_cache: dict[Path, QImage] = {}

    def load(self) -> "PlateTextureLibrary":
        raw = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
        self.textures = {}
        for entry in raw.get("textures", []):
            texture = PlateTexture(
                id=entry["id"],
                label=entry.get("label", entry["id"]),
                head=optional_texture_file(self.root, entry.get("head")),
                body=optional_texture_file(self.root, entry.get("body")),
            )
            self.textures[texture.id] = texture
        if "smooth" not in self.textures:
            self.textures["smooth"] = PlateTexture("smooth", "Smooth gradient", None, None)
        return self

    def list(self) -> list[PlateTexture]:
        return list(self.textures.values())

    def get(self, texture_id: str) -> PlateTexture:
        if texture_id in self.textures:
            return self.textures[texture_id]
        return self.textures["smooth"]

    def image(self, path: Path | None) -> QImage | None:
        if path is None:
            return None
        if path not in self._image_cache:
            self._image_cache[path] = QImage(str(path))
        image = self._image_cache[path]
        return None if image.isNull() else image


def optional_texture_file(root: Path, relative: str | None) -> Path | None:
    if not relative:
        return None
    path = root / relative
    return path if path.exists() else None
