from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from deckart_studio.image_source import ImageSource
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.drag_mime import accepts_image_drop, sources_from_mime
from deckart_studio.ui.gallery_picker_dialog import pick_card_back
from deckart_studio.ui.thumbnail_box import ThumbnailBox

BACK_THUMBNAIL_WIDTH = 46
TITLE_STYLE = "font-weight: bold;"
CAPTION_STYLE = "color: #888;"


class CardBackWidget(QFrame):
    """Shows the back image shared by the deck's cards; click or drop an image to change every back at once."""

    def __init__(self, context: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self._box = ThumbnailBox(context.thumbnails, BACK_THUMBNAIL_WIDTH, self)
        self._caption = QLabel()
        self._change_button = QPushButton("Change card back…")
        self._build()
        self._connect()
        self.refresh()

    def _build(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAcceptDrops(True)
        self.setToolTip("The back every card shows in TTS. Click the image or the button to pick a new one, "
                        "or drop an image here.")
        self._box.setCursor(Qt.CursorShape.PointingHandCursor)
        self._caption.setStyleSheet(CAPTION_STYLE)
        title = QLabel("Card back (all cards)")
        title.setStyleSheet(TITLE_STYLE)
        text_column = QVBoxLayout()
        text_column.setSpacing(2)
        text_column.addWidget(title)
        text_column.addWidget(self._caption)
        text_column.addWidget(self._change_button)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.addWidget(self._box)
        layout.addLayout(text_column)

    def _connect(self) -> None:
        self._change_button.clicked.connect(self.choose_back)
        self.context.session.backsChanged.connect(self.refresh)
        self.context.session.deckLoaded.connect(self.refresh)

    def refresh(self) -> None:
        source = self.context.session.common_back_source()
        self._box.set_key(source.display_key())
        self._caption.setText(elide_middle(source.label, 34) if not source.is_empty() else "No deck open")
        self._change_button.setEnabled(self.context.session.has_deck())

    def choose_back(self) -> None:
        if not self.context.session.has_deck():
            return
        chosen = pick_card_back(self.context, self)
        if chosen is not None:
            self.context.session.assign_all_backs(chosen)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._box.geometry().contains(event.pos()):
            self.choose_back()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self.context.session.has_deck() and accepts_image_drop(event.mimeData()):
            event.acceptProposedAction()
            self._box.set_highlighted(True)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._box.set_highlighted(False)

    def dropEvent(self, event: QDropEvent) -> None:
        self._box.set_highlighted(False)
        sources: list[ImageSource] = sources_from_mime(event.mimeData())
        if sources:
            event.acceptProposedAction()
            self.context.session.assign_all_backs(sources[0])


def elide_middle(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    keep = (limit - 1) // 2
    return f"{text[:keep]}…{text[-keep:]}"
