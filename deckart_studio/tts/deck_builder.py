from dataclasses import dataclass, field

from deckart_studio.tts.object_factory import (
    STACK_SPACING_X,
    STANDARD_CARD_BACK_URL,
    BuiltCard,
    build_card_object,
    build_deck_object,
)

__all__ = ["BuiltCard", "BuiltStack", "STANDARD_CARD_BACK_URL", "build_deck_save", "build_stacks_save"]


@dataclass
class BuiltStack:
    """A named pile of cards (main deck, sideboard, tokens…) that spawns as its own TTS deck object."""

    name: str
    cards: list[BuiltCard] = field(default_factory=list)
    tags: tuple[str, ...] = ()


def build_deck_save(deck_name: str, cards: list[BuiltCard], back_url: str = STANDARD_CARD_BACK_URL) -> dict:
    """Assemble a saved object holding a single stack; kept for callers that only have one pile of cards."""
    return build_stacks_save(deck_name, [BuiltStack(deck_name, cards)], back_url)


def build_stacks_save(deck_name: str, stacks: list[BuiltStack], back_url: str = STANDARD_CARD_BACK_URL) -> dict:
    """Assemble a saved object where every non-empty stack spawns side by side as a separate deck."""
    save = empty_save(deck_name)
    next_sheet_id = 1
    for stack_index, stack in enumerate(stack for stack in stacks if stack.cards):
        card_objects = [build_card_object(next_sheet_id + offset, card, back_url) for offset, card in enumerate(stack.cards)]
        next_sheet_id += len(card_objects)
        save["ObjectStates"].append(build_deck_object(stack.name, card_objects, STACK_SPACING_X * stack_index, stack.tags))
    return save


def empty_save(deck_name: str) -> dict:
    return {
        "SaveName": "", "Date": "", "VersionNumber": "", "GameMode": "", "GameType": "",
        "GameComplexity": "", "Tags": [], "Gravity": 0.5, "PlayArea": 0.5, "Table": "", "Sky": "",
        "Note": deck_name, "TabStates": {}, "LuaScript": "", "LuaScriptState": "", "XmlUI": "",
        "ObjectStates": [],
    }
