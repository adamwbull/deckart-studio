from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QContextMenuEvent, QDragEnterEvent, QDragLeaveEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import QFrame, QLabel, QMenu, QVBoxLayout, QWidget

from deckart_studio.image_source import ImageSource
from deckart_studio.tts.card_face import CardFace
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.drag_mime import accepts_image_drop, sources_from_mime
from deckart_studio.ui.image_tile import elide
from deckart_studio.ui.thumbnail_box import ThumbnailBox

NAME_LABEL_HEIGHT = 34


class CardSlotWidget(QFrame):
    """One card's face in a deck view: click to pick art, or drop an image straight onto it."""

    clicked = Signal(int)
    designRequested = Signal(int)
    removeRequested = Signal(int)
    commanderRequested = Signal(int)
    moveRequested = Signal(int, int)
    imageDropped = Signal(int, ImageSource)

    def __init__(self, context: AppContext, card: CardFace, width: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self.card_index = card.index
        self._box = ThumbnailBox(context.thumbnails, width, self)
        self._name = QLabel(elide(card.nickname, 26), self)
        self._build_layout(width)
        self.refresh(card)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _build_layout(self, width: int) -> None:
        self._name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name.setWordWrap(True)
        self._name.setFixedHeight(NAME_LABEL_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        layout.addWidget(self._box)
        layout.addWidget(self._name)
        self.setFixedWidth(width + 8)
        self.setFrameShape(QFrame.Shape.StyledPanel)

    def set_card(self, card: CardFace) -> None:
        self.card_index = card.index
        self.refresh(card)

    def refresh(self, card: CardFace) -> None:
        self._box.set_key(self.context.session.face_source(card).display_key())
        self._name.setText(elide(card.nickname, 26))
        self.setToolTip(f"{card.nickname}\n{card.face_url}")

    def set_box_width(self, width: int) -> None:
        self._box.set_box_width(width)
        self.setFixedWidth(width + 8)

    def set_selected(self, selected: bool) -> None:
        self._box.set_highlighted(selected)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.card_index)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = QMenu(self)
        pick_action = menu.addAction("Pick art from gallery…")
        design_action = menu.addAction("Design full card face (Card Maker)…")
        menu.addSeparator()
        commander_action = self._add_commander_action(menu)
        move_actions = self._add_move_submenu(menu)
        remove_action = menu.addAction("Remove card from this stack")
        chosen = menu.exec(event.globalPos())
        if chosen is pick_action:
            self.clicked.emit(self.card_index)
        elif chosen is design_action:
            self.designRequested.emit(self.card_index)
        elif chosen is commander_action:
            self.commanderRequested.emit(self.card_index)
        elif chosen is remove_action:
            self.removeRequested.emit(self.card_index)
        elif chosen in move_actions:
            self.moveRequested.emit(self.card_index, move_actions[chosen])

    def _add_commander_action(self, menu: QMenu):
        board = self.context.session.active_board()
        action = menu.addAction("Set as commander (move to Commander stack)")
        action.setEnabled(board is not None and not board.is_commander)
        return action

    def _add_move_submenu(self, menu: QMenu) -> dict:
        session = self.context.session
        other_boards = [(index, name) for index, name in enumerate(session.board_names()) if index != session.active_board_index]
        submenu = menu.addMenu("Move to stack")
        submenu.setEnabled(bool(other_boards))
        return {submenu.addAction(name): index for index, name in other_boards}

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if accepts_image_drop(event.mimeData()):
            event.acceptProposedAction()
            self._box.set_highlighted(True)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._box.set_highlighted(False)

    def dropEvent(self, event: QDropEvent) -> None:
        self._box.set_highlighted(False)
        sources = sources_from_mime(event.mimeData())
        if sources:
            event.acceptProposedAction()
            self.imageDropped.emit(self.card_index, sources[0])
