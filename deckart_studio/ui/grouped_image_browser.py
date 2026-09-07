from dataclasses import dataclass, field

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QLineEdit, QScrollArea, QToolButton, QVBoxLayout, QWidget

from deckart_studio.gallery.thumbnail_loader import ThumbnailLoader
from deckart_studio.image_source import ImageSource
from deckart_studio.ui.flow_layout import FlowLayout
from deckart_studio.ui.image_tile import ImageTile

MAX_TILES_RENDERED = 1500
HEADER_STYLE = ("QToolButton { font-size: 14px; font-weight: bold; padding: 6px 4px; color: #e6edf3; border: none; "
                "text-align: left; } QToolButton:hover { color: #ffffff; }")


@dataclass
class ImageGroup:
    """A folder's worth of gallery images, shown under one collapsible heading."""

    name: str
    sources: list[ImageSource] = field(default_factory=list)


class GroupedImageBrowser(QWidget):
    """Gallery images grouped by folder, each group sorted by name, with one search box across all of them."""

    sourceActivated = Signal(ImageSource)

    def __init__(self, loader: ThumbnailLoader, tile_width: int = 120, parent: QWidget | None = None):
        super().__init__(parent)
        self._loader = loader
        self._tile_width = tile_width
        self._groups: list[ImageGroup] = []
        self._collapsed: set[str] = set()
        self._filter = QLineEdit(self)
        self._status = QLabel(self)
        self._sections_host = QWidget()
        self._sections_layout = QVBoxLayout(self._sections_host)
        self._build_layout()
        self._filter.textChanged.connect(self._rebuild)

    def _build_layout(self) -> None:
        self._filter.setPlaceholderText("Search all folders by file or folder name…")
        self._filter.setClearButtonEnabled(True)
        self._sections_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._sections_layout.setContentsMargins(0, 0, 0, 0)
        self._sections_layout.setSpacing(0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._sections_host)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._filter)
        layout.addWidget(scroll, 1)
        layout.addWidget(self._status)

    def set_groups(self, groups: list[ImageGroup]) -> None:
        self._groups = sorted((ImageGroup(group.name, sorted(group.sources, key=source_sort_key)) for group in groups),
                              key=lambda group: group.name.lower())
        self._rebuild()

    def set_tile_width(self, width: int) -> None:
        self._tile_width = width
        self._rebuild()

    def total_count(self) -> int:
        return sum(len(group.sources) for group in self._groups)

    def _rebuild(self) -> None:
        self._clear_sections()
        needle = self._filter.text().strip().lower()
        budget = MAX_TILES_RENDERED
        shown = 0
        for group in self._groups:
            matching = [source for source in group.sources if matches(needle, group.name, source)]
            if matching:
                self._add_section(group.name, matching[:budget])
                budget -= min(len(matching), budget)
                shown += len(matching)
        self._sections_layout.addStretch(1)
        self._status.setText(describe_count(shown, self.total_count()))

    def _clear_sections(self) -> None:
        while self._sections_layout.count():
            item = self._sections_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _add_section(self, name: str, sources: list[ImageSource]) -> None:
        flow_host = QWidget(self._sections_host)
        flow = FlowLayout(flow_host)
        for source in sources:
            flow.addWidget(self._tile(source, flow_host))
        flow_host.setVisible(name not in self._collapsed)
        self._sections_layout.addWidget(self._header(name, len(sources), flow_host))
        self._sections_layout.addWidget(flow_host)

    def _header(self, name: str, count: int, body: QWidget) -> QToolButton:
        header = QToolButton(self._sections_host)
        header.setStyleSheet(HEADER_STYLE)
        header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        header.setArrowType(Qt.ArrowType.RightArrow if name in self._collapsed else Qt.ArrowType.DownArrow)
        header.setText(f"{name}  ({count})")
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.clicked.connect(lambda: self._toggle_group(name, header, body))
        return header

    def _toggle_group(self, name: str, header: QToolButton, body: QWidget) -> None:
        collapsed = name not in self._collapsed
        self._collapsed.symmetric_difference_update({name})
        body.setVisible(not collapsed)
        header.setArrowType(Qt.ArrowType.RightArrow if collapsed else Qt.ArrowType.DownArrow)

    def _tile(self, source: ImageSource, parent: QWidget) -> ImageTile:
        tile = ImageTile(source, self._loader, self._tile_width, parent)
        tile.activated.connect(self.sourceActivated)
        return tile


def source_sort_key(source: ImageSource) -> str:
    return source.label.lower()


def matches(needle: str, group_name: str, source: ImageSource) -> bool:
    return not needle or needle in source.label.lower() or needle in group_name.lower()


def describe_count(shown: int, total: int) -> str:
    if shown == total:
        return f"{total} images"
    return f"{min(shown, MAX_TILES_RENDERED)} of {total} images match"
