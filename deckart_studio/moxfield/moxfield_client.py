from dataclasses import dataclass, field

from deckart_studio.moxfield.deck_entry import DeckEntry
from deckart_studio.net import BROWSER_USER_AGENT, fetch_json

MOXFIELD_API = "https://api2.moxfield.com/v3/decks/all"
TOKENS_BOARD = "tokens"


@dataclass
class MoxfieldDeck:
    name: str
    entries: list[DeckEntry] = field(default_factory=list)


def fetch_moxfield_deck(public_id: str) -> MoxfieldDeck:
    raw = fetch_json(f"{MOXFIELD_API}/{public_id}", user_agent=BROWSER_USER_AGENT)
    entries = entries_from_boards(raw.get("boards", {})) + entries_from_tokens(raw.get("tokens", []))
    return MoxfieldDeck(name=raw.get("name") or public_id, entries=entries)


def entries_from_boards(boards: dict) -> list[DeckEntry]:
    entries: list[DeckEntry] = []
    for board_name, board in boards.items():
        cards = board.get("cards", {}) if isinstance(board, dict) else {}
        entries.extend(entry_from_board_card(board_name, card) for card in cards.values())
    return entries


def entries_from_tokens(tokens: list[dict]) -> list[DeckEntry]:
    """Moxfield lists every related object under "tokens"; keep the true tokens, one copy each."""
    unique: dict[str, dict] = {}
    for token in tokens:
        if token.get("isToken") and token.get("scryfall_id"):
            unique.setdefault(token["scryfall_id"], token)
    return [entry_from_card(TOKENS_BOARD, card, 1) for card in unique.values()]


def entry_from_board_card(board_name: str, board_card: dict) -> DeckEntry:
    return entry_from_card(board_name, board_card.get("card", {}), int(board_card.get("quantity", 1)))


def entry_from_card(board_name: str, card: dict, quantity: int) -> DeckEntry:
    return DeckEntry(
        name=card.get("name", "Unknown"),
        quantity=quantity,
        set_code=card.get("set", ""),
        collector_number=str(card.get("cn", "")),
        scryfall_id=card.get("scryfall_id", ""),
        board=board_name,
    )
