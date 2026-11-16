from dataclasses import dataclass

from deckart_studio.image_source import ImageSource, clean_tts_url

CARD_OBJECT_NAMES = {"Card", "CardCustom"}
DECK_OBJECT_NAMES = {"Deck", "DeckCustom"}
CARDS_PER_SHEET_ID = 100


@dataclass
class CardFace:
    """A live reference to one card inside a TTS saved object, plus its container if any."""

    index: int
    state: dict
    parent_deck: dict | None
    position_in_parent: int

    @property
    def nickname(self) -> str:
        return self.state.get("Nickname") or f"Card {self.index + 1}"

    @property
    def oracle_name(self) -> str:
        notes = (self.state.get("GMNotes") or "").strip()
        return notes or self.nickname

    @property
    def description(self) -> str:
        return self.state.get("Description") or ""

    @property
    def card_id(self) -> int:
        return int(self.state.get("CardID", 0))

    @property
    def sheet_id(self) -> int:
        return self.card_id // CARDS_PER_SHEET_ID

    @property
    def sheet(self) -> dict:
        return self.state.setdefault("CustomDeck", {}).setdefault(str(self.sheet_id), {})

    @property
    def face_url(self) -> str:
        return clean_tts_url(self.sheet.get("FaceURL", ""))

    @property
    def back_url(self) -> str:
        return clean_tts_url(self.sheet.get("BackURL", ""))

    def face_source(self) -> ImageSource:
        return ImageSource.from_tts_url(self.face_url)

    def is_single_image_sheet(self) -> bool:
        return int(self.sheet.get("NumWidth", 1)) == 1 and int(self.sheet.get("NumHeight", 1)) == 1

    def type_group(self) -> str:
        return classify_card_type(self.description)


TYPE_KEYWORDS = [
    "Land", "Creature", "Planeswalker", "Battle", "Artifact", "Enchantment", "Instant", "Sorcery",
]


def classify_card_type(description: str) -> str:
    first_lines = "\n".join(description.splitlines()[:3])
    for keyword in TYPE_KEYWORDS:
        if keyword.lower() in first_lines.lower():
            return keyword
    return "Other"
