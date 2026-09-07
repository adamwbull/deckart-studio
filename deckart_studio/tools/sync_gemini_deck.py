"""Render gemini folder art as Clear Art card faces and wire them into a TTS deck save."""
import argparse
from pathlib import Path

from deckart_studio.gemini.sync import add_elephant_token, sync_gemini_deck
from deckart_studio.settings import AppSettings

DEFAULT_DECK = Path.home() / "OneDrive/Documents/My Games/Tabletop Simulator/Saves/Saved Objects/The-Moment-1.4.json"
DEFAULT_GEMINI = Path("D:/MTG/DeckArt/doctorwho/gemini")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deck", type=Path, default=DEFAULT_DECK)
    parser.add_argument("--gemini", type=Path, default=DEFAULT_GEMINI)
    parser.add_argument("--template", default="clearart")
    parser.add_argument("--artist", default="")
    parser.add_argument("--missing-only", action="store_true")
    parser.add_argument("--skip-elephant", action="store_true")
    args = parser.parse_args()
    if args.missing_only:
        missing = list_missing_gemini_art(args.deck, args.gemini)
        print(f"Missing gemini art ({len(missing)}):")
        for name in missing:
            print(f"  {name}")
        return 0
    artist = args.artist.strip() or AppSettings.load().last_artist_credit.strip() or None
    stats = sync_gemini_deck(args.deck, args.gemini, args.template, artist)
    print(f"Matched {stats['matched']} cards, rendered {stats['rendered']} faces.")
    print(f"Still missing gemini art ({len(stats['missing'])}):")
    for name in stats["missing"]:
        print(f"  {name}")
    if not args.skip_elephant:
        add_elephant_token(args.deck, args.template, artist)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
