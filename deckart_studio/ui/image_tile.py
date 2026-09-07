from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout, QWidget

from deckart_studio.gallery.thumbnail_loader import ThumbnailLoader
from deckart_studio.image_source import ImageSource
from deckart_studio.ui.drag_mime import mime_for_source
from deckart_studio.ui.thumbnail_box import ThumbnailBox

CAPTION_HEIGHT = 34


class ImageTile(QFrame):
    """A draggable gallery thumbnail; clicking it offers the image to whatever is listening."""

    activated = Signal(ImageSource)

    def __init__(self, source: ImageSource, loader: ThumbnailLoader, width: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.source = source
        self._press_position: QPoint | None = None
        self._box = ThumbnailBox(loader, width, self)
        self._box.set_key(source.display_key())
        self._caption = QLabel(elide(source.label, 24), self)
        self._build_layout(width)
        self.setToolTip(source.display_key())
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _build_layout(self, width: int) -> None:
        self._caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._caption.setWordWrap(True)
        self._caption.setFixedHeight(CAPTION_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        layout.addWidget(self._box)
        layout.addWidget(self._caption)
        self.setFixedWidth(width + 8)
        self.setFrameShape(QFrame.Shape.StyledPanel)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_position = event.position().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_position is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if (event.position().toPoint() - self._press_position).manhattanLength() >= QApplication.startDragDistance():
            self._start_drag()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._press_position is not None and event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self.source)
        self._press_position = None

    def _start_drag(self) -> None:
        self._press_position = None
        drag = QDrag(self)
        drag.setMimeData(mime_for_source(self.source))
        pixmap = self._box.current_pixmap()
        if pixmap is not None and not pixmap.isNull():
            drag.setPixmap(pixmap.scaledToWidth(90, Qt.TransformationMode.SmoothTransformation))
        drag.exec(Qt.DropAction.CopyAction)


def elide(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
