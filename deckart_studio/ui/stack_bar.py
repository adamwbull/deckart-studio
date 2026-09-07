from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton, QWidget

from deckart_studio.tts.board import Board
from deckart_studio.ui.action_bar import hint_label
from deckart_studio.ui.add_card_dialog import add_card_to_active_stack
from deckart_studio.ui.app_context import AppContext

STACK_LABEL_STYLE = "font-weight: bold;"


class StackBar(QFrame):
    """Chooses which stack (main deck, sideboard, tokens…) the views show, and adds/removes cards or stacks."""

    def __init__(self, context: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self._stacks = QComboBox()
        self._count = QLabel()
        self._add_card = QPushButton("+ Add card…")
        self._new_stack = QPushButton("+ New stack…")
        self._rename = QPushButton("Rename…")
        self._delete = QPushButton("Delete stack")
        self._build()
        self._connect()
        self.refresh()

    def _build(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._stacks.setMinimumWidth(260)
        self._stacks.setToolTip("Each stack spawns as its own pile in Tabletop Simulator. The first stack is your main deck.")
        self._add_card.setToolTip("Look a card up on Scryfall and add copies of it to this stack")
        self._new_stack.setToolTip("Create another pile, e.g. Sideboard or Tokens")
        self._delete.setToolTip("Remove this stack and every card in it")
        title = QLabel("Stack:")
        title.setStyleSheet(STACK_LABEL_STYLE)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.addWidget(title)
        layout.addWidget(self._stacks)
        layout.addWidget(self._count)
        layout.addSpacing(16)
        layout.addWidget(self._add_card)
        layout.addWidget(self._new_stack)
        layout.addWidget(self._rename)
        layout.addWidget(self._delete)
        layout.addStretch(1)
        layout.addWidget(hint_label("Right-click a card to set it as commander, move it to another stack, or remove it."))

    def _connect(self) -> None:
        self._stacks.activated.connect(self.context.session.set_active_board)
        self._add_card.clicked.connect(lambda: add_card_to_active_stack(self.context, self))
        self._new_stack.clicked.connect(self._create_stack)
        self._rename.clicked.connect(self._rename_stack)
        self._delete.clicked.connect(self._delete_stack)
        self.context.session.boardsChanged.connect(self.refresh)
        self.context.session.cardsReset.connect(self.refresh)

    def refresh(self) -> None:
        session = self.context.session
        self._stacks.blockSignals(True)
        self._stacks.clear()
        self._stacks.addItems([describe_board(board, index == 0) for index, board in enumerate(session.boards())])
        self._stacks.setCurrentIndex(session.active_board_index)
        self._stacks.blockSignals(False)
        self._refresh_buttons()

    def _refresh_buttons(self) -> None:
        board = self.context.session.active_board()
        has_deck = self.context.session.has_deck()
        self._count.setText(f"{board.card_count()} cards" if board else "")
        self._stacks.setEnabled(board is not None)
        self._add_card.setEnabled(board is not None)
        self._new_stack.setEnabled(has_deck)
        self._rename.setEnabled(board is not None and not board.is_loose)
        self._delete.setEnabled(board is not None)

    def _create_stack(self) -> None:
        name, accepted = QInputDialog.getText(self, "New stack", "Stack name (e.g. Sideboard, Tokens):")
        if accepted and name.strip():
            self.context.session.add_board(name)

    def _rename_stack(self) -> None:
        board = self.context.session.active_board()
        if board is None:
            return
        name, accepted = QInputDialog.getText(self, "Rename stack", "Stack name:", text=board.name)
        if accepted and name.strip():
            self.context.session.rename_active_board(name)

    def _delete_stack(self) -> None:
        board = self.context.session.active_board()
        if board is None:
            return
        answer = QMessageBox.question(self, "Delete stack",
                                      f"Remove “{board.name}” and its {board.card_count()} card(s) from this save?")
        if answer == QMessageBox.StandardButton.Yes:
            self.context.session.delete_active_board()


def describe_board(board: Board, is_main: bool) -> str:
    suffix = "  (main deck)" if is_main else "  (command zone)" if board.is_commander else ""
    return f"{board.name} — {board.card_count()}{suffix}"
