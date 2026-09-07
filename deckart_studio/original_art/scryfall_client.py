import time
from pathlib import Path
from urllib.parse import quote

from deckart_studio.image_source import tts_safe_url
from deckart_studio.net import download_file, fetch_json
from deckart_studio.original_art.original_art import OriginalArt

SCRYFALL_API = "https://api.scryfall.com"
REQUEST_SPACING_SECONDS = 0.12
COLLECTION_BATCH_SIZE = 75


class ScryfallClient:
    """Thin Scryfall API wrapper that respects the rate limit and yields OriginalArt faces."""

    def __init__(self):
        self._last_request_time = 0.0

    def search_printings(self, card_name: str) -> list[OriginalArt]:
        query = quote(f'!"{card_name}"')
        url = f"{SCRYFALL_API}/cards/search?q={query}&unique=prints&order=released&include_extras=true"
        return [art for card in self._paginate(url) for art in card_faces(card)]

    def card_by_id(self, scryfall_id: str) -> dict:
        return self._get(f"{SCRYFALL_API}/cards/{scryfall_id}")

    def named(self, card_name: str, set_code: str = "") -> dict:
        set_part = f"&set={quote(set_code)}" if set_code else ""
        try:
            return self._get(f"{SCRYFALL_API}/cards/named?exact={quote(card_name)}{set_part}")
        except Exception:
            return self._get(f"{SCRYFALL_API}/cards/named?fuzzy={quote(card_name)}")

    def autocomplete(self, partial_name: str) -> list[str]:
        if len(partial_name.strip()) < 2:
            return []
        return self._get(f"{SCRYFALL_API}/cards/autocomplete?q={quote(partial_name.strip())}").get("data", [])

    def collection(self, identifiers: list[dict]) -> tuple[list[dict], list[dict]]:
        found: list[dict] = []
        not_found: list[dict] = []
        for start in range(0, len(identifiers), COLLECTION_BATCH_SIZE):
            batch = identifiers[start:start + COLLECTION_BATCH_SIZE]
            response = self._post(f"{SCRYFALL_API}/cards/collection", {"identifiers": batch})
            found.extend(response.get("data", []))
            not_found.extend(response.get("not_found", []))
        return found, not_found

    def download_art(self, art: OriginalArt, destination_folder: Path) -> Path:
        return download_file(art.image_url, Path(destination_folder) / art.suggested_filename())

    def _paginate(self, url: str) -> list[dict]:
        cards: list[dict] = []
        next_url: str | None = url
        while next_url:
            page = self._get(next_url)
            cards.extend(page.get("data", []))
            next_url = page.get("next_page") if page.get("has_more") else None
        return cards

    def _get(self, url: str) -> dict:
        self._respect_rate_limit()
        return fetch_json(url)

    def _post(self, url: str, body: dict) -> dict:
        self._respect_rate_limit()
        return fetch_json(url, body=body)

    def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < REQUEST_SPACING_SECONDS:
            time.sleep(REQUEST_SPACING_SECONDS - elapsed)
        self._last_request_time = time.monotonic()


def card_faces(card: dict) -> list[OriginalArt]:
    if "image_uris" in card:
        return [face_art(card, card, 0)]
    return [face_art(card, face, index) for index, face in enumerate(card.get("card_faces", []))
            if "image_uris" in face]


def face_art(card: dict, face: dict, face_index: int) -> OriginalArt:
    image_uris = face.get("image_uris", {})
    return OriginalArt(
        name=card.get("name", ""),
        face_name=face.get("name", card.get("name", "")),
        set_code=card.get("set", ""),
        collector_number=str(card.get("collector_number", "")),
        scryfall_id=card.get("id", ""),
        face_index=face_index,
        image_url=tts_safe_url(image_uris.get("large") or image_uris.get("normal") or image_uris.get("png", "")),
        type_line=face.get("type_line") or card.get("type_line", ""),
        oracle_text=face.get("oracle_text") or card.get("oracle_text", ""),
    )


def front_face(card: dict) -> OriginalArt | None:
    faces = card_faces(card)
    return faces[0] if faces else None
