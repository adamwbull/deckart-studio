import json
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QImage

from deckart_studio.app_paths import resource_root

TEXTURES_ROOT = resource_root() / "assets" / "cardmaker" / "textures"
CATALOG_FILE = TEXTURES_ROOT / "textures.json"
LEGACY_TEXTURE_IDS = {
    "arcane": "alabaster",
    "frost": "alabaster",
    "void": "slate",
    "colorless": "stone",
    "linen": "plaster",
    "ember": "leather",
    "grove": "wood",
    "gilded": "steel",
}


@dataclass(frozen=True)
class PlateTexture:
    id: str
    label: str
    sheet: Path | None

    def is_smooth(self) -> bool:
        return self.sheet is None


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
                sheet=optional_texture_file(self.root, entry.get("sheet") or entry.get("head")),
            )
            self.textures[texture.id] = texture
        if "smooth" not in self.textures:
            self.textures["smooth"] = PlateTexture("smooth", "Smooth", None)
        return self

    def list(self) -> list[PlateTexture]:
        return list(self.textures.values())

    def get(self, texture_id: str) -> PlateTexture:
        resolved = LEGACY_TEXTURE_IDS.get(texture_id, texture_id)
        if resolved in self.textures:
            return self.textures[resolved]
        if "stone" in self.textures:
            return self.textures["stone"]
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
