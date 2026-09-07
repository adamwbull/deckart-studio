from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLabel, QSlider, QWidget,
)

from deckart_studio.cardmaker.card_design import CHROME_PIECES, CHROME_STYLE, PIECE_FIELDS
from deckart_studio.cardmaker.fullart_styles import plate_style_list
from deckart_studio.cardmaker.plate_textures import PlateTextureLibrary
from deckart_studio.ui.piece_slot_row import PieceSlotRow

OPACITY_SLIDER_SCALE = 100


class FullArtChromePanel(QWidget):
    """Plate style, texture, opacity, and optional custom PNG slots for Full Art batch or card work."""

    def __init__(self, textures: PlateTextureLibrary, parent=None):
        super().__init__(parent)
        self._chrome_mode = QComboBox()
        self._plate_style = QComboBox()
        self._plate_texture = QComboBox()
        self._opacity = QSlider(Qt.Orientation.Horizontal)
        self._opacity_label = QLabel()
        self._pieces_panel = QWidget()
        self._piece_rows = {kind: PieceSlotRow() for kind in PIECE_FIELDS}
        self._fill_choices(textures)
        self._build()
        self._chrome_mode.currentIndexChanged.connect(self._refresh_pieces)
        self._opacity.valueChanged.connect(self._update_opacity_label)
        self._refresh_pieces()

    def chrome_mode(self) -> str:
        return self._chrome_mode.currentData() or CHROME_STYLE

    def plate_style_id(self) -> str:
        return self._plate_style.currentData() or "bars"

    def plate_texture_id(self) -> str:
        return self._plate_texture.currentData() or "stone"

    def opacity(self) -> float:
        return self._opacity.value() / OPACITY_SLIDER_SCALE

    def piece_path(self, kind: str) -> str:
        return self._piece_rows[kind].path() if kind in self._piece_rows else ""

    def set_enabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)

    def _fill_choices(self, textures: PlateTextureLibrary) -> None:
        self._chrome_mode.addItem("Built-in styles", CHROME_STYLE)
        self._chrome_mode.addItem("Custom pieces", CHROME_PIECES)
        for style in plate_style_list():
            self._plate_style.addItem(style.label, style.id)
        for texture in textures.list():
            self._plate_texture.addItem(texture.label, texture.id)
        self._opacity.setRange(40, 100)
        self._opacity.setValue(92)
        self._update_opacity_label()

    def _build(self) -> None:
        opacity_row = QWidget()
        opacity_layout = QHBoxLayout(opacity_row)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.addWidget(self._opacity, 1)
        opacity_layout.addWidget(self._opacity_label)
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addRow("Chrome", self._chrome_mode)
        layout.addRow("Plate style", self._plate_style)
        layout.addRow("Plate texture", self._plate_texture)
        layout.addRow("Plate opacity", opacity_row)
        layout.addRow(self._pieces_panel)
        self._build_pieces()

    def _build_pieces(self) -> None:
        layout = QFormLayout(self._pieces_panel)
        layout.setContentsMargins(0, 8, 0, 0)
        note = QLabel("Empty slots keep the plate style. Card-sized PNGs align to the whole face.")
        note.setWordWrap(True)
        layout.addRow(note)
        layout.addRow("Title bar", self._piece_rows["title"])
        layout.addRow("Custom name bar", self._piece_rows["subtitle"])
        layout.addRow("Type line", self._piece_rows["type"])
        layout.addRow("Rules box", self._piece_rows["text"])

    def _refresh_pieces(self) -> None:
        self._pieces_panel.setVisible(self.chrome_mode() == CHROME_PIECES)

    def _update_opacity_label(self) -> None:
        self._opacity_label.setText(f"{self._opacity.value()}%")
