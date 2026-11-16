import os
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import QApplication

from deckart_studio.cardmaker.asset_library import CardAssetLibrary
from deckart_studio.cardmaker.card_design import design_from_scryfall
from deckart_studio.cardmaker.card_lookup import CardLookup
from deckart_studio.cardmaker.card_renderer import EXPORT_SCALE, CardRenderer
from deckart_studio.cardmaker.deck_batch import BatchCard, BatchOptions, DeckFaceBatch
from deckart_studio.cardmaker.design_store import DesignStore
from deckart_studio.cardmaker.token_lookup import lookup_token_card
from deckart_studio.gallery.gallery_library import GalleryLibrary
from deckart_studio.gemini.matching import match_images, missing_card_names
from deckart_studio.image_source import local_path_to_url
from deckart_studio.moxfield.deck_importer import built_card_from_scryfall
from deckart_studio.original_art.scryfall_client import ScryfallClient
from deckart_studio.settings import AppSettings
from deckart_studio.tts.deck_document import DeckDocument
from deckart_studio.tts.object_factory import BuiltCard

DEFAULT_TEMPLATE_ID = "clearart"
ProgressCallback = Callable[[str], None]


def ensure_qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication([])
    return app


def render_scope_name(deck_name: str, board_index: int, board_name: str) -> str:
    if board_index <= 0:
        return deck_name
    return f"{deck_name} - {board_name}"


def sync_gemini_deck(deck_path: Path, gemini_folder: Path, template_id: str = DEFAULT_TEMPLATE_ID,
                     artist: str | None = None, report: ProgressCallback = print) -> dict[str, object]:
    ensure_qt_app()
    settings = AppSettings.load()
    document = DeckDocument.load(deck_path)
    boards = document.boards()
    deck_name = document.name
    card_names = sorted({name for board in boards for card in board.cards
                         for name in (card.nickname, card.oracle_name)})
    matches = match_images(gemini_folder, card_names)
    if not matches:
        report("No gemini images matched any card in the deck.")
        return {"matched": 0, "rendered": 0, "missing": missing_card_names(gemini_folder, card_names)}

    batch_cards: list[BatchCard] = []
    for board_index, board in enumerate(boards):
        scope = render_scope_name(deck_name, board_index, board.name)
        for card in board.cards:
            art = matches.get(card.nickname) or matches.get(card.oracle_name)
            if art is None:
                continue
            batch_cards.append(BatchCard(board_index, card.index, card.nickname, card.description,
                                         None, scope, source_art_path=art, oracle_name=card.oracle_name))

    assets = CardAssetLibrary().load()
    store = DesignStore(settings.deck_art_root())
    batch = DeckFaceBatch(CardLookup(ScryfallClient()), CardRenderer(assets), store, GalleryLibrary(settings))
    report(f"Rendering {len(batch_cards)} Clear Art faces from {len(matches)} gemini images…")
    rendered = batch.run(batch_cards, BatchOptions(template_id=template_id, artist=artist), report)

    for face in rendered:
        board = boards[face.board_index]
        document.set_face(board.cards[face.index], local_path_to_url(face.path))

    document.save()
    unmatched = sorted({
        card.nickname for board in boards for card in board.cards
        if card.nickname not in matches and card.oracle_name not in matches
    })
    return {"matched": len(matches), "rendered": len(rendered), "missing": unmatched}


def list_missing_gemini_art(deck_path: Path, gemini_folder: Path) -> list[str]:
    document = DeckDocument.load(deck_path)
    cards = [card for board in document.boards() for card in board.cards]
    names = [name for card in cards for name in (card.nickname, card.oracle_name)]
    matches = match_images(gemini_folder, names)
    return sorted({
        card.nickname for card in cards
        if card.nickname not in matches and card.oracle_name not in matches
    })


def add_elephant_token(deck_path: Path, template_id: str = DEFAULT_TEMPLATE_ID,
                       artist: str | None = None, report: ProgressCallback = print) -> bool:
    ensure_qt_app()
    document = DeckDocument.load(deck_path)
    tokens_index = next((index for index, board in enumerate(document.boards()) if board.name.lower() == "tokens"), None)
    if tokens_index is None:
        report("No Tokens stack found in the deck.")
        return False
    tokens_board = document.boards()[tokens_index]
    if any(card.nickname == "Elephant" for card in tokens_board.cards):
        report("Elephant token already present.")
        return False

    scryfall = ScryfallClient()
    token_card = lookup_token_card(scryfall, "Elephant", "Token Creature — Elephant\n")
    if token_card is None:
        report("Could not build Elephant token from Scryfall.")
        return False
    built = built_card_from_scryfall(token_card)
    if built is None:
        report("Could not build Elephant token from Scryfall.")
        return False

    settings = AppSettings.load()
    store = DesignStore(settings.deck_art_root())
    renderer = CardRenderer(CardAssetLibrary().load())
    scope = render_scope_name(document.name, tokens_index, tokens_board.name)
    index = len(tokens_board.cards)
    design = design_from_scryfall(token_card, template_id)
    if artist:
        design.artist = artist
    art_path = CardLookup(scryfall).art_crop_path(token_card)
    if art_path is not None:
        design.art_path = str(art_path)
    render_path = store.render_path(scope, index, design.name or "Elephant")
    render_path.parent.mkdir(parents=True, exist_ok=True)
    renderer.render(design, EXPORT_SCALE).save(str(render_path), "PNG")
    store.save(design, render_path)

    built = BuiltCard("Elephant", built.description, local_path_to_url(render_path))
    document.add_card(tokens_board, built)
    document.save()
    report("Added green 3/3 Elephant token to the Tokens stack.")
    return True
