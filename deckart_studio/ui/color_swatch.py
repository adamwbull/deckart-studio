from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QPushButton


class ColorSwatch(QPushButton):
    """A compact button that opens a color picker and shows the current color."""

    colorChanged = Signal(str)

    def __init__(self, hex_color: str, parent=None):
        super().__init__(parent)
        self._hex = QColor(hex_color).name() if QColor(hex_color).isValid() else "#141414"
        self.setFixedSize(28, 24)
        self.setToolTip("Text color")
        self.clicked.connect(self._choose_color)
        self._apply_swatch()

    def hex(self) -> str:
        return self._hex

    def set_hex(self, hex_color: str) -> None:
        color = QColor(hex_color)
        if not color.isValid():
            return
        self._hex = color.name()
        self._apply_swatch()

    def _choose_color(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._hex), self, "Text color")
        if not chosen.isValid():
            return
        self.set_hex(chosen.name())
        self.colorChanged.emit(self._hex)

    def _apply_swatch(self) -> None:
        self.setStyleSheet(
            f"QPushButton {{ background-color: {self._hex}; border: 1px solid #333; border-radius: 3px; }}"
        )
