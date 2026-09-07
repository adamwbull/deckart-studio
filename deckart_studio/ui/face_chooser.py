from PySide6.QtWidgets import QWidget

from deckart_studio.image_source import ImageSource
from deckart_studio.tts.card_face import CardFace
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.card_maker_dialog import design_card_face
from deckart_studio.ui.gallery_picker_dialog import pick_image_for_card


def choose_face_for_card(context: AppContext, card: CardFace, parent: QWidget | None) -> ImageSource | None:
    """Open the gallery picker; if the user asks for Card Maker instead, hand off to it."""
    outcome = pick_image_for_card(context, card, parent)
    if outcome.open_card_maker:
        return design_card_face(context, card, parent)
    return outcome.source
