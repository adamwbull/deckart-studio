from dataclasses import dataclass
from pathlib import Path

from deckart_studio.image_source import ImageSource


@dataclass(frozen=True)
class OriginalArt:
    """One official printing face of a card, available remotely and possibly cached locally."""

    name: str
    face_name: str
    set_code: str
    collector_number: str
    scryfall_id: str
    face_index: int
    image_url: str
    type_line: str = ""
    oracle_text: str = ""
    local_file: Path | None = None

    def display_label(self) -> str:
        return f"{self.face_name} ({self.set_code.upper()} {self.collector_number})"

    def suggested_filename(self) -> str:
        suffix = "_back" if self.face_index else ""
        return f"{self.set_code}_{self.collector_number}_{sanitize_card_name(self.face_name)}{suffix}.jpg"

    def description_text(self) -> str:
        return "\n".join(part for part in (self.type_line, self.oracle_text) if part)

    def to_image_source(self) -> ImageSource:
        return ImageSource(local_path=self.local_file, remote_url=self.image_url, label=self.display_label())


def sanitize_card_name(name: str) -> str:
    replaced = name.replace("//", "--")
    kept = "".join(character for character in replaced if character.isalnum() or character in " -")
    return "-".join(kept.split())


def normalize_card_name(name: str) -> str:
    return name.split("//")[0].strip().lower()
