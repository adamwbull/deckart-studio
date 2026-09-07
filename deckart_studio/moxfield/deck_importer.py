import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from deckart_studio.moxfield.board_stacks import group_entries_by_stack, stack_label, stack_tags
from deckart_studio.moxfield.deck_entry import DeckEntry, parse_decklist_text, parse_moxfield_public_id
from deckart_studio.moxfield.moxfield_client import fetch_moxfield_deck
from deckart_studio.original_art.scryfall_client import ScryfallClient, front_face
from deckart_studio.tts.deck_builder import BuiltCard, BuiltStack, build_stacks_save
from deckart_studio.tts.saved_objects import sanitize_file_stem, unique_save_path

ProgressCallback = Callable[[str], None]


@dataclass
class ImportResult:
    saved_path: Path
    deck_name: str
    card_count: int
    unresolved: list[str] = field(default_factory=list)
    first_face_url: str = ""
    stack_summary: str = ""


class DeckImporter:
    """Turns a Moxfield URL or a pasted deck list into a new TTS saved object on disk, one stack per board."""

    def __init__(self, saved_objects_folder: Path, scryfall: ScryfallClient | None = None):
        self.saved_objects_folder = Path(saved_objects_folder)
        self.scryfall = scryfall or ScryfallClient()

    def import_text(self, text: str, deck_name_override: str, report: ProgressCallback) -> ImportResult:
        deck_name, entries = self._entries_from_text(text, report)
        deck_name = deck_name_override.strip() or deck_name
        built, unresolved = self._resolve_entries(entries, report)
        stacks = self._stacks_from_built(deck_name, entries, built)
        saved_path = self._write_save(deck_name, stacks, report)
        first_face = next((card.face_url for stack in stacks for card in stack.cards), "")
        return ImportResult(saved_path, deck_name, sum(len(stack.cards) for stack in stacks), unresolved,
                            first_face, summarize_stacks(stacks))

    def _stacks_from_built(self, deck_name: str, entries: list[DeckEntry], built: dict[int, list[BuiltCard]]) -> list[BuiltStack]:
        stacks: list[BuiltStack] = []
        for stack_key, stack_entries in group_entries_by_stack(entries).items():
            cards = [card for entry in stack_entries for card in built.get(id(entry), [])]
            stacks.append(BuiltStack(stack_label(stack_key, deck_name, len(cards)), cards, stack_tags(stack_key)))
        return stacks

    def _entries_from_text(self, text: str, report: ProgressCallback) -> tuple[str, list[DeckEntry]]:
        public_id = parse_moxfield_public_id(text)
        if public_id:
            report(f"Fetching Moxfield deck {public_id}…")
            deck = fetch_moxfield_deck(public_id)
            return deck.name, deck.entries
        report("Parsing pasted deck list…")
        return "Imported Deck", parse_decklist_text(text)

    def _resolve_entries(self, entries: list[DeckEntry], report: ProgressCallback) -> tuple[dict[int, list[BuiltCard]], list[str]]:
        report(f"Resolving {len(entries)} card entries on Scryfall…")
        resolved = self._resolve_pass(entries, [entry.scryfall_identifier() for entry in entries])
        missing = [entry for entry in entries if id(entry) not in resolved]
        if missing:
            report(f"Retrying {len(missing)} entries by name only…")
            resolved.update(self._resolve_pass(missing, [entry.fallback_identifier() for entry in missing]))
        built = {id(entry): self._build_copies(entry, resolved) for entry in entries}
        unresolved = [entry.name for entry in entries if id(entry) not in resolved]
        report(f"Resolved {sum(len(copies) for copies in built.values())} cards, {len(unresolved)} unresolved.")
        return built, unresolved

    def _resolve_pass(self, entries: list[DeckEntry], identifiers: list[dict]) -> dict[int, dict]:
        found, _not_found = self.scryfall.collection(identifiers)
        return {id(entry): card for entry, card in zip_found_to_entries(entries, found)}

    def _build_copies(self, entry: DeckEntry, resolved: dict[int, dict]) -> list[BuiltCard]:
        built = built_card_from_scryfall(resolved[id(entry)]) if id(entry) in resolved else None
        return [built] * entry.quantity if built is not None else []

    def _write_save(self, deck_name: str, stacks: list[BuiltStack], report: ProgressCallback) -> Path:
        self.saved_objects_folder.mkdir(parents=True, exist_ok=True)
        saved_path = unique_save_path(self.saved_objects_folder, sanitize_file_stem(deck_name))
        saved_path.write_text(json.dumps(build_stacks_save(deck_name, stacks), indent=2), encoding="utf-8")
        report(f"Wrote {saved_path.name}")
        return saved_path


def summarize_stacks(stacks: list[BuiltStack]) -> str:
    return ", ".join(f"{stack.name}: {len(stack.cards)}" for stack in stacks if stack.cards)


def built_card_from_scryfall(card: dict) -> BuiltCard | None:
    """The BuiltCard for a Scryfall card object's front face, or None when it has no printable face."""
    face = front_face(card)
    if face is None:
        return None
    return BuiltCard(face.name, face.description_text(), face.image_url)


def zip_found_to_entries(entries: list[DeckEntry], found: list[dict]) -> list[tuple[DeckEntry, dict]]:
    """Scryfall returns found cards in request order, skipping misses; match them back by identifier."""
    remaining = list(found)
    pairs: list[tuple[DeckEntry, dict]] = []
    for entry in entries:
        match_index = index_of_matching_card(entry, remaining)
        if match_index is not None:
            pairs.append((entry, remaining.pop(match_index)))
    return pairs


def index_of_matching_card(entry: DeckEntry, cards: list[dict]) -> int | None:
    for index, card in enumerate(cards):
        if card_matches_entry(entry, card):
            return index
    return None


def card_matches_entry(entry: DeckEntry, card: dict) -> bool:
    if entry.scryfall_id:
        return card.get("id") == entry.scryfall_id
    return names_match(entry.name, card)


def names_match(requested: str, card: dict) -> bool:
    wanted = requested.lower().replace(" / ", " // ")
    wanted_front = wanted.split(" // ")[0]
    candidates = [card.get("name", "").lower()] + [face.get("name", "").lower() for face in card.get("card_faces", [])]
    return any(wanted in (candidate, candidate.split(" // ")[0]) or wanted_front == candidate.split(" // ")[0]
               for candidate in candidates)


def describe_identifier(identifier: dict) -> str:
    return identifier.get("name") or identifier.get("id") or f"{identifier.get('set')} #{identifier.get('collector_number')}"
