from pathlib import Path

DECK_MARKERS = ('"CardCustom"', '"Card"', '"Deck"', '"DeckCustom"')


def discover_deck_files(folder: Path) -> list[Path]:
    folder = Path(folder)
    if not folder.exists():
        return []
    return sorted((path for path in folder.rglob("*.json") if looks_like_card_save(path)),
                  key=lambda path: path.name.lower())


def looks_like_card_save(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        return False
    return '"ObjectStates"' in text and any(marker in text for marker in DECK_MARKERS)


def sanitize_file_stem(name: str) -> str:
    allowed = "".join(character if character.isalnum() or character in " -_." else " " for character in name)
    return "-".join(part.strip("-") for part in allowed.split() if part.strip("-")) or "deck"


def unique_save_path(folder: Path, stem: str) -> Path:
    candidate = folder / f"{stem}.json"
    counter = 2
    while candidate.exists():
        candidate = folder / f"{stem}-{counter}.json"
        counter += 1
    return candidate
