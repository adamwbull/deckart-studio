from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import QLabel, QWidget

from deckart_studio.image_source import ImageSource
from deckart_studio.ui.drag_mime import accepts_image_drop, local_paths_from_mime, sources_from_mime

IDLE_STYLE = "QLabel { border: 2px dashed #6c7a89; border-radius: 8px; padding: 10px; color: #c9d1d9; }"
ACTIVE_STYLE = "QLabel { border: 2px solid #5aaaff; border-radius: 8px; padding: 10px; color: #ffffff; background: #223; }"


class DropZone(QLabel):
    """A labelled target that accepts image files, folders, gallery tiles, or URLs dropped onto it."""

    sourcesDropped = Signal(list)
    pathsDropped = Signal(list)

    def __init__(self, caption: str, parent: QWidget | None = None):
        super().__init__(caption, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setAcceptDrops(True)
        self.setStyleSheet(IDLE_STYLE)
        self.setMinimumHeight(56)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if accepts_image_drop(event.mimeData()):
            event.acceptProposedAction()
            self.setStyleSheet(ACTIVE_STYLE)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.setStyleSheet(IDLE_STYLE)

    def dropEvent(self, event: QDropEvent) -> None:
        self.setStyleSheet(IDLE_STYLE)
        event.acceptProposedAction()
        sources: list[ImageSource] = sources_from_mime(event.mimeData())
        paths: list[Path] = local_paths_from_mime(event.mimeData())
        if sources:
            self.sourcesDropped.emit(sources)
        if paths:
            self.pathsDropped.emit(paths)
