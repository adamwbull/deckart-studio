from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QListWidget, QPushButton, QVBoxLayout, QWidget,
)

from deckart_studio.gallery.gallery_library import GallerySection
from deckart_studio.image_source import ImageSource
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.drop_zone import DropZone
from deckart_studio.ui.image_tile_grid import ImageTileGrid

SECTION_CHOICES = {
    "Gallery": (GallerySection.HANDPICKED, GallerySection.AI_RECOMMENDED),
    "Original": (GallerySection.ORIGINAL,),
}


class GalleryDock(QWidget):
    """Persistent gallery: register photo sources by dropping them, then drag tiles onto cards."""

    def __init__(self, context: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self._section = QComboBox()
        self._sources_list = QListWidget()
        self._grid = ImageTileGrid(context.thumbnails, tile_width=100)
        self._build_layout()
        self._connect()
        self.reload()

    def _build_layout(self) -> None:
        drop = DropZone("Drop photos or whole folders here to register them in the gallery")
        drop.pathsDropped.connect(self._on_paths_dropped)
        self._section.addItems(list(SECTION_CHOICES))
        self._sources_list.setMaximumHeight(110)
        layout = QVBoxLayout(self)
        layout.addWidget(drop)
        layout.addLayout(self._source_buttons())
        layout.addWidget(self._sources_list)
        layout.addWidget(self._section)
        layout.addWidget(self._grid, 1)

    def _source_buttons(self) -> QHBoxLayout:
        add_folder = QPushButton("Add folder…")
        add_files = QPushButton("Add photos…")
        remove = QPushButton("Remove selected source")
        rescan = QPushButton("Rescan")
        add_folder.clicked.connect(self._choose_folder)
        add_files.clicked.connect(self._choose_files)
        remove.clicked.connect(self._remove_selected_source)
        rescan.clicked.connect(self.context.refresh_gallery)
        row = QHBoxLayout()
        for button in (add_folder, add_files, remove, rescan):
            row.addWidget(button)
        return row

    def _connect(self) -> None:
        self._section.currentIndexChanged.connect(lambda _index: self._reload_grid())
        self.context.galleryChanged.connect(self.reload)

    def reload(self) -> None:
        self._sources_list.clear()
        self._sources_list.addItems(self.context.settings.gallery_sources())
        self._reload_grid()

    def _reload_grid(self) -> None:
        sections = SECTION_CHOICES[self._section.currentText()]
        images = [image for section in sections for image in self.context.gallery.images(section)]
        self._grid.set_sources([ImageSource.from_local(image.path, image.label) for image in images])

    def _on_paths_dropped(self, paths: list[Path]) -> None:
        added = self.context.register_dropped_paths(paths)
        self.context.session.statusMessage.emit(f"Registered {added} new gallery source(s)")

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Add gallery folder")
        if folder:
            self._on_paths_dropped([Path(folder)])

    def _choose_files(self) -> None:
        files, _filter = QFileDialog.getOpenFileNames(self, "Add photos", "", "Images (*.jpg *.jpeg *.png *.webp *.bmp *.gif)")
        if files:
            self._on_paths_dropped([Path(file) for file in files])

    def _remove_selected_source(self) -> None:
        item = self._sources_list.currentItem()
        if item is not None:
            self.context.remove_gallery_source(item.text())
