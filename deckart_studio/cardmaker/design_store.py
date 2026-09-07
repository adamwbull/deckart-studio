from pathlib import Path

from deckart_studio.cardmaker.card_design import CardDesign
from deckart_studio.original_art.original_art import sanitize_card_name

RENDERED_FOLDER_NAME = "rendered"
DESIGN_SUFFIX = ".design.json"


class DesignStore:
    """Where rendered card faces and their editable designs live: DeckArt/rendered/<deck>/<nn>-<name>.png."""

    def __init__(self, deck_art_root: Path):
        self.root = Path(deck_art_root) / RENDERED_FOLDER_NAME

    def render_path(self, deck_name: str, card_index: int, card_name: str) -> Path:
        folder = self.root / sanitize_card_name(deck_name)
        return folder / f"{card_index + 1:03d}-{sanitize_card_name(card_name) or 'card'}.png"

    @staticmethod
    def design_path_for(render_path: Path) -> Path:
        return render_path.with_name(render_path.stem + DESIGN_SUFFIX)

    def load_design_for_face(self, face_path: Path | None) -> CardDesign | None:
        if face_path is None:
            return None
        design_path = self.design_path_for(face_path)
        return CardDesign.load(design_path) if design_path.exists() else None

    def save(self, design: CardDesign, render_path: Path) -> None:
        design.save(self.design_path_for(render_path))
