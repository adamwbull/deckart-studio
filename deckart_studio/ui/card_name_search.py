from PySide6.QtCore import QStringListModel, Qt, QTimer, Signal
from PySide6.QtWidgets import QCompleter, QHBoxLayout, QLineEdit, QPushButton, QWidget

from deckart_studio.original_art.scryfall_client import ScryfallClient
from deckart_studio.ui.workers import run_in_background

AUTOCOMPLETE_DEBOUNCE_MS = 250


class CardNameSearch(QWidget):
    """A search box with live Scryfall name suggestions; emits the chosen card name."""

    cardChosen = Signal(str)

    def __init__(self, scryfall: ScryfallClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.scryfall = scryfall
        self._suggestions = QStringListModel(self)
        self._input = QLineEdit()
        self._completer = QCompleter(self._suggestions, self)
        self._debounce = QTimer(self)
        self._latest_query = ""
        self._build()

    def _build(self) -> None:
        self._input.setPlaceholderText("Type a card name and press Enter to fill everything from Scryfall…")
        self._input.setClearButtonEnabled(True)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self._input.setCompleter(self._completer)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._fetch_suggestions)
        self._input.textEdited.connect(lambda _text: self._debounce.start(AUTOCOMPLETE_DEBOUNCE_MS))
        self._input.returnPressed.connect(self._choose_current_text)
        self._completer.activated.connect(self.cardChosen.emit)
        search_button = QPushButton("Look up")
        search_button.clicked.connect(self._choose_current_text)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._input, 1)
        layout.addWidget(search_button)

    def set_text(self, text: str) -> None:
        self._input.setText(text)

    def _fetch_suggestions(self) -> None:
        query = self._input.text().strip()
        self._latest_query = query
        run_in_background(lambda report: (query, self.scryfall.autocomplete(query)),
                          self._on_suggestions, lambda error: None, owner=self)

    def _on_suggestions(self, payload: object) -> None:
        query, names = payload
        if query != self._latest_query:
            return
        self._suggestions.setStringList(names)
        if names and self._input.hasFocus():
            self._completer.complete()

    def _choose_current_text(self) -> None:
        text = self._input.text().strip()
        if text:
            self.cardChosen.emit(text)
