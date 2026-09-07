from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from deckart_studio.cardmaker.card_design import DEFAULT_TEMPLATE_ID, CardDesign, design_from_scryfall, format_imported_rules
from deckart_studio.cardmaker.card_lookup import CardLookup
from deckart_studio.cardmaker.card_renderer import EXPORT_SCALE, CardRenderer
from deckart_studio.cardmaker.design_store import DesignStore
from deckart_studio.gallery.gallery_library import GalleryLibrary
from deckart_studio.image_source import ImageSource
from deckart_studio.cardmaker.token_lookup import is_token_description, lookup_token_card
from deckart_studio.original_art.original_art import normalize_card_name
from deckart_studio.tts.card_face import CardFace

ProgressCallback = Callable[[str], None]


@dataclass
class BatchCard:
    """A snapshot of one card taken on the GUI thread so the worker never touches the live document."""

    board_index: int
    index: int
    nickname: str
    description: str
    face_local_path: Path | None
    scope_name: str
    source_art_path: Path | None = None


@dataclass
class RenderedFace:
    board_index: int
    index: int
    path: Path


@dataclass
class BatchOptions:
    template_id: str | None = None
    artist: str | None = None
    apply_fullart_chrome: bool = False
    plate_style_id: str = "bars"
    plate_texture_id: str = "stone"
    chrome_mode: str = "style"
    title_piece_path: str = ""
    subtitle_piece_path: str = ""
    type_piece_path: str = ""
    text_piece_path: str = ""
    opacity: float = 0.92


class DeckFaceBatch:
    """Re-renders every card of a deck, optionally forcing one template and/or one artist credit."""

    def __init__(self, lookup: CardLookup, renderer: CardRenderer, store: DesignStore, gallery: GalleryLibrary):
        self.lookup = lookup
        self.renderer = renderer
        self.store = store
        self.gallery = gallery

    @staticmethod
    def snapshot(cards: list[CardFace], face_source: Callable[[CardFace], ImageSource], board_index: int,
                 scope_name: str) -> list[BatchCard]:
        return [BatchCard(board_index, card.index, card.nickname, card.description,
                          face_source(card).local_path, scope_name) for card in cards]

    def run(self, cards: list[BatchCard], options: BatchOptions, report: ProgressCallback) -> list[RenderedFace]:
        report(f"Looking up {len(cards)} cards on Scryfall…")
        scryfall_cards = self._lookup_cards(cards)
        rendered: list[RenderedFace] = []
        for position, card in enumerate(cards, start=1):
            report(f"Rendering {position}/{len(cards)}: {card.nickname}")
            scryfall = scryfall_cards.get(card.nickname)
            rendered.append(self._render_card(card, scryfall, options))
        return rendered

    def _lookup_cards(self, cards: list[BatchCard]) -> dict[str, dict]:
        token_cards = [card for card in cards if is_token_description(card.description)]
        regular_cards = [card for card in cards if not is_token_description(card.description)]
        found: dict[str, dict] = {}
        if regular_cards:
            scryfall_cards = self.lookup.lookup_many([card.nickname for card in regular_cards])
            for card in regular_cards:
                match = scryfall_cards.get(normalize_card_name(card.nickname))
                if match is not None:
                    found[card.nickname] = match
        for card in token_cards:
            match = lookup_token_card(self.lookup.scryfall, card.nickname, card.description)
            if match is not None:
                found[card.nickname] = match
        return found

    def _render_card(self, card: BatchCard, scryfall_card: dict | None, options: BatchOptions) -> RenderedFace:
        design = self._design_for(card, scryfall_card, options)
        render_path = self.store.render_path(card.scope_name, card.index, design.name or card.nickname)
        render_path.parent.mkdir(parents=True, exist_ok=True)
        self.renderer.render(design, EXPORT_SCALE).save(str(render_path), "PNG")
        self.store.save(design, render_path)
        return RenderedFace(card.board_index, card.index, render_path)

    def _design_for(self, card: BatchCard, scryfall_card: dict | None, options: BatchOptions) -> CardDesign:
        fallback = options.template_id or DEFAULT_TEMPLATE_ID
        stored = self.store.load_design_for_face(card.face_local_path)
        if scryfall_card is not None:
            design = design_from_scryfall(scryfall_card, fallback)
            if stored:
                design.art_zoom = stored.art_zoom
                design.art_offset_x = stored.art_offset_x
                design.art_offset_y = stored.art_offset_y
        else:
            design = stored or self._fresh_design(card, scryfall_card, fallback)
        apply_batch_options(design, options)
        design.art_path = self._art_for(card, design, scryfall_card)
        return design

    @staticmethod
    def _fresh_design(card: BatchCard, scryfall_card: dict | None, template_id: str) -> CardDesign:
        if scryfall_card is not None:
            return design_from_scryfall(scryfall_card, template_id)
        lines = card.description.splitlines()
        return CardDesign(template_id=template_id, name=card.nickname, type_line=lines[0] if lines else "",
                          rules_text=format_imported_rules("\n".join(lines[1:])))

    def _art_for(self, card: BatchCard, design: CardDesign, scryfall_card: dict | None) -> str:
        if card.source_art_path is not None and card.source_art_path.exists():
            return str(card.source_art_path)
        if card.face_local_path is not None and self.gallery.contains(card.face_local_path):
            return str(card.face_local_path)
        if design.art_path and Path(design.art_path).exists():
            return design.art_path
        crop = self.lookup.art_crop_path(scryfall_card) if scryfall_card else None
        return str(crop) if crop else ""


def apply_batch_options(design: CardDesign, options: BatchOptions) -> None:
    if options.template_id:
        design.template_id = options.template_id
    if options.artist:
        design.artist = options.artist
    if not options.apply_fullart_chrome:
        return
    design.plate_style_id = options.plate_style_id
    design.plate_texture_id = options.plate_texture_id
    design.chrome_mode = options.chrome_mode
    design.title_piece_path = options.title_piece_path
    design.subtitle_piece_path = options.subtitle_piece_path
    design.type_piece_path = options.type_piece_path
    design.text_piece_path = options.text_piece_path
    design.head_opacity = options.opacity
    design.body_opacity = options.opacity
