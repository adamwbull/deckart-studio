from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QSplitter, QTextEdit,
    QVBoxLayout, QWidget,
)

from deckart_studio.image_source import ImageSource
from deckart_studio.tts.card_face import CardFace
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.card_maker_dialog import design_card_face
from deckart_studio.ui.card_slot import CardSlotWidget
from deckart_studio.ui.face_chooser import choose_face_for_card
from deckart_studio.ui.gallery_picker_panel import GalleryPickerPanel
from deckart_studio.ui.styles import PRIMARY_BUTTON_STYLE

PREVIEW_WIDTH = 340
PLACEHOLDER_CARD = CardFace(0, {"Nickname": "No deck loaded"}, None, 0)


class FocusTab(QWidget):
    """Work down the deck one card at a time: big preview in the middle, gallery picker on the right."""

    def __init__(self, context: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self._current = 0
        self._card_list = QListWidget()
        self._preview = CardSlotWidget(context, PLACEHOLDER_CARD, PREVIEW_WIDTH)
        self._title = QLabel()
        self._description = QTextEdit()
        self._auto_advance = QCheckBox("Auto-advance after picking")
        self._picker = GalleryPickerPanel(context, tile_width=120)
        self._build_layout()
        self._connect()
        self.rebuild()

    def _build_layout(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._card_list)
        splitter.addWidget(self._preview_column())
        splitter.addWidget(self._picker)
        splitter.setSizes([230, 420, 700])
        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

    def _preview_column(self) -> QWidget:
        column = QWidget()
        self._title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._title.setWordWrap(True)
        self._description.setReadOnly(True)
        self._description.setMaximumHeight(150)
        self._auto_advance.setChecked(self.context.settings.auto_advance)
        layout = QVBoxLayout(column)
        layout.addWidget(self._title)
        layout.addWidget(self._preview, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addLayout(self._navigation_row())
        layout.addWidget(self._card_maker_button())
        layout.addWidget(self._auto_advance)
        layout.addWidget(QLabel("Click the card or drop an image on it. Pick from the gallery on the right."))
        layout.addWidget(self._description)
        layout.addStretch(1)
        return column

    def _navigation_row(self) -> QHBoxLayout:
        previous_button = QPushButton("◀ Previous")
        next_button = QPushButton("Next ▶")
        previous_button.clicked.connect(lambda: self.step(-1))
        next_button.clicked.connect(lambda: self.step(1))
        row = QHBoxLayout()
        row.addWidget(previous_button)
        row.addWidget(next_button)
        return row

    def _card_maker_button(self) -> QPushButton:
        button = QPushButton("Edit this card in Card Maker (custom art + frame)…")
        button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        button.clicked.connect(self.design_current_card)
        return button

    def design_current_card(self) -> None:
        self._open_card_maker(self._current)

    def _connect(self) -> None:
        self._card_list.currentRowChanged.connect(self.show_card)
        self._preview.clicked.connect(self._open_picker_dialog)
        self._preview.designRequested.connect(self._open_card_maker)
        self._preview.removeRequested.connect(self.context.session.remove_card)
        self._preview.commanderRequested.connect(self.context.session.make_commander)
        self._preview.moveRequested.connect(self.context.session.move_card)
        self._preview.imageDropped.connect(self._assign)
        self._picker.sourceChosen.connect(lambda source: self._assign(self._current, source))
        self._auto_advance.toggled.connect(self._on_auto_advance_toggled)
        self.context.session.cardsReset.connect(self.rebuild)
        self.context.session.facesChanged.connect(self._on_faces_changed)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, activated=lambda: self.step(-1))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, activated=lambda: self.step(1))

    def rebuild(self) -> None:
        self._card_list.clear()
        for card in self.context.session.cards():
            self._card_list.addItem(QListWidgetItem(f"{card.index + 1:>3}. {card.nickname}"))
        self.show_card(min(self._current, self._card_list.count() - 1))

    def show_card(self, index: int) -> None:
        card = self.context.session.card(index)
        if card is None:
            self._show_placeholder()
            return
        self._current = index
        self._preview.set_card(card)
        self._title.setText(f"{index + 1} / {self._card_list.count()} — {card.nickname}")
        self._description.setPlainText(card.description)
        self._picker.set_card_name(card.nickname)
        self._sync_list_selection(index)

    def step(self, delta: int) -> None:
        count = self._card_list.count()
        if count:
            self.show_card((self._current + delta) % count)

    def _show_placeholder(self) -> None:
        self._preview.set_card(PLACEHOLDER_CARD)
        self._title.setText("Open a deck to begin")
        self._description.clear()
        self._picker.set_card_name("")

    def _sync_list_selection(self, index: int) -> None:
        if self._card_list.currentRow() != index:
            self._card_list.blockSignals(True)
            self._card_list.setCurrentRow(index)
            self._card_list.blockSignals(False)

    def _open_picker_dialog(self, index: int) -> None:
        card = self.context.session.card(index)
        if card is not None:
            self._assign_if_chosen(index, choose_face_for_card(self.context, card, self))

    def _open_card_maker(self, index: int) -> None:
        card = self.context.session.card(index)
        if card is not None:
            self._assign_if_chosen(index, design_card_face(self.context, card, self))

    def _assign_if_chosen(self, index: int, chosen: ImageSource | None) -> None:
        if chosen is not None:
            self._assign(index, chosen)

    def _assign(self, index: int, source: ImageSource) -> None:
        if not self.context.session.has_deck():
            return
        self.context.session.assign_face(index, source)
        if self._auto_advance.isChecked() and index == self._current:
            self.step(1)

    def _on_faces_changed(self, indices: list[int]) -> None:
        card = self.context.session.card(self._current)
        if card is not None and (not indices or self._current in indices):
            self._preview.refresh(card)

    def _on_auto_advance_toggled(self, checked: bool) -> None:
        self.context.settings.auto_advance = checked
        self.context.settings.save()
