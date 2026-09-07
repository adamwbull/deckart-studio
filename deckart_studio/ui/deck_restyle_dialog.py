from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from deckart_studio.cardmaker.card_design import DEFAULT_TEMPLATE_ID
from deckart_studio.cardmaker.deck_batch import BatchCard, DeckFaceBatch, RenderedFace
from deckart_studio.image_source import ImageSource
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.deck_session import DeckSession
from deckart_studio.ui.styles import PRIMARY_BUTTON_STYLE
from deckart_studio.ui.workers import run_in_background


class DeckRestyleDialog(QDialog):
    """Rebuild every card in the open deck: one chosen frame, and/or one artist credit."""

    def __init__(self, context: AppContext, parent: QWidget | None = None, artist_only: bool = False):
        super().__init__(parent)
        self.context = context
        self._artist_only = artist_only
        self._template = QComboBox()
        self._artist = QLineEdit()
        self._progress = QProgressBar()
        self._status = QLabel()
        self._start_button = QPushButton(self._start_label())
        self._close_button = QPushButton("Cancel")
        self.setWindowTitle(self._window_title())
        self.resize(560, 280)
        self._build()

    def _window_title(self) -> str:
        return "Set artist on all cards" if self._artist_only else "Make deck single art"

    def _start_label(self) -> str:
        return "Apply artist and re-render" if self._artist_only else "Render deck and save"

    def _build(self) -> None:
        self._fill_template_choices()
        self._artist.setText(self.context.settings.last_artist_credit)
        self._artist.setPlaceholderText("Leave blank to keep each card's artist" if not self._artist_only
                                        else "Artist credit printed on every card")
        self._progress.setRange(0, 0)
        self._progress.hide()
        self._status.setWordWrap(True)
        self._start_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self._start_button.setDefault(True)
        self._start_button.clicked.connect(self._start)
        self._close_button.clicked.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self._explanation())
        layout.addLayout(self._form())
        layout.addWidget(self._progress)
        layout.addWidget(self._status)
        layout.addStretch(1)
        layout.addLayout(self._button_row())

    def _fill_template_choices(self) -> None:
        for template in self.context.card_assets.template_list():
            self._template.addItem(template.name, template.id)
        self._template.setCurrentIndex(max(0, self._template.findData(DEFAULT_TEMPLATE_ID)))

    def _explanation(self) -> QLabel:
        count = len(self.context.session.all_cards())
        stacks = len(self.context.session.boards())
        if self._artist_only:
            text = (f"The artist credit on all {count} cards across {stacks} stack(s) will be replaced, "
                    "then every face will be re-rendered in its current frame.")
        else:
            text = (f"All {count} cards across {stacks} stack(s) will be rebuilt in the frame you pick. "
                    "Name, cost, type, rules and P/T come from Scryfall (or the deck's own text). "
                    "Art you already picked from the gallery is kept; otherwise the card's original artwork is used.")
        label = QLabel(text)
        label.setWordWrap(True)
        return label

    def _form(self) -> QFormLayout:
        form = QFormLayout()
        if not self._artist_only:
            form.addRow("Frame", self._template)
        form.addRow("Artist credit", self._artist)
        return form

    def _button_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self._close_button)
        row.addWidget(self._start_button)
        return row

    def _start(self) -> None:
        artist = self._artist.text().strip()
        if self._artist_only and not artist:
            self._status.setText("Enter an artist name to apply to every card.")
            return
        cards = snapshot_entire_deck(self.context.session)
        if not cards:
            self._status.setText("This deck has no cards.")
            return
        remember_artist(self.context, artist)
        template_id = None if self._artist_only else self._template.currentData()
        batch = self.context.deck_face_batch()
        self._set_busy(True)
        run_in_background(lambda report: batch.run(cards, template_id, artist or None, report),
                          self._on_rendered, self._on_failed, self._status.setText, owner=self)

    def _set_busy(self, busy: bool) -> None:
        self._start_button.setEnabled(not busy)
        self._template.setEnabled(not busy)
        self._artist.setEnabled(not busy)
        self._close_button.setEnabled(not busy)
        self._progress.setVisible(busy)

    def _on_rendered(self, rendered: object) -> None:
        faces: list[RenderedFace] = rendered
        for face in faces:
            self.context.thumbnails.forget(str(face.path))
        self.context.session.assign_board_faces(
            [(face.board_index, face.index, ImageSource.from_local(face.path)) for face in faces])
        self.context.session.save()
        self.accept()

    def _on_failed(self, error: str) -> None:
        self._set_busy(False)
        self._status.setText(f"Failed:\n{error}")
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)


def snapshot_entire_deck(session: DeckSession) -> list[BatchCard]:
    cards: list[BatchCard] = []
    for board_index, board in enumerate(session.boards()):
        cards.extend(DeckFaceBatch.snapshot(board.cards, session.face_source, board_index,
                                            session.render_scope_name_for(board_index)))
    return cards


def remember_artist(context: AppContext, artist: str) -> None:
    if not artist:
        return
    context.settings.last_artist_credit = artist
    context.settings.save()


def restyle_whole_deck(context: AppContext, parent: QWidget | None) -> None:
    if context.session.has_deck():
        DeckRestyleDialog(context, parent).exec()


def set_deck_artist(context: AppContext, parent: QWidget | None) -> None:
    if context.session.has_deck():
        DeckRestyleDialog(context, parent, artist_only=True).exec()
