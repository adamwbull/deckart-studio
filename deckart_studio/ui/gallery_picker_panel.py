from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from deckart_studio.gallery.gallery_library import GalleryImage, GallerySection
from deckart_studio.image_source import ImageSource
from deckart_studio.net import download_file
from deckart_studio.original_art.original_art import OriginalArt
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.drop_zone import DropZone
from deckart_studio.ui.grouped_image_browser import GroupedImageBrowser, ImageGroup
from deckart_studio.ui.image_tile_grid import ImageTileGrid
from deckart_studio.ui.workers import run_in_background

GALLERY_SECTIONS = (GallerySection.HANDPICKED, GallerySection.AI_RECOMMENDED)
GALLERY_TAB = 0
ORIGINAL_TAB = 1


class GalleryPickerPanel(QWidget):
    """Two picker pages: your own Gallery grouped by folder (default), and the card's Original printings."""

    sourceChosen = Signal(ImageSource)

    def __init__(self, context: AppContext, tile_width: int = 120, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self._card_name = ""
        self._tabs = QTabWidget(self)
        self._gallery = GroupedImageBrowser(context.thumbnails, tile_width)
        self._original = ImageTileGrid(context.thumbnails, tile_width)
        self._original_status = QLabel("Pick a card to see its official printings.")
        self._search_button = QPushButton("Fetch printings from Scryfall")
        self._build_layout()
        self._connect()
        self.reload_gallery()

    def _build_layout(self) -> None:
        self._tabs.addTab(self._gallery_page(), "Gallery")
        self._tabs.addTab(self._original_page(), "Original")
        self._tabs.setCurrentIndex(GALLERY_TAB)
        self._tabs.setCornerWidget(self._refresh_button(), Qt.Corner.TopRightCorner)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tabs)

    def _refresh_button(self) -> QPushButton:
        button = QPushButton("⟳ Refresh")
        button.setToolTip("Rescan the gallery folders and the original-art cache")
        button.clicked.connect(self.context.refresh_gallery)
        return button

    def _gallery_page(self) -> QWidget:
        page = QWidget()
        drop = DropZone("Drop photos or folders here to add them to the gallery")
        drop.pathsDropped.connect(self._on_gallery_paths_dropped)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(drop)
        layout.addWidget(self._gallery, 1)
        return page

    def _original_page(self) -> QWidget:
        page = QWidget()
        header = QHBoxLayout()
        header.addWidget(self._original_status, 1)
        header.addWidget(self._search_button)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(header)
        layout.addWidget(self._original, 1)
        return page

    def _connect(self) -> None:
        self._gallery.sourceActivated.connect(self.sourceChosen)
        self._original.sourceActivated.connect(self._on_original_activated)
        self._search_button.clicked.connect(self._search_scryfall)
        self.context.galleryChanged.connect(self.reload_gallery)

    def reload_gallery(self) -> None:
        images = [image for section in GALLERY_SECTIONS for image in self.context.gallery.images(section)]
        self._gallery.set_groups(group_gallery_images(images))
        self._tabs.setTabText(GALLERY_TAB, f"Gallery ({len(images)})")
        self.set_card_name(self._card_name)

    def set_card_name(self, card_name: str) -> None:
        self._card_name = card_name
        arts = self.context.original_index.find(card_name) if card_name else []
        self._original.set_sources([art.to_image_source() for art in arts])
        self._search_button.setEnabled(bool(card_name))
        self._original_status.setText(describe_original_results(card_name, len(arts)))

    def show_section(self, section: GallerySection) -> None:
        self._tabs.setCurrentIndex(ORIGINAL_TAB if section == GallerySection.ORIGINAL else GALLERY_TAB)

    def _on_gallery_paths_dropped(self, paths: list[Path]) -> None:
        added = self.context.register_dropped_paths(paths)
        self.context.session.statusMessage.emit(f"Added {added} gallery source(s)")

    def _on_original_activated(self, source: ImageSource) -> None:
        self.sourceChosen.emit(source)
        if source.local_path is None and source.remote_url:
            self._download_local_copy(source)

    def _download_local_copy(self, source: ImageSource) -> None:
        destination = self.context.downloaded_originals_folder() / filename_for_remote(source)
        run_in_background(lambda report: download_file(source.remote_url, destination),
                          lambda _result: self.context.refresh_gallery(),
                          lambda error: self.context.session.statusMessage.emit(f"Download failed: {error}"),
                          owner=self)

    def _search_scryfall(self) -> None:
        card_name = self._card_name
        self._original_status.setText(f"Searching Scryfall for “{card_name}”…")
        self._search_button.setEnabled(False)
        run_in_background(lambda report: self.context.scryfall.search_printings(card_name),
                          self._on_search_finished, self._on_search_failed, owner=self)

    def _on_search_finished(self, arts: object) -> None:
        printings: list[OriginalArt] = list(arts)
        known_urls = {art.image_url for art in self.context.original_index.find(self._card_name)}
        self._original.append_sources([art.to_image_source() for art in printings if art.image_url not in known_urls])
        self._original_status.setText(f"{len(printings)} printings found on Scryfall for “{self._card_name}”.")
        self._search_button.setEnabled(True)

    def _on_search_failed(self, error: str) -> None:
        self._original_status.setText(f"Scryfall search failed: {error.strip().splitlines()[-1]}")
        self._search_button.setEnabled(True)


def group_gallery_images(images: list[GalleryImage]) -> list[ImageGroup]:
    groups: dict[str, ImageGroup] = {}
    for image in images:
        groups.setdefault(image.group, ImageGroup(image.group)).sources.append(ImageSource.from_local(image.path, image.label))
    return list(groups.values())


def describe_original_results(card_name: str, count: int) -> str:
    if not card_name:
        return "Pick a card to see its official printings."
    if count == 0:
        return f"No local originals for “{card_name}” yet — fetch its printings from Scryfall."
    return f"{count} local original(s) for “{card_name}”."


def filename_for_remote(source: ImageSource) -> str:
    stem = "".join(character if character.isalnum() or character in "-_ " else "-" for character in source.label)
    suffix = Path(source.remote_url.split("?")[0]).suffix or ".jpg"
    return f"{'-'.join(stem.split()) or 'image'}{suffix}"
