from PySide6.QtCore import QObject

from deckart_studio.image_source import ImageSource
from deckart_studio.tts.card_face import CardFace
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.card_commands import confirm_delete_card
from deckart_studio.ui.card_maker_dialog import design_card_face
from deckart_studio.ui.card_slot import CardSlotWidget
from deckart_studio.ui.face_chooser import choose_face_for_card


class SlotCollection(QObject):
    """Owns the CardSlotWidgets of one deck view and wires their clicks and drops to the session."""

    def __init__(self, context: AppContext, parent_widget, slot_width: int):
        super().__init__(parent_widget)
        self.context = context
        self.parent_widget = parent_widget
        self.slot_width = slot_width
        self._slots: dict[int, CardSlotWidget] = {}
        context.session.facesChanged.connect(self.refresh_faces)

    def create_slot(self, card: CardFace) -> CardSlotWidget:
        slot = CardSlotWidget(self.context, card, self.slot_width, self.parent_widget)
        slot.clicked.connect(self._on_slot_clicked)
        slot.designRequested.connect(self._on_design_requested)
        slot.removeRequested.connect(self._on_remove_requested)
        slot.commanderRequested.connect(self.context.session.make_commander)
        slot.duplicateRequested.connect(self.context.session.duplicate_card)
        slot.imageDropped.connect(self._on_slot_dropped)
        self._slots[card.index] = slot
        return slot

    def clear(self) -> None:
        self._slots.clear()

    def slot(self, index: int) -> CardSlotWidget | None:
        return self._slots.get(index)

    def set_slot_width(self, width: int) -> None:
        self.slot_width = width
        for slot in self._slots.values():
            slot.set_box_width(width)

    def refresh_faces(self, indices: list[int]) -> None:
        targets = indices or list(self._slots.keys())
        for index in targets:
            self._refresh_slot(index)

    def _refresh_slot(self, index: int) -> None:
        slot = self._slots.get(index)
        card = self.context.session.card(index)
        if slot is not None and card is not None:
            slot.refresh(card)

    def _on_remove_requested(self, index: int) -> None:
        confirm_delete_card(self.parent_widget, self.context.session, index)

    def _on_slot_clicked(self, index: int) -> None:
        card = self.context.session.card(index)
        if card is not None:
            self._assign_if_chosen(index, choose_face_for_card(self.context, card, self.parent_widget))

    def _on_design_requested(self, index: int) -> None:
        card = self.context.session.card(index)
        if card is not None:
            self._assign_if_chosen(index, design_card_face(self.context, card, self.parent_widget))

    def _assign_if_chosen(self, index: int, chosen: ImageSource | None) -> None:
        if chosen is not None:
            self.context.session.assign_face(index, chosen)

    def _on_slot_dropped(self, index: int, source: ImageSource) -> None:
        self.context.session.assign_face(index, source)
