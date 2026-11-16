from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QPlainTextEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from deckart_studio.gemini.image_client import CardArtContext, GeminiImageClient, model_choices
from deckart_studio.prompt_library import prompt_source_name, prompt_text_for, save_card_prompt
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.styles import PRIMARY_BUTTON_STYLE
from deckart_studio.ui.workers import run_in_background

PREVIEW_WIDTH = 280
PROMPT_SAVE_DELAY_MS = 400


class PromptEdit(QPlainTextEdit):
    """Gemini scene box that always pastes clipboard text, including HTML-only copies."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)
        self.setUndoRedoEnabled(True)
        self.setTabChangesFocus(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

    def canInsertFromMimeData(self, source) -> bool:
        return bool(source and (source.hasText() or source.hasHtml() or super().canInsertFromMimeData(source)))

    def insertFromMimeData(self, source) -> None:
        text = mime_plain_text(source)
        if text:
            self.insertPlainText(text)
            return
        super().insertFromMimeData(source)

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Paste):
            self.paste()
            event.accept()
            return
        super().keyPressEvent(event)

    def paste(self) -> None:
        text = QApplication.clipboard().text()
        if text:
            self.insertPlainText(text)
            return
        super().paste()


def mime_plain_text(source) -> str:
    if source is None:
        return ""
    text = source.text()
    if text:
        return text
    html = source.html() if source.hasHtml() else ""
    return html


class AiArtPanel(QWidget):
    """Generate Gemini card art and save it to the gallery AI folder immediately."""

    artGenerated = Signal(str)
    openSettingsRequested = Signal()

    def __init__(self, context: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self._card = CardArtContext()
        self._model = QComboBox()
        self._style = QComboBox()
        self._style.setEditable(False)
        self._prompt = PromptEdit()
        self._status = QLabel()
        self._preview = QLabel()
        self._generate = QPushButton("Generate art")
        self._loading_prompt = False
        self._saved_prompt = ""
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(PROMPT_SAVE_DELAY_MS)
        self._build()

    def _build(self) -> None:
        self._prompt.setPlaceholderText(
            "Describe the scene, or paste one. Matching cards load from *prompt*.txt in the Prompt folder.")
        self._prompt.setMinimumHeight(180)
        self._status.setWordWrap(True)
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(200)
        self._generate.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self._generate.clicked.connect(self._generate_art)
        self._save_timer.timeout.connect(self._save_prompt_now)
        self._prompt.textChanged.connect(self._schedule_prompt_save)
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
        self._style.currentTextChanged.connect(self._persist_style)
        self._model.currentIndexChanged.connect(self._persist_model)

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
        paste = QPushButton("Paste")
        paste.clicked.connect(self._prompt.paste)
        reload_prompt = QPushButton("Load from file")
        reload_prompt.clicked.connect(self._fill_saved_prompt)
        prompt_buttons = QWidget()
        button_row = QHBoxLayout(prompt_buttons)
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.addWidget(paste)
        button_row.addWidget(reload_prompt)
        button_row.addStretch(1)
        prompt_block = QWidget()
        prompt_layout = QVBoxLayout(prompt_block)
        prompt_layout.setContentsMargins(0, 0, 0, 0)
        prompt_layout.addWidget(prompt_buttons)
        prompt_layout.addWidget(self._prompt)
        form = QFormLayout()
        form.addRow("Model", self._model)
        form.addRow("Art style", style_row)
        form.addRow("Prompt", prompt_block)
        form.addRow("", settings_link)
        return form

    def set_card_context(self, card: CardArtContext) -> None:
        names_changed = card.true_name != self._card.true_name or card.display_name != self._card.display_name
        if names_changed:
            self._save_prompt_now()
        self._card = card
        if names_changed:
            self._fill_saved_prompt()

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
        self._fill_saved_prompt()

    def _fill_saved_prompt(self) -> None:
        folder = Path(self.context.settings.prompt_folder)
        text = prompt_text_for(folder, self._card.true_name, self._card.display_name)
        if not text:
            self._loading_prompt = True
            self._prompt.clear()
            self._loading_prompt = False
            self._saved_prompt = ""
            source = prompt_source_name(folder)
            if source:
                self._status.setText(f"No prompt for this card in {source}.")
            return
        self._loading_prompt = True
        self._prompt.setPlainText(text)
        self._loading_prompt = False
        self._saved_prompt = text
        source = prompt_source_name(folder)
        self._status.setText(f"Loaded prompt from {source}." if source else "Loaded saved prompt.")

    def _refresh_styles(self) -> None:
        settings = self.context.settings
        self._style.blockSignals(True)
        self._style.clear()
        for style in settings.art_styles:
            self._style.addItem(style)
        index = self._style.findText(settings.last_art_style)
        self._style.setCurrentIndex(index if index >= 0 else 0)
        self._style.blockSignals(False)

    def _schedule_prompt_save(self) -> None:
        if self._loading_prompt:
            return
        self._save_timer.start()

    def _save_prompt_now(self) -> None:
        self._save_timer.stop()
        prompt = " ".join(self._prompt.toPlainText().split())
        if not prompt or prompt == self._saved_prompt:
            return
        if not (self._card.true_name.strip() or self._card.display_name.strip()):
            return
        try:
            path = save_card_prompt(
                Path(self.context.settings.prompt_folder),
                [self._card.true_name, self._card.display_name],
                prompt,
                self._card.display_name,
                self._card.true_name,
            )
        except (OSError, ValueError) as error:
            self._status.setText(f"Could not save prompt: {error}")
            return
        self._saved_prompt = prompt
        self._status.setText(f"Saved prompt to {path.name}.")

    def hideEvent(self, event) -> None:
        self._save_prompt_now()
        super().hideEvent(event)

    def _persist_style(self, style: str) -> None:
        if not style:
            return
        self.context.settings.last_art_style = style
        self.context.settings.save()

    def _persist_model(self) -> None:
        model_id = self._model.currentData()
        if not model_id:
            return
        self.context.settings.gemini_model_id = model_id
        self.context.settings.save()

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
        self._save_prompt_now()
        self._generate.setEnabled(False)
        self._status.setText("Generating with Gemini…")
        style = self._style.currentText()
        prompt = self._prompt.toPlainText()
        card = self._card
        run_in_background(
            lambda report: GeminiImageClient().generate_card_art(settings, style, prompt, card),
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
        self._status.setText(friendly_worker_error(error))

    def _show_preview(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return
        self._preview.setPixmap(pixmap.scaledToWidth(PREVIEW_WIDTH, Qt.TransformationMode.SmoothTransformation))


def friendly_worker_error(error: str) -> str:
    for line in reversed(error.splitlines()):
        if "GeminiImageError:" in line:
            return line.split("GeminiImageError:", 1)[-1].strip()
        if line.startswith("URLError:") or line.startswith("URLError("):
            return line
    return error.splitlines()[-1] if error else "Generation failed."
