from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QSlider, QVBoxLayout, QWidget

from deckart_studio.ui.action_bar import hint_label
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.flow_layout import FlowLayout
from deckart_studio.ui.slot_collection import SlotCollection

MIN_SLOT_WIDTH = 90
MAX_SLOT_WIDTH = 320


class BirdsEyeTab(QWidget):
    """Every card face of the current stack at once; click any slot to re-art it or drop an image onto it."""

    def __init__(self, context: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self._flow_host = QWidget()
        self._flow = FlowLayout(self._flow_host)
        self._slots = SlotCollection(context, self._flow_host, context.settings.slot_size)
        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._count_label = QLabel()
        self._build_layout()
        context.session.cardsReset.connect(self.rebuild)
        self.rebuild()

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.addLayout(self._header())
        layout.addWidget(self._scroll_area(), 1)

    def _header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.addWidget(self._count_label)
        header.addWidget(hint_label("Click a card to pick art, drop an image onto it, or right-click for more."))
        header.addStretch(1)
        header.addLayout(self._size_controls())
        return header

    def _size_controls(self) -> QHBoxLayout:
        self._size_slider.setRange(MIN_SLOT_WIDTH, MAX_SLOT_WIDTH)
        self._size_slider.setValue(self.context.settings.slot_size)
        self._size_slider.setFixedWidth(160)
        self._size_slider.valueChanged.connect(self._on_slot_size_changed)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Card size"))
        controls.addWidget(self._size_slider)
        return controls

    def _scroll_area(self) -> QScrollArea:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._flow_host)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return scroll

    def rebuild(self) -> None:
        self._flow.clear_widgets()
        self._slots.clear()
        cards = self.context.session.cards()
        for card in cards:
            self._flow.addWidget(self._slots.create_slot(card))
        self._count_label.setText(f"{len(cards)} cards")

    def _on_slot_size_changed(self, width: int) -> None:
        self._slots.set_slot_width(width)
        self.context.settings.slot_size = width
        self.context.settings.save()
        self._flow_host.updateGeometry()
