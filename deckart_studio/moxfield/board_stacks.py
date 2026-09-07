"""How Moxfield board names fold into the stacks that spawn in Tabletop Simulator."""
import re

from deckart_studio.moxfield.deck_entry import DeckEntry
from deckart_studio.tts.board import COMMANDER_TAG, commander_stack_name

MAIN_DECK_BOARDS = ("mainboard",)
COMMANDER_BOARDS = ("commanders", "signatureSpells")
STACK_ORDER = ("main", "commander", "companions", "sideboard", "maybeboard", "tokens")
STACK_LABELS = {"companions": "Companion", "sideboard": "Sideboard", "maybeboard": "Maybeboard", "tokens": "Tokens"}


def stack_key_for_board(board: str) -> str:
    if board in MAIN_DECK_BOARDS:
        return "main"
    if board in COMMANDER_BOARDS:
        return "commander"
    return board


def stack_label(stack_key: str, deck_name: str, card_count: int = 1) -> str:
    if stack_key == "main":
        return deck_name
    if stack_key == "commander":
        return commander_stack_name(card_count)
    return STACK_LABELS.get(stack_key) or humanize_board_name(stack_key)


def stack_tags(stack_key: str) -> tuple[str, ...]:
    return (COMMANDER_TAG,) if stack_key == "commander" else ()


def humanize_board_name(board: str) -> str:
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", board)
    return spaced[:1].upper() + spaced[1:]


def group_entries_by_stack(entries: list[DeckEntry]) -> dict[str, list[DeckEntry]]:
    """Ordered mapping of stack key -> entries: main deck, commanders, then the well-known boards, then the rest."""
    grouped: dict[str, list[DeckEntry]] = {}
    for entry in entries:
        grouped.setdefault(stack_key_for_board(entry.board), []).append(entry)
    ordered_keys = [key for key in STACK_ORDER if key in grouped] + sorted(key for key in grouped if key not in STACK_ORDER)
    return {key: grouped[key] for key in ordered_keys}
