from pathlib import Path

from deckart_studio.gallery.thumbnail_loader import remote_cache_path
from deckart_studio.net import download_file
from deckart_studio.original_art.original_art import normalize_card_name
from deckart_studio.original_art.scryfall_client import ScryfallClient


class CardLookup:
    """Resolves card names to Scryfall card data in bulk and fetches their art crops locally."""

    def __init__(self, scryfall: ScryfallClient):
        self.scryfall = scryfall

    def lookup_many(self, names: list[str]) -> dict[str, dict]:
        unique_names = list(dict.fromkeys(normalize_card_name(name) for name in names if name.strip()))
        found, _missing = self.scryfall.collection([{"name": name} for name in unique_names])
        return {key: card for card in found for key in card_name_keys(card)}

    @staticmethod
    def art_crop_path(card: dict) -> Path | None:
        url = art_crop_url(card)
        if not url:
            return None
        return download_file(url, remote_cache_path(url))


def card_name_keys(card: dict) -> set[str]:
    keys = {normalize_card_name(card.get("name", ""))}
    keys.update(normalize_card_name(face.get("name", "")) for face in card.get("card_faces", []))
    return {key for key in keys if key}


def art_crop_url(card: dict) -> str:
    faces = card.get("card_faces") or []
    source = card if "image_uris" in card else (faces[0] if faces else card)
    return source.get("image_uris", {}).get("art_crop", "")
