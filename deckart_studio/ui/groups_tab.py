from collections import OrderedDict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from deckart_studio.tts.card_face import CardFace
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.flow_layout import FlowLayout
from deckart_studio.ui.slot_collection import SlotCollection

GROUPING_MODES = ("Card type", "First letter", "Image sheet", "Tens")
HEADER_STYLE = "QLabel { font-size: 15px; font-weight: bold; padding: 6px 4px; color: #e6edf3; }"


class GroupsTab(QWidget):
    """The deck split into labelled sections so related cards can be re-arted together."""

    def __init__(self, context: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self._mode = QComboBox()
        self._sections_host = QWidget()
        self._sections_layout = QVBoxLayout(self._sections_host)
        self._slots = SlotCollection(context, self._sections_host, max(110, context.settings.slot_size - 40))
        self._build_layout()
        self._mode.currentTextChanged.connect(lambda _text: self.rebuild())
        context.session.cardsReset.connect(self.rebuild)
        self.rebuild()

    def _build_layout(self) -> None:
        self._mode.addItems(GROUPING_MODES)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Group by"))
        controls.addWidget(self._mode)
        controls.addStretch(1)
        self._sections_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._sections_host)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(scroll, 1)

    def rebuild(self) -> None:
        self._clear_sections()
        self._slots.clear()
        for title, cards in group_cards(self.context.session.cards(), self._mode.currentText()).items():
            self._add_section(title, cards)
        self._sections_layout.addStretch(1)

    def _clear_sections(self) -> None:
        while self._sections_layout.count():
            item = self._sections_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _add_section(self, title: str, cards: list[CardFace]) -> None:
        header = QLabel(f"{title}  ({len(cards)})")
        header.setStyleSheet(HEADER_STYLE)
        flow_host = QWidget(self._sections_host)
        flow = FlowLayout(flow_host)
        for card in cards:
            flow.addWidget(self._slots.create_slot(card))
        self._sections_layout.addWidget(header)
        self._sections_layout.addWidget(flow_host)


def group_cards(cards: list[CardFace], mode: str) -> "OrderedDict[str, list[CardFace]]":
    groups: "OrderedDict[str, list[CardFace]]" = OrderedDict()
    for card in cards:
        groups.setdefault(group_key(card, mode), []).append(card)
    return OrderedDict(sorted(groups.items(), key=lambda item: sort_key(item[0], mode)))


def group_key(card: CardFace, mode: str) -> str:
    if mode == "Card type":
        return card.type_group()
    if mode == "First letter":
        return card.nickname[:1].upper() or "#"
    if mode == "Image sheet":
        return f"Sheet {card.sheet_id}"
    return f"Cards {card.index // 10 * 10 + 1}–{card.index // 10 * 10 + 10}"


def sort_key(title: str, mode: str):
    if mode == "Card type":
        order = ["Creature", "Planeswalker", "Battle", "Instant", "Sorcery", "Artifact", "Enchantment", "Land", "Other"]
        return (order.index(title) if title in order else len(order), title)
    if mode == "Tens":
        return (int(title.split()[1].split("–")[0]), title)
    return (0, title)
