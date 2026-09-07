from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget,
)

from deckart_studio.moxfield.deck_importer import DeckImporter, ImportResult
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.workers import run_in_background

INSTRUCTIONS = (
    "Paste a Moxfield deck link (e.g. https://moxfield.com/decks/N64gEdLjQkmWuIHGit6dMQ) "
    "or paste a deck list (one card per line, like “1 The Tenth Doctor (WHO) 163”)."
)


class ImportDeckDialog(QDialog):
    """Collects a Moxfield URL or deck list, builds a TTS saved object, and reports where it landed."""

    def __init__(self, context: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self.result_path: Path | None = None
        self._result: ImportResult | None = None
        self.setWindowTitle("Import deck into Saved Objects")
        self.resize(640, 460)
        self._input = QPlainTextEdit()
        self._name_override = QLineEdit()
        self._status = QLabel("Ready.")
        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._build_layout()

    def _build_layout(self) -> None:
        instructions = QLabel(INSTRUCTIONS)
        instructions.setWordWrap(True)
        self._input.setPlaceholderText("https://moxfield.com/decks/…  or  1 Sol Ring\n1 Command Tower\n…")
        self._name_override.setPlaceholderText("Optional: override the saved deck name")
        self._status.setWordWrap(True)
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Import")
        self._buttons.accepted.connect(self._start_import)
        self._buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(instructions)
        layout.addWidget(self._input, 1)
        layout.addWidget(self._name_override)
        layout.addWidget(self._status)
        layout.addWidget(self._buttons)

    def _start_import(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            self._status.setText("Paste a Moxfield link or a deck list first.")
            return
        self._buttons.setEnabled(False)
        importer = DeckImporter(Path(self.context.settings.saved_objects_folder), self.context.scryfall)
        name_override = self._name_override.text()
        run_in_background(lambda report: importer.import_text(text, name_override, report),
                          self._on_import_finished, self._on_import_failed, self._status.setText, owner=self)

    def result_face_url(self) -> str:
        return self._result.first_face_url if self._result else ""

    def _on_import_finished(self, outcome: object) -> None:
        result: ImportResult = outcome
        self._result = result
        self.result_path = result.saved_path
        self._status.setText(summarize(result))
        self.accept()

    def _on_import_failed(self, error: str) -> None:
        self._status.setText(f"Import failed:\n{error.strip().splitlines()[-1]}")
        self._buttons.setEnabled(True)


def summarize(result: ImportResult) -> str:
    unresolved = f" Unresolved: {', '.join(result.unresolved)}" if result.unresolved else ""
    stacks = f" Stacks — {result.stack_summary}." if result.stack_summary else ""
    return f"Imported “{result.deck_name}” with {result.card_count} cards → {result.saved_path.name}.{stacks}{unresolved}"
