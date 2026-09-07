import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterator

from deckart_studio.hosting.tts_compat import is_tts_unreachable
from deckart_studio.image_source import clean_tts_url, tts_safe_url, url_to_local_path
from deckart_studio.settings import backup_directory
from deckart_studio.tts.board import (
    COMMANDER_STACK_NAMES,
    COMMANDER_TAG,
    LOOSE_CARDS_BOARD_NAME,
    Board,
    commander_stack_name,
    stack_display_name,
)
from deckart_studio.tts.card_face import (
    CARD_OBJECT_NAMES,
    CARDS_PER_SHEET_ID,
    DECK_OBJECT_NAMES,
    CardFace,
)
from deckart_studio.tts.object_factory import (
    STACK_SPACING_X,
    BuiltCard,
    build_card_object,
    build_deck_object,
    single_image_sheet,
)

IMAGE_URL_FIELDS = ("FaceURL", "BackURL")


class DeckDocument:
    """A loaded Tabletop Simulator saved object whose stacks and card faces can be rewritten."""

    def __init__(self, path: Path, raw: dict):
        self.path = Path(path)
        self.raw = raw
        self.dirty = False
        self._backed_up = False

    @staticmethod
    def load(path: Path) -> "DeckDocument":
        raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        return DeckDocument(path, raw)

    @property
    def name(self) -> str:
        return self.path.stem

    def cards(self) -> list[CardFace]:
        faces: list[CardFace] = []
        for state in self.raw.get("ObjectStates", []):
            self._collect_faces(state, faces)
        return faces

    def _collect_faces(self, state: dict, faces: list[CardFace]) -> None:
        object_name = state.get("Name", "")
        if object_name in CARD_OBJECT_NAMES:
            faces.append(CardFace(len(faces), state, None, 0))
        elif object_name in DECK_OBJECT_NAMES:
            for position, contained in enumerate(state.get("ContainedObjects", [])):
                faces.append(CardFace(len(faces), contained, state, position))

    def boards(self) -> list[Board]:
        """Every stack in the save, in file order, with loose top-level cards gathered into one trailing board."""
        boards = [self._board_for_deck(state, ordinal) for ordinal, state in enumerate(self._deck_states(), start=1)]
        loose = self._loose_board()
        if loose.cards:
            boards.append(loose)
        return boards

    def _deck_states(self) -> list[dict]:
        return [state for state in self.raw.get("ObjectStates", []) if state.get("Name", "") in DECK_OBJECT_NAMES]

    def _board_for_deck(self, state: dict, ordinal: int) -> Board:
        cards = [CardFace(position, contained, state, position)
                 for position, contained in enumerate(state.get("ContainedObjects", []))]
        return Board(stack_display_name(state, ordinal), state, cards)

    def _loose_board(self) -> Board:
        loose_states = [state for state in self.raw.get("ObjectStates", []) if state.get("Name", "") in CARD_OBJECT_NAMES]
        return Board(LOOSE_CARDS_BOARD_NAME, None, [CardFace(index, state, None, 0) for index, state in enumerate(loose_states)])

    def add_board(self, name: str, tags: tuple[str, ...] = (), beside_main: bool = False) -> Board:
        state = build_deck_object(name, [], position_x=STACK_SPACING_X * len(self._deck_states()), tags=tags)
        states = self.raw.setdefault("ObjectStates", [])
        states.insert(self._index_after_main_deck(), state) if beside_main else states.append(state)
        self.dirty = True
        return Board(name, state, [])

    def _index_after_main_deck(self) -> int:
        states = self.raw.get("ObjectStates", [])
        main = next((index for index, state in enumerate(states) if state.get("Name", "") in DECK_OBJECT_NAMES), -1)
        return main + 1

    def commander_board(self) -> Board | None:
        return next((board for board in self.boards() if board.is_commander), None)

    def split_commanders(self, cards: list[CardFace]) -> Board:
        """Move the given cards into the commander stack, creating it right after the main deck when needed."""
        target = self.commander_board() or self.add_board(commander_stack_name(len(cards)), (COMMANDER_TAG,), beside_main=True)
        for card in cards:
            self.move_card(card, target)
        if target.name.lower() in COMMANDER_STACK_NAMES:
            self.rename_board(target, commander_stack_name(len(target.container.get("ContainedObjects", []))))
        return target

    def rename_board(self, board: Board, name: str) -> None:
        if board.container is not None:
            board.container["Nickname"] = name
            self.dirty = True

    def delete_board(self, board: Board) -> None:
        states = self.raw.get("ObjectStates", [])
        if board.container is not None:
            states.remove(board.container)
        else:
            states[:] = [state for state in states if state.get("Name", "") not in CARD_OBJECT_NAMES]
        self.dirty = True

    def add_card(self, board: Board, built: BuiltCard) -> None:
        card_object = build_card_object(self._next_free_sheet_id(), built, board.common_back_url())
        self._attach_card_state(board, card_object)
        self.dirty = True

    def remove_card(self, card: CardFace) -> None:
        if card.parent_deck is not None:
            self._detach_from_deck(card)
        else:
            self.raw.get("ObjectStates", []).remove(card.state)
        self.dirty = True

    def move_card(self, card: CardFace, target: Board) -> None:
        self.remove_card(card)
        self._attach_card_state(target, card.state)

    def _attach_card_state(self, board: Board, card_object: dict) -> None:
        if board.container is None:
            self.raw.setdefault("ObjectStates", []).append(card_object)
            return
        board.container.setdefault("ContainedObjects", []).append(card_object)
        board.container.setdefault("DeckIDs", []).append(int(card_object.get("CardID", 0)))
        for sheet_id, sheet in card_object.get("CustomDeck", {}).items():
            board.container.setdefault("CustomDeck", {})[sheet_id] = dict(sheet)

    def _detach_from_deck(self, card: CardFace) -> None:
        parent = card.parent_deck
        contained = parent.get("ContainedObjects", [])
        position = next(index for index, state in enumerate(contained) if state is card.state)
        del contained[position]
        deck_ids = parent.get("DeckIDs", [])
        if position < len(deck_ids):
            del deck_ids[position]
        self._prune_unreferenced_parent_sheets(parent)

    def set_face(self, card: CardFace, url: str) -> None:
        if self._has_private_sheet(card):
            self._write_sheet_field(card, "FaceURL", url)
        else:
            self._move_to_new_sheet(card, url)
        self.dirty = True

    def set_all_faces(self, url: str) -> None:
        for card in self.cards():
            self.set_face(card, url)

    def set_all_backs(self, url: str) -> None:
        for card in self.cards():
            self._write_sheet_field(card, "BackURL", url)
        self.dirty = True

    def image_urls(self) -> set[str]:
        return {clean_tts_url(value) for value in iter_image_url_values(self.raw)}

    def local_image_paths(self) -> list[Path]:
        paths = (url_to_local_path(url) for url in sorted(self.image_urls()))
        return [path for path in paths if path is not None]

    def unreachable_image_urls(self) -> list[str]:
        return sorted(url for url in self.image_urls() if is_tts_unreachable(url))

    def unpublished_image_urls(self) -> list[str]:
        """Every image link TTS cannot show to other players: files on this PC plus hosts TTS cannot reach."""
        return sorted(url for url in self.image_urls() if url_to_local_path(url) is not None or is_tts_unreachable(url))

    def sanitize_image_urls(self) -> int:
        """Rewrite remote image links into the form TTS can load (no cache-buster queries); returns how many changed."""
        return self.replace_image_urls({url: tts_safe_url(url) for url in self.image_urls() if tts_safe_url(url) != url})

    def replace_image_urls(self, replacements: dict[str, str]) -> int:
        replaced = 0
        for holder, field in iter_image_url_fields(self.raw):
            new_value = replacements.get(clean_tts_url(holder[field]))
            if new_value and new_value != holder[field]:
                holder[field] = new_value
                replaced += 1
        self.dirty = self.dirty or replaced > 0
        return replaced

    def save(self) -> None:
        self._drop_empty_decks()
        self._backup_original_once()
        self.path.write_text(json.dumps(self.raw, indent=2), encoding="utf-8")
        self.dirty = False

    def save_as(self, path: Path) -> None:
        self.path = Path(path)
        self._backed_up = True
        self.save()

    def _drop_empty_decks(self) -> None:
        states = self.raw.get("ObjectStates", [])
        states[:] = [state for state in states if not is_empty_deck(state)]

    def _has_private_sheet(self, card: CardFace) -> bool:
        return card.is_single_image_sheet() and self._sheet_reference_count(card.sheet_id) == 1

    def _sheet_reference_count(self, sheet_id: int) -> int:
        return sum(1 for other in self.cards() if other.sheet_id == sheet_id)

    def _write_sheet_field(self, card: CardFace, field: str, value: str) -> None:
        card.sheet[field] = value
        if card.parent_deck is not None:
            parent_sheet = card.parent_deck.setdefault("CustomDeck", {}).setdefault(str(card.sheet_id), {})
            parent_sheet[field] = value

    def _move_to_new_sheet(self, card: CardFace, url: str) -> None:
        new_sheet_id = self._next_free_sheet_id()
        new_sheet = single_image_sheet(url, card.sheet)
        card.state["CustomDeck"] = {str(new_sheet_id): new_sheet}
        card.state["CardID"] = new_sheet_id * CARDS_PER_SHEET_ID
        if card.parent_deck is not None:
            self._register_sheet_in_parent(card, new_sheet_id, new_sheet)

    def _register_sheet_in_parent(self, card: CardFace, sheet_id: int, sheet: dict) -> None:
        parent = card.parent_deck
        parent.setdefault("CustomDeck", {})[str(sheet_id)] = dict(sheet)
        deck_ids = parent.setdefault("DeckIDs", [])
        while len(deck_ids) <= card.position_in_parent:
            deck_ids.append(0)
        deck_ids[card.position_in_parent] = sheet_id * CARDS_PER_SHEET_ID
        self._prune_unreferenced_parent_sheets(parent)

    def _prune_unreferenced_parent_sheets(self, parent: dict) -> None:
        referenced = {str(int(contained.get("CardID", 0)) // CARDS_PER_SHEET_ID)
                      for contained in parent.get("ContainedObjects", [])}
        custom_deck = parent.get("CustomDeck", {})
        for sheet_id in list(custom_deck.keys()):
            if sheet_id not in referenced:
                del custom_deck[sheet_id]

    def _next_free_sheet_id(self) -> int:
        used = {card.sheet_id for card in self.cards()}
        for state in self.raw.get("ObjectStates", []):
            used.update(int(key) for key in state.get("CustomDeck", {}).keys())
        return max(used, default=0) + 1

    def _backup_original_once(self) -> None:
        if self._backed_up or not self.path.exists():
            return
        backup_directory().mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(self.path, backup_directory() / f"{self.path.stem}-{stamp}.json")
        self._backed_up = True


def is_empty_deck(state: dict) -> bool:
    return state.get("Name", "") in DECK_OBJECT_NAMES and not state.get("ContainedObjects")


def iter_image_url_fields(node) -> Iterator[tuple[dict, str]]:
    """Yield (dict, key) for every FaceURL/BackURL anywhere in the saved object."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in IMAGE_URL_FIELDS and isinstance(value, str):
                yield node, key
            else:
                yield from iter_image_url_fields(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_image_url_fields(item)


def iter_image_url_values(node) -> Iterator[str]:
    return (holder[field] for holder, field in iter_image_url_fields(node) if holder[field])
