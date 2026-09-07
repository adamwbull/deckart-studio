from collections import Counter
from dataclasses import dataclass, field

from deckart_studio.tts.card_face import CardFace
from deckart_studio.tts.object_factory import STANDARD_CARD_BACK_URL

LOOSE_CARDS_BOARD_NAME = "Loose cards"
COMMANDER_TAG = "DeckArt-Commander"
COMMANDER_STACK_NAMES = {"commander", "commanders", "command zone"}


@dataclass
class Board:
    """One stack of cards inside a saved object: a TTS Deck, or the loose top-level cards when container is None."""

    name: str
    container: dict | None
    cards: list[CardFace] = field(default_factory=list)

    @property
    def is_loose(self) -> bool:
        return self.container is None

    @property
    def is_commander(self) -> bool:
        return self.container is not None and is_commander_state(self.container)

    def card_count(self) -> int:
        return len(self.cards)

    def common_back_url(self) -> str:
        backs = Counter(card.back_url for card in self.cards if card.back_url)
        return backs.most_common(1)[0][0] if backs else STANDARD_CARD_BACK_URL


def is_commander_state(state: dict) -> bool:
    return COMMANDER_TAG in state.get("Tags", []) or state.get("Nickname", "").strip().lower() in COMMANDER_STACK_NAMES


def commander_stack_name(card_count: int) -> str:
    return "Commanders" if card_count > 1 else "Commander"


def stack_display_name(state: dict, ordinal: int) -> str:
    return state.get("Nickname") or f"Stack {ordinal}"
