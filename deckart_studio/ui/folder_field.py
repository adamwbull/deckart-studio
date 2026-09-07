from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget


class FolderField(QWidget):
    """A path line edit with Browse… and Open buttons."""

    def __init__(self, initial: str, dialog_title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.dialog_title = dialog_title
        self._edit = QLineEdit(initial)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        open_button = QPushButton("Open")
        open_button.clicked.connect(self._open)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._edit, 1)
        layout.addWidget(browse)
        layout.addWidget(open_button)

    def path(self) -> Path:
        return Path(self._edit.text().strip())

    def text(self) -> str:
        return self._edit.text().strip()

    def set_read_only(self, read_only: bool) -> None:
        self._edit.setReadOnly(read_only)

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, self.dialog_title, self._edit.text())
        if chosen:
            self._edit.setText(str(Path(chosen)))

    def _open(self) -> None:
        if not self.text():
            return
        self.path().mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path())))
