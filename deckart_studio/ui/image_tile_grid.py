from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from deckart_studio.gallery.thumbnail_loader import ThumbnailLoader
from deckart_studio.image_source import ImageSource
from deckart_studio.ui.flow_layout import FlowLayout
from deckart_studio.ui.image_tile import ImageTile

MAX_TILES_RENDERED = 1500


class ImageTileGrid(QWidget):
    """A filterable, scrolling flow of ImageTiles built from a list of ImageSources."""

    sourceActivated = Signal(ImageSource)

    def __init__(self, loader: ThumbnailLoader, tile_width: int = 120, parent: QWidget | None = None):
        super().__init__(parent)
        self._loader = loader
        self._tile_width = tile_width
        self._sources: list[ImageSource] = []
        self._filter = QLineEdit(self)
        self._status = QLabel(self)
        self._flow_host = QWidget()
        self._flow = FlowLayout(self._flow_host)
        self._build_layout()
        self._filter.textChanged.connect(self._rebuild)

    def _build_layout(self) -> None:
        self._filter.setPlaceholderText("Filter by file name…")
        self._filter.setClearButtonEnabled(True)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._flow_host)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._filter)
        layout.addWidget(scroll, 1)
        layout.addWidget(self._status)

    def set_sources(self, sources: list[ImageSource]) -> None:
        self._sources = list(sources)
        self._rebuild()

    def append_sources(self, sources: list[ImageSource]) -> None:
        self.set_sources(self._sources + list(sources))

    def set_tile_width(self, width: int) -> None:
        self._tile_width = width
        self._rebuild()

    def _rebuild(self) -> None:
        self._flow.clear_widgets()
        visible = [source for source in self._sources if self._matches_filter(source)]
        for source in visible[:MAX_TILES_RENDERED]:
            self._add_tile(source)
        self._status.setText(describe_count(len(visible), len(self._sources)))

    def _add_tile(self, source: ImageSource) -> None:
        tile = ImageTile(source, self._loader, self._tile_width, self._flow_host)
        tile.activated.connect(self.sourceActivated)
        self._flow.addWidget(tile)

    def _matches_filter(self, source: ImageSource) -> bool:
        needle = self._filter.text().strip().lower()
        return not needle or needle in source.label.lower() or needle in source.display_key().lower()


def describe_count(visible: int, total: int) -> str:
    shown = min(visible, MAX_TILES_RENDERED)
    if visible == total:
        return f"{shown} images"
    return f"{shown} of {total} images match"
