from pathlib import Path

from deckart_studio.image_source import is_image_file

FILENAME_ALIASES = {
    "everythingturnstodust": "Everything Comes to Dust",
    "dinosaurs": "Dinosaurs on a Spaceship",
    "evolving": "Evolving Wilds",
    "atraxi": "Atraxi Warden",
    "tenthdoctor": "The Tenth Doctor",
    "eleventhdoctor": "The Eleventh Doctor",
    "theninthdoctor": "The Ninth Doctor",
    "theseconddoctor": "The Second Doctor",
    "thewardoctor": "The War Doctor",
    "rosetyler": "Rose Tyler",
    "factorfiction": "Fact or Fiction",
    "blasphemousact1": "Blasphemous Act",
    "asfortold": "As Foretold",
    "frostboisnarl": "Frostboil Snarl",
    "idrisssouloftardis": "Idris, Soul of the TARDIS",
    "mysticmonastary": "Mystic Monastery",
    "excoticorchard": "Exotic Orchard",
    "faceofboe": "The Face of Boe",
    "girlinthefireplace": "The Girl in the Fireplace",
    "themoment": "The Moment",
    "thepandorica": "The Pandorica",
    "thepartingofways": "The Parting of the Ways",
    "thespianstage": "Thespian's Stage",
    "weddingofriversong": "The Wedding of River Song",
    "timebeetle": "Time Beetle",
    "trenzaloreclocktower": "Trenzalore Clocktower",
    "warroom": "War Room",
    "tardis": "TARDIS",
    "gallifreyfallsnomore": "Gallifrey Falls // No More",
    "weartear": "Wear // Tear",
}


def normalize_key(text: str) -> str:
    return "".join(character for character in text.lower() if character.isalnum())


GENERATED_STYLE_MARKERS = ("-western-anime", "-photorealistic-cinematic")


def file_key(path: Path) -> str:
    stem = path.stem.lower()
    if stem.endswith("(1)"):
        stem = stem[:-3]
    for marker in GENERATED_STYLE_MARKERS:
        index = stem.find(marker)
        if index > 0:
            stem = stem[:index]
            break
    return normalize_key(stem)


def card_keys(name: str) -> list[str]:
    base = normalize_key(name)
    keys = [base]
    if base.startswith("the"):
        keys.append(base[3:])
    return keys


def match_image_to_card(image: Path, card_names: list[str]) -> str | None:
    key = file_key(image)
    if key in FILENAME_ALIASES:
        return FILENAME_ALIASES[key]
    exact = {normalize_key(name): name for name in card_names}
    if key in exact:
        return exact[key]
    best_name = None
    best_score = 0
    for name in card_names:
        for card_key in card_keys(name):
            if key == card_key:
                return name
            if len(card_key) >= 5 and (key.startswith(card_key) or key.endswith(card_key)
                                       or card_key.endswith(key)):
                score = min(len(card_key), len(key))
                if score > best_score:
                    best_name, best_score = name, score
    return best_name if best_score >= 5 else None


def match_images(folder: Path, card_names: list[str]) -> dict[str, Path]:
    matches: dict[str, Path] = {}
    newest: dict[str, float] = {}
    for image in sorted(Path(folder).iterdir()):
        if not image.is_file() or not is_image_file(image):
            continue
        name = match_image_to_card(image, card_names)
        if name is None:
            continue
        stamp = image.stat().st_mtime
        if name not in matches or stamp > newest[name]:
            matches[name] = image
            newest[name] = stamp
    return matches


def missing_card_names(folder: Path, card_names: list[str]) -> list[str]:
    matches = match_images(folder, card_names)
    return sorted(name for name in card_names if name not in matches)
