import os
from pathlib import Path

from PySide6.QtCore import QByteArray, QTimer, Qt
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QKeySequence
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QComboBox, QDockWidget, QFileDialog, QLabel, QMainWindow, QMessageBox, QTabWidget, QToolBar, QVBoxLayout, QWidget,
)

from deckart_studio.tts.saved_objects import discover_deck_files
from deckart_studio.updates import (
    apply_downloaded_update, download_release_package, frozen_install_folder, is_newer_version,
    latest_release, should_check_for_updates, update_download_folder,
)
from deckart_studio.version import APP_NAME, APP_VERSION
from deckart_studio.ui.action_bar import ActionBar
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.birds_eye_tab import BirdsEyeTab
from deckart_studio.ui.card_back_widget import CardBackWidget
from deckart_studio.ui.stack_bar import StackBar
from deckart_studio.ui.deck_restyle_dialog import restyle_whole_deck, set_deck_artist
from deckart_studio.ui.focus_tab import FocusTab
from deckart_studio.ui.gallery_dock import GalleryDock
from deckart_studio.ui.groups_tab import GroupsTab
from deckart_studio.ui.import_deck_dialog import ImportDeckDialog
from deckart_studio.ui.publish_dialog import publish_deck
from deckart_studio.ui.save_thumbnail import write_save_thumbnail
from deckart_studio.ui.settings_dialog import SettingsDialog
from deckart_studio.ui.workers import run_in_background


def window_title(deck_name: str = "", update_version: str = "") -> str:
    parts = [f"{APP_NAME} {APP_VERSION}"]
    if deck_name:
        parts.append(deck_name)
    if update_version:
        parts.append(f"update {update_version} available")
    return " — ".join(parts)


