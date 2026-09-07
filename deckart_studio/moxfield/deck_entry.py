import re
from dataclasses import dataclass

DECKLIST_LINE = re.compile(
    r"^\s*(?P<quantity>\d+)x?\s+(?P<name>.+?)(?:\s+\((?P<set>[A-Za-z0-9]{2,6})\)(?:\s+(?P<number>[\w\-★]+))?)?"
    r"(?P<tags>(?:\s+\*[A-Za-z]+\*)*)\s*$"
)
COMMANDER_LINE_TAG = "*CMDR*"
MOXFIELD_DECK_URL = re.compile(r"moxfield\.com/decks/(?P<public_id>[A-Za-z0-9_\-]+)", re.IGNORECASE)


@dataclass
class DeckEntry:
    """A requested card from a deck list: how many, which name, and optionally which printing."""

    name: str
    quantity: int = 1
    set_code: str = ""
    collector_number: str = ""
    scryfall_id: str = ""
    board: str = "mainboard"

    def scryfall_identifier(self) -> dict:
        if self.scryfall_id:
            return {"id": self.scryfall_id}
        if self.set_code:
            return {"name": self.scryfall_name(), "set": self.set_code.lower()}
        return self.fallback_identifier()

    def fallback_identifier(self) -> dict:
        return {"name": self.scryfall_name()}

    def scryfall_name(self) -> str:
        return self.name.replace(" // ", " / ").split(" / ")[0].strip()


def parse_moxfield_public_id(text: str) -> str | None:
    match = MOXFIELD_DECK_URL.search(text)
    return match.group("public_id") if match else None


def parse_decklist_text(text: str) -> list[DeckEntry]:
    entries: list[DeckEntry] = []
    board = "mainboard"
    for line in text.splitlines():
        board = detect_board_header(line, board)
        entry = parse_decklist_line(line, board)
        if entry is not None:
            entries.append(entry)
    return entries


def detect_board_header(line: str, current_board: str) -> str:
    header = line.strip().lower()
    if header in {"commander", "commanders"}:
        return "commanders"
    if header in {"deck", "mainboard", "main"}:
        return "mainboard"
    if header in {"maybeboard", "considering"}:
        return "maybeboard"
    if header in {"tokens", "token"}:
        return "tokens"
    if header == "sideboard" or is_unrecognized_section_header(line):
        return "sideboard"
    return current_board


def is_unrecognized_section_header(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and stripped.isupper() and not stripped[0].isdigit()


def parse_decklist_line(line: str, board: str) -> DeckEntry | None:
    match = DECKLIST_LINE.match(line)
    if not match:
        return None
    return DeckEntry(
        name=match.group("name").strip(),
        quantity=int(match.group("quantity")),
        set_code=(match.group("set") or "").lower(),
        collector_number=match.group("number") or "",
        board="commanders" if COMMANDER_LINE_TAG in (match.group("tags") or "").upper() else board,
    )
