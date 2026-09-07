import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from deckart_studio.settings import cache_directory, settings_directory
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.folder_field import FolderField


class SettingsDialog(QDialog):
    """Every folder the app touches, editable in one place."""

    def __init__(self, context: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        settings = context.settings
        self._saved_objects = FolderField(settings.saved_objects_folder, "Tabletop Simulator Saved Objects folder")
        self._deck_art = FolderField(settings.deck_art_folder, "DeckArt folder (gallery root + rendered cards)")
        self._original_art = FolderField(settings.original_art_folder, "Original card art cache folder")
        self._data = FolderField(str(settings_directory()), "App data folder")
        self._tts_folder = FolderField(settings.tts_install_folder, "Tabletop Simulator install folder")
        self._prefer_remote = QCheckBox("Write Scryfall image URLs into the deck (instead of local file paths) when picking original art")
        self._gemini_key = QLineEdit(settings.gemini_api_key)
        self._gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._gemini_key.setPlaceholderText("Paste a Google AI Studio / Gemini API key")
        self._show_key = QCheckBox("Show key")
        self._check_updates = QCheckBox("Check GitHub Releases for updates on startup")
        self.setWindowTitle("Settings")
        self.resize(820, 460)
        self._build()

    def _build(self) -> None:
        self._data.set_read_only(True)
        self._prefer_remote.setChecked(self.context.settings.prefer_remote_original_urls)
        self._check_updates.setChecked(self.context.settings.check_for_updates)
        self._show_key.toggled.connect(self._toggle_key_visibility)
        layout = QVBoxLayout(self)
        layout.addLayout(self._form())
        layout.addWidget(self._prefer_remote)
        layout.addWidget(self._check_updates)
        layout.addWidget(self._hint())
        layout.addStretch(1)
        layout.addWidget(self._buttons())

    def _form(self) -> QFormLayout:
        form = QFormLayout()
        form.addRow("TTS Saved Objects", self._saved_objects)
        form.addRow("DeckArt folder", self._deck_art)
        form.addRow("Original art cache", self._original_art)
        form.addRow("Settings / cache / backups", self._data)
        form.addRow("Tabletop Simulator folder", self._tts_folder)
        form.addRow("Gemini API key", self._gemini_key_row())
        form.addRow("", self._steam_status_label())
        form.addRow("", self._clear_cache_button())
        return form

    def _gemini_key_row(self) -> QWidget:
        host = QWidget()
        layout = QHBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._gemini_key, 1)
        layout.addWidget(self._show_key)
        return host

    def _toggle_key_visibility(self, visible: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self._gemini_key.setEchoMode(mode)

    def _steam_status_label(self) -> QLabel:
        status = self.context.steam_status()
        label = QLabel(status.describe() + "\n(Leave the folder blank to auto-detect from your Steam libraries.)")
        label.setWordWrap(True)
        label.setStyleSheet("color: #7fd18a;" if status.is_ready() else "color: #ff8a80;")
        return label

    @staticmethod
    def _hint() -> QLabel:
        hint = QLabel("Extra gallery folders and files are managed in the Gallery sources panel (toolbar), or by dropping "
                      "them onto the Gallery tab. The DeckArt folder is always a gallery source.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        return hint

    def _clear_cache_button(self) -> QPushButton:
        button = QPushButton("Clear thumbnail / download cache")
        button.clicked.connect(self._clear_cache)
        return button

    def _buttons(self) -> QDialogButtonBox:
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        return buttons

    def _clear_cache(self) -> None:
        shutil.rmtree(cache_directory(), ignore_errors=True)
        self.context.thumbnails.forget_all()

    def _save(self) -> None:
        settings = self.context.settings
        settings.saved_objects_folder = self._saved_objects.text()
        if self._deck_art.path() != settings.deck_art_root():
            settings.change_deck_art_root(self._deck_art.path())
        settings.original_art_folder = self._original_art.text()
        settings.tts_install_folder = self._tts_folder.text()
        settings.prefer_remote_original_urls = self._prefer_remote.isChecked()
        settings.gemini_api_key = self._gemini_key.text().strip()
        settings.check_for_updates = self._check_updates.isChecked()
        Path(settings.original_art_folder).mkdir(parents=True, exist_ok=True)
        self.context.apply_folder_settings()
        self.accept()
