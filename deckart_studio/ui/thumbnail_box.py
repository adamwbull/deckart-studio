from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from deckart_studio.gallery.thumbnail_loader import ThumbnailLoader, keys_match

CARD_ASPECT_RATIO = 7 / 5


class ThumbnailBox(QWidget):
    """Paints one image key (file path or URL) scaled to fit, loading lazily through the ThumbnailLoader."""

    def __init__(self, loader: ThumbnailLoader, width: int, parent: QWidget | None = None,
                 aspect_ratio: float = CARD_ASPECT_RATIO):
        super().__init__(parent)
        self._loader = loader
        self._key = ""
        self._aspect_ratio = aspect_ratio
        self._highlighted = False
        self.set_box_width(width)
        loader.thumbnailReady.connect(self._on_thumbnail_ready)
        loader.keyInvalidated.connect(self._on_key_invalidated)

    def set_box_width(self, width: int) -> None:
        self.setFixedSize(QSize(width, int(width * self._aspect_ratio)))
        self.update()

    def request_size(self) -> int:
        return max(self.width(), self.height())

    def set_key(self, key: str) -> None:
        if key != self._key:
            self._key = key
            self.update()

    def key(self) -> str:
        return self._key

    def set_highlighted(self, highlighted: bool) -> None:
        self._highlighted = highlighted
        self.update()

    def current_pixmap(self) -> QPixmap | None:
        return self._loader.request(self._key, self.request_size()) if self._key else None

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor(30, 30, 34))
        pixmap = self.current_pixmap()
        if pixmap is not None and not pixmap.isNull():
            painter.drawPixmap(centered_fit_rect(pixmap.size(), self.rect()), pixmap)
        else:
            self._paint_placeholder(painter)
        if self._highlighted:
            painter.setPen(QPen(QColor(90, 170, 255), 3))
            painter.drawRect(self.rect().adjusted(1, 1, -2, -2))

    def _paint_placeholder(self, painter: QPainter) -> None:
        painter.setPen(QColor(110, 110, 120))
        message = "no image" if not self._key else "loading…"
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, message)

    def _on_thumbnail_ready(self, key: str, size: int) -> None:
        if key == self._key and size == self.request_size():
            self.update()

    def _on_key_invalidated(self, key: str) -> None:
        if keys_match(key, self._key):
            self.update()


def centered_fit_rect(image_size: QSize, box: QRect) -> QRect:
    fitted = image_size.scaled(box.size(), Qt.AspectRatioMode.KeepAspectRatio)
    left = box.x() + (box.width() - fitted.width()) // 2
    top = box.y() + (box.height() - fitted.height()) // 2
    return QRect(left, top, fitted.width(), fitted.height())
