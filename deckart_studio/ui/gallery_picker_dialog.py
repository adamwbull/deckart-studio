from dataclasses import dataclass

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPushButton, QVBoxLayout, QWidget

from deckart_studio.image_source import ImageSource
from deckart_studio.tts.card_face import CardFace
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.gallery_picker_panel import GalleryPickerPanel


@dataclass
class PickOutcome:
    source: ImageSource | None = None
    open_card_maker: bool = False


class GalleryPickerDialog(QDialog):
    """Modal wrapper around the picker panel; closes as soon as an image is chosen."""

    def __init__(self, context: AppContext, title: str, subject: str, offer_card_maker: bool,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.outcome = PickOutcome()
        self.setWindowTitle(title)
        self.resize(1100, 760)
        self._panel = GalleryPickerPanel(context, tile_width=130, parent=self)
        self._panel.set_card_name(subject)
        self._panel.sourceChosen.connect(self._accept_source)
        self._build_layout(subject, offer_card_maker)

    def _build_layout(self, subject: str, offer_card_maker: bool) -> None:
        heading = QLabel(f"<b>{subject}</b> — click an image to assign it.")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        if offer_card_maker:
            buttons.addButton(self._card_maker_button(), QDialogButtonBox.ButtonRole.ActionRole)
        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(self._panel, 1)
        layout.addWidget(buttons)

    def _card_maker_button(self) -> QPushButton:
        button = QPushButton("Design a full card face with Card Maker…")
        button.clicked.connect(self._request_card_maker)
        return button

    def _accept_source(self, source: ImageSource) -> None:
        self.outcome = PickOutcome(source=source)
        self.accept()

    def _request_card_maker(self) -> None:
        self.outcome = PickOutcome(open_card_maker=True)
        self.accept()


def pick_image_for_card(context: AppContext, card: CardFace, parent: QWidget | None) -> PickOutcome:
    dialog = GalleryPickerDialog(context, f"Choose art for {card.nickname}", card.nickname, True, parent)
    dialog.exec()
    return dialog.outcome


def pick_card_back(context: AppContext, parent: QWidget | None) -> ImageSource | None:
    dialog = GalleryPickerDialog(context, "Choose the card back for every card", "Card back", False, parent)
    dialog.exec()
    return dialog.outcome.source
