from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from deckart_studio.gemini.image_client import GeminiImageClient, model_choices
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.styles import PRIMARY_BUTTON_STYLE
from deckart_studio.ui.workers import run_in_background

PREVIEW_WIDTH = 280


class AiArtPanel(QWidget):
    """Generate Gemini card art and save it to the gallery AI folder immediately."""

    artGenerated = Signal(str)
    openSettingsRequested = Signal()

    def __init__(self, context: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self._card_name = ""
        self._type_line = ""
        self._model = QComboBox()
        self._style = QComboBox()
        self._style.setEditable(False)
        self._prompt = QPlainTextEdit()
        self._status = QLabel()
        self._preview = QLabel()
        self._generate = QPushButton("Generate art")
        self._build()

    def _build(self) -> None:
        self._prompt.setPlaceholderText("Describe the scene. This is added to the shared card-art instructions.")
        self._prompt.setMinimumHeight(140)
        self._status.setWordWrap(True)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(200)
        self._generate.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self._generate.clicked.connect(self._generate_art)
        heading = QLabel("Gemini art")
        heading.setStyleSheet("font-weight: bold; font-size: 15px;")
        hint = QLabel("Every generate is saved to DeckArt/generated_ai and shows up under AI Recommended, even if you do not save the card.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addLayout(self._form())
        layout.addWidget(self._generate)
        layout.addWidget(self._status)
        layout.addWidget(self._preview, 1)
        layout.addWidget(hint)
        self.reload_from_settings()

    def _form(self) -> QFormLayout:
        add_style = QPushButton("Add style…")
        add_style.clicked.connect(self._add_style)
        style_row = QWidget()
        style_layout = QHBoxLayout(style_row)
        style_layout.setContentsMargins(0, 0, 0, 0)
        style_layout.addWidget(self._style, 1)
        style_layout.addWidget(add_style)
        settings_link = QPushButton("Settings…")
        settings_link.clicked.connect(self.openSettingsRequested.emit)
        form = QFormLayout()
        form.addRow("Model", self._model)
        form.addRow("Art style", style_row)
        form.addRow("Prompt", self._prompt)
        form.addRow("", settings_link)
        return form

    def set_card_context(self, card_name: str, type_line: str) -> None:
        self._card_name = card_name
        self._type_line = type_line

    def reload_from_settings(self) -> None:
        settings = self.context.settings
        self._model.blockSignals(True)
        self._model.clear()
        for label, model_id in model_choices():
            self._model.addItem(label, model_id)
        self._model.setCurrentIndex(max(0, self._model.findData(settings.gemini_model_id)))
        self._model.blockSignals(False)
        self._refresh_styles()
        if settings.gemini_api_key.strip():
            self._status.setText("Ready. Generated images go to the AI gallery folder immediately.")
        else:
            self._status.setText("Add a Gemini API key in Settings to generate art here.")

    def _refresh_styles(self) -> None:
        settings = self.context.settings
        self._style.blockSignals(True)
        self._style.clear()
        for style in settings.art_styles:
            self._style.addItem(style)
        index = self._style.findText(settings.last_art_style)
        self._style.setCurrentIndex(index if index >= 0 else 0)
        self._style.blockSignals(False)

    def _add_style(self) -> None:
        style, accepted = QInputDialog.getText(self, "Add art style", "Style name")
        name = style.strip()
        if not accepted or not name:
            return
        if name not in self.context.settings.art_styles:
            self.context.settings.art_styles.append(name)
        self.context.settings.last_art_style = name
        self.context.settings.save()
        self._refresh_styles()

    def _generate_art(self) -> None:
        settings = self.context.settings
        settings.gemini_model_id = self._model.currentData() or settings.gemini_model_id
        settings.last_art_style = self._style.currentText()
        settings.save()
        if not settings.gemini_api_key.strip():
            self._status.setText("Add a Gemini API key in Settings first.")
            self.openSettingsRequested.emit()
            return
        self._generate.setEnabled(False)
        self._status.setText("Generating with Gemini…")
        style = self._style.currentText()
        prompt = self._prompt.toPlainText()
        card_name, type_line = self._card_name, self._type_line
        run_in_background(
            lambda report: GeminiImageClient().generate_card_art(settings, style, prompt, card_name, type_line),
            self._on_generated,
            self._on_failed,
            owner=self,
        )

    def _on_generated(self, result: object) -> None:
        self._generate.setEnabled(True)
        path = Path(result.path)
        self.context.refresh_gallery()
        self._show_preview(path)
        self._status.setText(f"Saved {path.name} to the AI gallery folder.")
        self.artGenerated.emit(str(path))

    def _on_failed(self, error: str) -> None:
        self._generate.setEnabled(True)
        message = error.splitlines()[-1] if error else "Generation failed."
        if "GeminiImageError" in message:
            message = message.split("GeminiImageError: ", 1)[-1]
        self._status.setText(message)

    def _show_preview(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return
        self._preview.setPixmap(pixmap.scaledToWidth(PREVIEW_WIDTH, Qt.TransformationMode.SmoothTransformation))
