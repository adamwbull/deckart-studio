from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QImage

from deckart_studio.app_paths import resource_root
from deckart_studio.cardmaker.card_template import CardTemplate, discover_templates
from deckart_studio.cardmaker.plate_textures import PlateTextureLibrary
from deckart_studio.cardmaker.symbols import SymbolLibrary

ASSET_ROOT = resource_root() / "assets" / "cardmaker"

LOGICAL_FONTS = {
    "Beleren Bold": ("Beleren", QFont.Weight.Bold, False),
    "Beleren Small Caps": ("Beleren Small Caps", QFont.Weight.Bold, False),
    "Matrix Bold": ("Matrix", QFont.Weight.Bold, False),
    "Matrix Bold Small Caps": ("MatrixBoldSmallCaps", QFont.Weight.Normal, False),
    "MPlantin": ("MPlantin", QFont.Weight.Normal, False),
    "MPlantin Italic": ("MPlantin", QFont.Weight.Normal, True),
    "Relay": ("Relay", QFont.Weight.Medium, False),
}


class CardAssetLibrary:
    """Loads templates, fonts, symbols, and shared images from the card maker asset folder once."""

    def __init__(self, root: Path = ASSET_ROOT):
        self.root = Path(root)
        self.templates: dict[str, CardTemplate] = {}
        self.symbols = SymbolLibrary(self.root / "symbols")
        self.plate_textures = PlateTextureLibrary().load()
        self._image_cache: dict[Path, QImage] = {}
        self._fonts_registered = False

    def load(self) -> "CardAssetLibrary":
        self.templates = {template.id: template for template in discover_templates(self.root / "templates")}
        self._register_fonts()
        return self

    def template(self, template_id: str) -> CardTemplate:
        if template_id in self.templates:
            return self.templates[template_id]
        return next(iter(self.templates.values()))

    def template_list(self) -> list[CardTemplate]:
        return list(self.templates.values())

    def image(self, path: Path | None) -> QImage | None:
        if path is None:
            return None
        if path not in self._image_cache:
            self._image_cache[path] = QImage(str(path))
        return self._image_cache[path]

    def symbol_image(self, token_body: str) -> QImage | None:
        return self.image(self.symbols.image_path(token_body))

    def artist_brush(self) -> QImage | None:
        return self.image(self.root / "misc" / "artistBrush.png")

    def card_mask(self) -> QImage | None:
        return self.image(self.root / "misc" / "cardMask.png")

    def font(self, logical_name: str, pixel_size: float, italic: bool = False) -> QFont:
        family, weight, italic_default = LOGICAL_FONTS.get(logical_name, (logical_name, QFont.Weight.Normal, False))
        font = QFont(family)
        font.setWeight(weight)
        font.setItalic(italic or italic_default)
        font.setPixelSize(max(1, round(pixel_size)))
        return font

    def _register_fonts(self) -> None:
        if self._fonts_registered:
            return
        for font_file in sorted((self.root / "fonts").glob("*.ttf")):
            QFontDatabase.addApplicationFont(str(font_file))
        self._fonts_registered = True