class MainWindow(QMainWindow):
    """DeckArt Studio's shell: deck chooser toolbar, the three deck views, and the gallery dock."""

    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self._deck_combo = QComboBox()
        self._deck_paths: list[Path] = []
        self._dirty_label = QLabel()
        self._available_update = ""
        self._action_bar = ActionBar()
        self._focus_tab = FocusTab(context)
        self._tabs = QTabWidget(self)
        self._refresh_window_title()
        self.resize(1500, 950)
        self._build_toolbar()
        self._build_action_bar()
        self._build_tabs()
        self._build_gallery_dock()
        self._connect_session()
        self._restore_geometry()
        self.refresh_deck_list()
        self._open_last_deck()
        self._offer_import_when_empty()
        if self.context.settings.check_for_updates and should_check_for_updates():
            QTimer.singleShot(2500, lambda: self._check_for_updates(silent=True))

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Deck", self)
        self._toolbar = toolbar
        toolbar.setMovable(False)
        toolbar.addWidget(QLabel(" Deck: "))
        self._deck_combo.setMinimumWidth(320)
        self._deck_combo.activated.connect(self._on_deck_chosen)
        toolbar.addWidget(self._deck_combo)
        self._add_action(toolbar, "Refresh list", self.refresh_deck_list)
        self._add_action(toolbar, "Import Moxfield / deck list…", self._import_deck, "Ctrl+I")
        toolbar.addSeparator()
        self._add_action(toolbar, "Save", self._save, "Ctrl+S")
        self._add_action(toolbar, "Save As…", self._save_as, "Ctrl+Shift+S")
        toolbar.addSeparator()
        self._artist_action = self._add_action(toolbar, "Set artist on all cards…", self._set_deck_artist)
        self._artist_action.setEnabled(False)
        self._add_action(toolbar, "Settings", self._open_settings)
        self._add_action(toolbar, "Check for updates…", self._check_for_updates)
        self._add_action(toolbar, "Open Saved Objects folder", self._open_saved_objects_folder)
        toolbar.addSeparator()
        toolbar.addWidget(self._dirty_label)
        self.addToolBar(toolbar)

    def _add_action(self, toolbar: QToolBar, text: str, handler, shortcut: str = "") -> QAction:
        action = QAction(text, self)
        action.triggered.connect(handler)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        toolbar.addAction(action)
        return action

    def _build_action_bar(self) -> None:
        self._action_bar.add_step(1, "Import deck from Moxfield…", self._import_deck,
                                  "Paste a Moxfield link or deck list; the deck lands in Saved Objects ready for TTS",
                                  needs_deck=False)
        self._action_bar.add_step(2, "Edit current card (Card Maker)…", self._design_current_card,
                                  "Swap the art and re-render the selected card as a custom face")
        self._action_bar.add_step(3, "Make deck single art…", self._restyle_deck,
                                  "Pick Full Art, Clear Art, or another frame and rebuild every card")
        self._action_bar.add_step(4, "Save deck", self._save, "Write the deck JSON back into Saved Objects")
        self._action_bar.add_step(5, "Publish to Steam Cloud…", self._publish_deck,
                                  "Upload local images to Steam Cloud so everyone in your TTS game sees them, then save")
        self._action_bar.add_trailing(CardBackWidget(self.context))
        self._action_bar.set_deck_open(False)

    def _build_tabs(self) -> None:
        self._tabs.addTab(self._focus_tab, "Focus (one card at a time)")
        self._tabs.addTab(BirdsEyeTab(self.context), "Bird's Eye (all faces)")
        self._tabs.addTab(GroupsTab(self.context), "Groups")
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._action_bar)
        layout.addWidget(StackBar(self.context))
        layout.addWidget(self._tabs, 1)
        self.setCentralWidget(central)

    def _design_current_card(self) -> None:
        self._tabs.setCurrentWidget(self._focus_tab)
        self._focus_tab.design_current_card()

    def _restyle_deck(self) -> None:
        restyle_whole_deck(self.context, self)

    def _set_deck_artist(self) -> None:
        set_deck_artist(self.context, self)

    def _publish_deck(self) -> None:
        publish_deck(self.context, self)

    def _offer_import_when_empty(self) -> None:
        if not self._deck_paths:
            self._import_deck()

    def _build_gallery_dock(self) -> None:
        dock = QDockWidget("Gallery sources", self)
        dock.setWidget(GalleryDock(self.context))
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.resizeDocks([dock], [360], Qt.Orientation.Horizontal)
        dock.hide()
        toggle = dock.toggleViewAction()
        toggle.setText("Gallery sources panel")
        self._toolbar.addAction(toggle)

    def _connect_session(self) -> None:
        self.context.session.statusMessage.connect(lambda message: self.statusBar().showMessage(message, 6000))
        self.context.session.dirtyChanged.connect(self._on_dirty_changed)
        self.context.session.deckLoaded.connect(self._on_deck_presence_changed)
        for signal in (self.context.session.deckLoaded, self.context.session.cardsReset, self.context.session.dirtyChanged):
            signal.connect(self._refresh_publish_hint)

    def _on_deck_presence_changed(self) -> None:
        has_deck = self.context.session.has_deck()
        self._action_bar.set_deck_open(has_deck)
        self._artist_action.setEnabled(has_deck)

    def _refresh_publish_hint(self) -> None:
        self._action_bar.set_publish_hint(self.context.session.publish_warning())

    def refresh_deck_list(self) -> None:
        self._deck_paths = discover_deck_files(Path(self.context.settings.saved_objects_folder))
        self._deck_combo.clear()
        self._deck_combo.addItems([str(path.relative_to(self.context.settings.saved_objects_folder))
                                   for path in self._deck_paths])
        self._select_current_deck_in_combo()

    def _select_current_deck_in_combo(self) -> None:
        current = self.context.session.document
        if current is not None and current.path in self._deck_paths:
            self._deck_combo.setCurrentIndex(self._deck_paths.index(current.path))

    def _open_last_deck(self) -> None:
        last = Path(self.context.settings.last_deck_path) if self.context.settings.last_deck_path else None
        if last is not None and last.exists():
            self.open_deck(last)
        elif self._deck_paths:
            self.open_deck(self._deck_paths[0])

    def open_deck(self, path: Path) -> None:
        if not self._confirm_discard_changes():
            self._select_current_deck_in_combo()
            return
        try:
            self.context.session.open_deck(path)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Could not open deck", f"{path}\n\n{error}")
        self._select_current_deck_in_combo()
        self._refresh_window_title()

    def _on_deck_chosen(self, index: int) -> None:
        if 0 <= index < len(self._deck_paths):
            self.open_deck(self._deck_paths[index])

    def _import_deck(self) -> None:
        dialog = ImportDeckDialog(self.context, self)
        if dialog.exec() and dialog.result_path is not None:
            self._finish_import(dialog.result_path, dialog.result_face_url())

    def _finish_import(self, saved_path: Path, first_face_url: str) -> None:
        run_in_background(lambda report: write_save_thumbnail(saved_path, first_face_url),
                          lambda _result: None, lambda _error: None, owner=self)
        self.refresh_deck_list()
        self.open_deck(saved_path)
        self.statusBar().showMessage(f"Imported {saved_path.name} into Saved Objects", 8000)
        self._offer_publish_after_import()

    def _offer_publish_after_import(self) -> None:
        warning = self.context.session.publish_warning()
        if not warning or not self.context.steam_status().is_ready():
            return
        answer = QMessageBox.question(self, "Publish now?",
                                      f"{warning}\n\nPublish the imported deck to Steam Cloud now so it loads in "
                                      "Tabletop Simulator? (You can still change art afterwards and publish again.)")
        if answer == QMessageBox.StandardButton.Yes:
            self._publish_deck()

    def _save(self) -> None:
        self.context.session.save()
        warning = self.context.session.publish_warning()
        if warning:
            self.statusBar().showMessage(f"Saved. {warning}", 12000)

    def _save_as(self) -> None:
        if not self.context.session.has_deck():
            return
        target, _filter = QFileDialog.getSaveFileName(self, "Save deck as", self.context.settings.saved_objects_folder,
                                                      "TTS saved object (*.json)")
        if target:
            self.context.session.save_as(Path(target))
            self.refresh_deck_list()
            self._refresh_window_title()

    def _open_settings(self) -> None:
        if SettingsDialog(self.context, self).exec():
            self.refresh_deck_list()

    def _check_for_updates(self, silent: bool = False) -> None:
        run_in_background(
            lambda report: latest_release(),
            lambda release: self._on_update_release(release, silent),
            lambda error: self._on_update_check_failed(error, silent),
            owner=self,
        )

    def _refresh_window_title(self) -> None:
        document = self.context.session.document
        deck_name = document.path.name if document is not None else ""
        self.setWindowTitle(window_title(deck_name, self._available_update))

    def _on_update_release(self, release: object, silent: bool) -> None:
        if not is_newer_version(release.version):
            self._available_update = ""
            self._refresh_window_title()
            if not silent:
                QMessageBox.information(self, "Up to date", f"You are on {APP_VERSION}.")
            return
        self._available_update = release.version
        self._refresh_window_title()
        if silent:
            self.statusBar().showMessage(f"Update {release.version} available", 12000)
            return
        answer = QMessageBox.question(
            self,
            "Update available",
            f"DeckArt Studio {release.version} is on GitHub (you have {APP_VERSION}).\n\nDownload and install it now?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        install_folder = frozen_install_folder()
        if install_folder is None:
            QMessageBox.information(
                self,
                "Update downloaded from source",
                f"This copy is running from source. Download the release zip from:\n{release.html_url}",
            )
            return
        self.statusBar().showMessage(f"Downloading {release.version}…", 8000)
        run_in_background(
            lambda report: download_release_package(release, update_download_folder(), install_folder),
            lambda package_path: self._install_update(package_path, install_folder),
            lambda error: QMessageBox.warning(self, "Update failed", error.splitlines()[-1]),
            owner=self,
        )

    def _install_update(self, package_path: object, install_folder) -> None:
        from pathlib import Path
        apply_downloaded_update(Path(package_path), install_folder, os.getpid())
        QMessageBox.information(self, "Installing update", "DeckArt Studio will close and reopen on the new version.")
        self.close()

    def _on_update_check_failed(self, error: str, silent: bool) -> None:
        if silent:
            return
        QMessageBox.warning(self, "Update check failed", error.splitlines()[-1])

    def _open_saved_objects_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.context.settings.saved_objects_folder))

    def _on_dirty_changed(self, dirty: bool) -> None:
        self._dirty_label.setText("  ● unsaved changes" if dirty else "")

    def _confirm_discard_changes(self) -> bool:
        document = self.context.session.document
        if document is None or not document.dirty:
            return True
        answer = QMessageBox.question(self, "Unsaved changes", f"Save changes to {document.path.name} first?",
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                                      | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Save:
            self.context.session.save()
        return answer != QMessageBox.StandardButton.Cancel

    def _restore_geometry(self) -> None:
        geometry_hex = self.context.settings.window_geometry_hex
        if geometry_hex:
            self.restoreGeometry(QByteArray.fromHex(geometry_hex.encode("ascii")))

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._confirm_discard_changes():
            event.ignore()
            return
        self.context.settings.window_geometry_hex = bytes(self.saveGeometry().toHex()).decode("ascii")
        self.context.settings.save()
        event.accept()
