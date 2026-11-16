from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QMenu, QPushButton, QVBoxLayout, QWidget

from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.card_commands import confirm_delete_card, fill_move_menu
from deckart_studio.ui.styles import DESTRUCTIVE_BUTTON_STYLE, PRIMARY_BUTTON_STYLE


class CardCommandBar(QWidget):
    """The actions for the card shown in Focus: edit, move, copy, or delete it."""

    editRequested = Signal()

    def __init__(self, context: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self._index = -1
        self._edit = QPushButton("Edit in Card Maker…")
        self._move = QPushButton("Move to stack")
        self._commander = QPushButton("Set as commander")
        self._copy = QPushButton("Add a copy")
        self._delete = QPushButton("Delete card")
        self._move_menu = QMenu(self._move)
        self._build()
        self._connect()
        self.show_no_card()

    def show_card(self, index: int) -> None:
        self._index = index
        self._refresh_enabled()

    def show_no_card(self) -> None:
        self._index = -1
        self._refresh_enabled()

    def delete_current(self) -> None:
        if self.context.session.card(self._index) is not None:
            confirm_delete_card(self, self.context.session, self._index)

    def _build(self) -> None:
        self._edit.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self._edit.setToolTip("Redraw this card: frame, art, name, and rules text")
        self._move.setMenu(self._move_menu)
        self._move.setToolTip("Move this card into another stack, or create a stack for it")
        self._copy.setToolTip("Put another copy of this card in the current stack")
        self._delete.setStyleSheet(DESTRUCTIVE_BUTTON_STYLE)
        self._delete.setToolTip("Remove this card from the deck. The Delete key does this too.")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._edit)
        layout.addLayout(self._button_row(self._move, self._commander))
        layout.addLayout(self._button_row(self._copy, self._delete))

    def _button_row(self, left: QPushButton, right: QPushButton) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(left)
        row.addWidget(right)
        return row

    def _connect(self) -> None:
        self._edit.clicked.connect(self.editRequested.emit)
        self._commander.clicked.connect(self._make_commander)
        self._copy.clicked.connect(self._duplicate)
        self._delete.clicked.connect(self.delete_current)
        self._move_menu.aboutToShow.connect(self._fill_move_menu)

    def _fill_move_menu(self) -> None:
        fill_move_menu(self._move_menu, self, self.context.session, self._index)

    def _make_commander(self) -> None:
        if self.context.session.card(self._index) is not None:
            self.context.session.make_commander(self._index)

    def _duplicate(self) -> None:
        if self.context.session.card(self._index) is not None:
            self.context.session.duplicate_card(self._index)

    def _refresh_enabled(self) -> None:
        session = self.context.session
        board = session.active_board()
        has_card = session.card(self._index) is not None
        in_command_zone = board is not None and board.is_commander
        for button in (self._edit, self._move, self._copy, self._delete):
            button.setEnabled(has_card)
        self._commander.setEnabled(has_card and not in_command_zone)
        self._commander.setToolTip(self._commander_tip(in_command_zone))

    def _commander_tip(self, in_command_zone: bool) -> str:
        if in_command_zone:
            return "This card is already in the command zone."
        return "Move this card into the Commander stack. The stack is created if you don't have one."
