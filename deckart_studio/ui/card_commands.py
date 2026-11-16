from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QInputDialog, QMenu, QMessageBox, QWidget

from deckart_studio.ui.deck_session import DeckSession


def confirm_delete_card(parent: QWidget, session: DeckSession, index: int) -> None:
    """Ask, then remove one card from the stack currently on screen."""
    card = session.card(index)
    board = session.active_board()
    if card is None or board is None:
        return
    answer = QMessageBox.question(
        parent,
        "Delete card",
        f"Delete “{card.nickname}” from {board.name}?\n\nSave the deck to keep this change.",
    )
    if answer == QMessageBox.StandardButton.Yes:
        session.remove_card(index)


def prompt_move_to_new_stack(parent: QWidget, session: DeckSession, index: int) -> None:
    """Name a stack, create it, and move this card into it."""
    card = session.card(index)
    if card is None:
        return
    name, accepted = QInputDialog.getText(parent, "Move to a new stack", "Stack name (e.g. Sideboard, Tokens):")
    if accepted and name.strip():
        session.move_card_to_new_board(index, name.strip())


def other_stacks(session: DeckSession) -> list[tuple[int, str]]:
    active = session.active_board_index
    return [(index, name) for index, name in enumerate(session.board_names()) if index != active]


def fill_move_menu(menu: QMenu, parent: QWidget, session: DeckSession, card_index: int) -> None:
    """Replace the menu with every other stack, plus a command that creates one."""
    menu.clear()
    for board_index, name in other_stacks(session):
        action = menu.addAction(name)
        action.triggered.connect(_later(_mover(session, card_index, board_index)))
    if menu.actions():
        menu.addSeparator()
    new_stack = menu.addAction("New stack…")
    new_stack.triggered.connect(_later(lambda: prompt_move_to_new_stack(parent, session, card_index)))


def _later(callback):
    def schedule(_checked: bool = False) -> None:
        QTimer.singleShot(0, callback)
    return schedule


def _mover(session: DeckSession, card_index: int, board_index: int):
    def move() -> None:
        session.move_card(card_index, board_index)
    return move
