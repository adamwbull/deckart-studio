from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QWidget


class PieceSlotRow(QWidget):
    """Browse or clear one custom plate PNG for a Full Art chrome slot."""

    pathChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._path = ""
        self._name = QLabel("None")
        browse = QPushButton("Browse…")
        clear = QPushButton("Clear")
        browse.clicked.connect(self._browse)
        clear.clicked.connect(self._clear)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._name, 1)
        layout.addWidget(browse)
        layout.addWidget(clear)
        self._refresh_name()

    def path(self) -> str:
        return self._path

    def set_path(self, path: str) -> None:
        self._path = path
        self._refresh_name()

    def _browse(self) -> None:
        chosen, _filter = QFileDialog.getOpenFileName(
            self, "Choose plate PNG", self._path, "Images (*.png *.webp *.jpg *.jpeg)"
        )
        if not chosen:
            return
        self.set_path(chosen)
        self.pathChanged.emit(self._path)

    def _clear(self) -> None:
        self.set_path("")
        self.pathChanged.emit("")

    def _refresh_name(self) -> None:
        self._name.setText(Path(self._path).name if self._path else "None")
        self._name.setToolTip(self._path)
