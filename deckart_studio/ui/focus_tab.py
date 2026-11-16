from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSplitter,
    QTextEdit, QVBoxLayout, QWidget,
)

from deckart_studio.image_source import ImageSource
from deckart_studio.tts.card_face import CardFace
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.card_command_bar import CardCommandBar
from deckart_studio.ui.card_commands import confirm_delete_card
from deckart_studio.ui.card_maker_dialog import design_card_face
from deckart_studio.ui.card_slot import CardSlotWidget
from deckart_studio.ui.face_chooser import choose_face_for_card
from deckart_studio.ui.gallery_picker_panel import GalleryPickerPanel

PREVIEW_WIDTH = 340
PLACEHOLDER_CARD = CardFace(0, {"Nickname": "No deck loaded"}, None, 0)


class FocusTab(QWidget):
    """Work down one stack a card at a time: list on the left, preview in the middle, gallery on the right."""

    def __init__(self, context: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self._current = 0
        self._filter = QLineEdit()
        self._card_list = QListWidget()
        self._preview = CardSlotWidget(context, PLACEHOLDER_CARD, PREVIEW_WIDTH)
        self._title = QLabel()
        self._description = QTextEdit()
        self._auto_advance = QCheckBox("Auto-advance after picking art")
        self._commands = CardCommandBar(context)
        self._previous = QPushButton("◀ Previous")
        self._next = QPushButton("Next ▶")
        self._picker = GalleryPickerPanel(context, tile_width=120)
        self._build_layout()
        self._connect()
        self.rebuild()

    def _build_layout(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._list_column())
        splitter.addWidget(self._preview_column())
        splitter.addWidget(self._picker)
        splitter.setSizes([240, 420, 700])
        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

    def _list_column(self) -> QWidget:
        self._filter.setPlaceholderText("Find a card in this stack")
        self._filter.setClearButtonEnabled(True)
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._filter)
        layout.addWidget(self._card_list, 1)
        return column

    def _preview_column(self) -> QWidget:
        column = QWidget()
        self._title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._title.setWordWrap(True)
        self._description.setReadOnly(True)
        self._description.setMaximumHeight(120)
        self._auto_advance.setChecked(self.context.settings.auto_advance)
        layout = QVBoxLayout(column)
        layout.addWidget(self._title)
        layout.addWidget(self._preview, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addLayout(self._navigation_row())
        layout.addWidget(self._commands)
        layout.addWidget(self._auto_advance)
        layout.addWidget(QLabel("Click the card, or drop an image on it, to change the art."))
        layout.addWidget(self._description)
        layout.addStretch(1)
        return column

    def _navigation_row(self) -> QHBoxLayout:
        self._previous.clicked.connect(lambda: self.step(-1))
        self._next.clicked.connect(lambda: self.step(1))
        row = QHBoxLayout()
        row.addWidget(self._previous)
        row.addWidget(self._next)
        return row

    def design_current_card(self) -> None:
        self._open_card_maker(self._current)

    def _connect(self) -> None:
        self._card_list.currentRowChanged.connect(self.show_card)
        self._filter.textChanged.connect(self._on_filter_changed)
        self._preview.clicked.connect(self._open_picker_dialog)
        self._preview.designRequested.connect(self._open_card_maker)
        self._preview.removeRequested.connect(lambda index: confirm_delete_card(self, self.context.session, index))
        self._preview.commanderRequested.connect(self.context.session.make_commander)
        self._preview.duplicateRequested.connect(self.context.session.duplicate_card)
        self._preview.imageDropped.connect(self._assign)
        self._commands.editRequested.connect(self.design_current_card)
        self._picker.sourceChosen.connect(lambda source: self._assign(self._current, source))
        self._auto_advance.toggled.connect(self._on_auto_advance_toggled)
        self.context.session.cardsReset.connect(self.rebuild)
        self.context.session.facesChanged.connect(self._on_faces_changed)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, activated=lambda: self.step(-1))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, activated=lambda: self.step(1))
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self._card_list, activated=self._commands.delete_current)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self._preview, activated=self._commands.delete_current)
        find_shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.Find), self)
        find_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        find_shortcut.activated.connect(self._filter.setFocus)

    def rebuild(self) -> None:
        self._card_list.blockSignals(True)
        self._card_list.clear()
        for card in self.context.session.cards():
            self._card_list.addItem(QListWidgetItem(f"{card.index + 1:>3}. {card.nickname}"))
        self._card_list.blockSignals(False)
        self._hide_non_matching(self._filter.text())
        self.show_card(self._index_to_show())

    def show_card(self, index: int) -> None:
        card = self.context.session.card(index)
        if card is None:
            self._show_empty(index)
            return
        self._current = index
        self._preview.set_card(card)
        self._title.setText(self._heading(card))
        self._description.setPlainText(card.description)
        self._picker.set_card_name(card.nickname)
        self._commands.show_card(index)
        self._sync_list_selection(index)
        self._refresh_navigation()

    def step(self, delta: int) -> None:
        visible = self._visible_indices()
        if not visible:
            return
        if self._current in visible:
            position = visible.index(self._current)
            self.show_card(visible[(position + delta) % len(visible)])
            return
        self.show_card(visible[0])

    def _show_empty(self, index: int) -> None:
        self._commands.show_no_card()
        self._refresh_navigation()
        if self.context.session.cards():
            self._preview.set_card(CardFace(-1, {"Nickname": "No match"}, None, 0))
            self._title.setText("No cards match this search")
            self._description.clear()
            self._picker.set_card_name("")
            return
        self._preview.set_card(PLACEHOLDER_CARD)
        self._title.setText("Open a deck to begin")
        self._description.clear()
        self._picker.set_card_name("")
        self._current = index

    def _heading(self, card: CardFace) -> str:
        board = self.context.session.active_board()
        stack = board.name if board is not None else ""
        if self._filter.text().strip():
            return f"{stack}  ·  {len(self._visible_indices())} match(es)  ·  {card.nickname}"
        return f"{stack}  ·  {self._current + 1} / {self._card_list.count()}  ·  {card.nickname}"

    def _index_to_show(self) -> int:
        if self._is_visible(self._current):
            return self._current
        visible = self._visible_indices()
        return visible[0] if visible else -1

    def _on_filter_changed(self, text: str) -> None:
        self._hide_non_matching(text)
        if self._card_list.count() and not self._is_visible(self._current):
            self.show_card(self._index_to_show())
        else:
            self._refresh_navigation()

    def _hide_non_matching(self, text: str) -> None:
        query = text.strip().casefold()
        for row in range(self._card_list.count()):
            item = self._card_list.item(row)
            item.setHidden(bool(query) and query not in item.text().casefold())

    def _visible_indices(self) -> list[int]:
        return [row for row in range(self._card_list.count()) if self._is_visible(row)]

    def _is_visible(self, index: int) -> bool:
        item = self._card_list.item(index)
        return item is not None and not item.isHidden()

    def _refresh_navigation(self) -> None:
        can_step = len(self._visible_indices()) > 1
        self._previous.setEnabled(can_step)
        self._next.setEnabled(can_step)

    def _sync_list_selection(self, index: int) -> None:
        if self._card_list.currentRow() != index:
            self._card_list.blockSignals(True)
            self._card_list.setCurrentRow(index)
            self._card_list.blockSignals(False)

    def _open_picker_dialog(self, index: int) -> None:
        card = self.context.session.card(index)
        if card is not None and self._is_visible(index):
            self._assign_if_chosen(index, choose_face_for_card(self.context, card, self))

    def _open_card_maker(self, index: int) -> None:
        card = self.context.session.card(index)
        if card is not None and self._is_visible(index):
            self._assign_if_chosen(index, design_card_face(self.context, card, self))

    def _assign_if_chosen(self, index: int, chosen: ImageSource | None) -> None:
        if chosen is not None:
            self._assign(index, chosen)

    def _assign(self, index: int, source: ImageSource) -> None:
        if not self.context.session.has_deck() or not self._is_visible(index):
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
