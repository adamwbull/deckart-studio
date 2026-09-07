import json
from pathlib import Path

from deckart_studio.original_art.original_art import OriginalArt, normalize_card_name

INDEX_FILENAME = "index.json"


class OriginalArtIndex:
    """The locally downloaded catalog of official card faces, keyed by card name."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._by_name: dict[str, list[OriginalArt]] = {}

    def reload(self) -> None:
        self._by_name = {}
        for entry in self._read_entries():
            art = self._entry_to_art(entry)
            if art is not None:
                self._register(art)

    def find(self, card_name: str) -> list[OriginalArt]:
        return list(self._by_name.get(normalize_card_name(card_name), []))

    def all_arts(self) -> list[OriginalArt]:
        unique = {(art.scryfall_id, art.face_index, art.image_url): art
                  for arts in self._by_name.values() for art in arts}
        return list(unique.values())

    def count(self) -> int:
        return len(self.all_arts())

    def _read_entries(self) -> list[dict]:
        index_path = self.root / INDEX_FILENAME
        if not index_path.exists():
            return []
        try:
            return json.loads(index_path.read_text(encoding="utf-8")).get("cards", [])
        except (OSError, ValueError):
            return []

    def _entry_to_art(self, entry: dict) -> OriginalArt | None:
        relative_file = entry.get("file")
        if not relative_file or not entry.get("name"):
            return None
        local_file = self.root / relative_file
        return OriginalArt(
            name=entry["name"],
            face_name=entry.get("face_name") or entry["name"],
            set_code=entry.get("set", ""),
            collector_number=str(entry.get("collector_number", "")),
            scryfall_id=entry.get("scryfall_id", ""),
            face_index=int(entry.get("face", 0)),
            image_url=entry.get("image_url", ""),
            type_line=entry.get("type_line", ""),
            oracle_text=entry.get("oracle_text", ""),
            local_file=local_file if local_file.exists() else None,
        )

    def _register(self, art: OriginalArt) -> None:
        keys = {normalize_card_name(art.name), normalize_card_name(art.face_name)}
        for key in keys:
            self._by_name.setdefault(key, []).append(art)
