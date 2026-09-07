from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QToolButton, QWidget

from deckart_studio.cardmaker.asset_library import CardAssetLibrary
from deckart_studio.cardmaker.symbols import PALETTE_SYMBOLS
from deckart_studio.ui.flow_layout import FlowLayout

BUTTON_SIDE = 30


class SymbolPalette(QWidget):
    """Click-to-insert row of mana and action symbols, mirroring the printmtg symbol bar."""

    symbolClicked = Signal(str)

    def __init__(self, assets: CardAssetLibrary, parent: QWidget | None = None):
        super().__init__(parent)
        layout = FlowLayout(self, spacing=3)
        layout.setContentsMargins(0, 0, 0, 0)
        for token in PALETTE_SYMBOLS:
            layout.addWidget(self._make_button(assets, token))

    def _make_button(self, assets: CardAssetLibrary, token: str) -> QToolButton:
        button = QToolButton(self)
        button.setFixedSize(BUTTON_SIDE, BUTTON_SIDE)
        button.setToolTip(token)
        button.setAutoRaise(True)
        image = assets.symbol_image(token[1:-1])
        if image is not None and not image.isNull():
            button.setIcon(QIcon(QPixmap.fromImage(image)))
            button.setIconSize(QSize(BUTTON_SIDE - 6, BUTTON_SIDE - 6))
        else:
            button.setText(token)
        button.clicked.connect(lambda _checked=False, value=token: self.symbolClicked.emit(value))
        return button
