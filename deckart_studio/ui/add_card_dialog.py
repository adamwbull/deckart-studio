from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget

from deckart_studio.moxfield.deck_importer import built_card_from_scryfall
from deckart_studio.tts.object_factory import BuiltCard
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.card_name_search import CardNameSearch
from deckart_studio.ui.styles import PRIMARY_BUTTON_STYLE
from deckart_studio.ui.workers import run_in_background

MAX_COPIES = 99


class AddCardDialog(QDialog):
    """Look a card up on Scryfall and add one or more copies of it to the stack being viewed."""

    def __init__(self, context: AppContext, stack_name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self._search = CardNameSearch(context.scryfall)
        self._quantity = QSpinBox()
        self._status = QLabel()
        self._found: BuiltCard | None = None
        self._add_button = QPushButton("Add to stack")
        self.setWindowTitle(f"Add card to {stack_name}")
        self.resize(560, 220)
        self._build(stack_name)

    def _build(self, stack_name: str) -> None:
        self._quantity.setRange(1, MAX_COPIES)
        self._status.setWordWrap(True)
        self._add_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self._add_button.setEnabled(False)
        self._add_button.clicked.connect(self._add)
        self._search.cardChosen.connect(self._lookup)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Search Scryfall for a card, then add it to <b>{stack_name}</b>."))
        layout.addLayout(self._form())
        layout.addWidget(self._status)
        layout.addStretch(1)
        layout.addLayout(self._button_row())

    def _form(self) -> QFormLayout:
        form = QFormLayout()
        form.addRow("Card name", self._search)
        form.addRow("Copies", self._quantity)
        return form

    def _button_row(self) -> QHBoxLayout:
        cancel = QPushButton("Close")
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(self._add_button)
        return row

    def _lookup(self, name: str) -> None:
        self._found = None
        self._add_button.setEnabled(False)
        self._status.setText(f"Looking up “{name}”…")
        run_in_background(lambda report: built_card_from_scryfall(self.context.scryfall.named(name)),
                          self._on_found, self._on_lookup_failed, owner=self)

    def _on_found(self, built: object) -> None:
        if built is None:
            self._status.setText("Scryfall returned a card with no printable face.")
            return
        self._found = built
        self._status.setText(f"Found <b>{built.name}</b>\n{built.description.splitlines()[0] if built.description else ''}")
        self._add_button.setEnabled(True)
        self._add_button.setFocus()

    def _on_lookup_failed(self, error: str) -> None:
        self._status.setText(f"Not found: {error}")

    def _add(self) -> None:
        if self._found is None:
            return
        self.context.session.add_cards(self._found, self._quantity.value())
        self._status.setText(f"Added {self._quantity.value()}× {self._found.name}. Search again or close.")
        self._search.set_text("")


def add_card_to_active_stack(context: AppContext, parent: QWidget | None) -> None:
    board = context.session.active_board()
    if board is not None:
        AddCardDialog(context, board.name, parent).exec()
