import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

REMINDER_TEXT = re.compile(r"(?<!\*)\([^()\n]*\)(?!\*)")

DEFAULT_TEMPLATE_ID = "fullart"
DEFAULT_LEGAL_TEXT = "Custom card — not for sale. MTG is ™ & © Wizards of the Coast."
COLOR_NAMES = {"W": "white", "U": "blue", "B": "black", "R": "red", "G": "green"}


@dataclass
class CardDesign:
    """Everything needed to render one custom card face."""

    template_id: str = DEFAULT_TEMPLATE_ID
    color_id: str = "blue"
    name: str = ""
    mana_cost: str = ""
    type_line: str = ""
    rules_text: str = ""
    power: str = ""
    toughness: str = ""
    artist: str = ""
    legal_text: str = DEFAULT_LEGAL_TEXT
    art_path: str = ""
    art_zoom: float = 1.0
    art_offset_x: float = 0.0
    art_offset_y: float = 0.0
    show_legendary_crown: bool = True
    use_custom_name: bool = False
    custom_name: str = ""
    real_name: str = ""
    plate_texture_id: str = "stone"
    plate_style_id: str = "bars"
    chrome_mode: str = "style"
    title_piece_path: str = ""
    subtitle_piece_path: str = ""
    type_piece_path: str = ""
    text_piece_path: str = ""
    head_opacity: float = 0.92
    body_opacity: float = 0.92
    center_title: bool = False
    center_subtitle: bool = True
    center_description: bool = False
    title_color: str = ""
    subtitle_color: str = ""
    type_color: str = ""
    rules_color: str = ""
    pt_color: str = ""
    artist_color: str = ""
    legal_color: str = ""
    notes: dict = field(default_factory=dict)

    def is_creature(self) -> bool:
        return bool(self.power.strip() or self.toughness.strip())

    def is_legendary(self) -> bool:
        return "legendary" in self.type_line.lower()

    def power_toughness(self) -> str:
        return f"{self.power.strip()}/{self.toughness.strip()}"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(raw: dict) -> "CardDesign":
        known = CardDesign.__dataclass_fields__.keys()
        return CardDesign(**{key: value for key, value in raw.items() if key in known})

    def save(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def load(path: Path) -> "CardDesign":
        return CardDesign.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def design_from_scryfall(card: dict, template_id: str = DEFAULT_TEMPLATE_ID) -> CardDesign:
    if is_split_card(card):
        return split_design_from_scryfall(card, template_id)
    face = front_face_data(card)
    card_name = face.get("name", card.get("name", ""))
    return CardDesign(
        template_id=template_id,
        color_id=infer_frame_color(card, face),
        name=card_name,
        real_name=card_name,
        mana_cost=face.get("mana_cost", card.get("mana_cost", "")),
        type_line=face.get("type_line", card.get("type_line", "")),
        rules_text=rules_with_flavor(face),
        power=face.get("power", ""),
        toughness=face.get("toughness", ""),
        artist=face.get("artist", card.get("artist", "")),
    )


def is_split_card(card: dict) -> bool:
    return card.get("layout") == "split" and len(card.get("card_faces") or []) >= 2


def split_design_from_scryfall(card: dict, template_id: str) -> CardDesign:
    faces = card.get("card_faces") or []
    card_name = card.get("name") or " // ".join(face.get("name", "") for face in faces)
    return CardDesign(
        template_id=template_id,
        color_id=infer_frame_color(card, faces[0]),
        name=card_name,
        real_name=card_name,
        mana_cost=join_split_values(face.get("mana_cost", "") for face in faces),
        type_line=join_split_values(face.get("type_line", "") for face in faces),
        rules_text=split_rules_text(faces),
        artist=card.get("artist", faces[0].get("artist", "")),
    )


def join_split_values(values) -> str:
    return " // ".join(value for value in values if value)


def split_rules_text(faces: list[dict]) -> str:
    blocks: list[str] = []
    fuse_text = ""
    for face in faces:
        rules = rules_with_flavor(face)
        fuse_index = rules.find("Fuse (")
        if fuse_index >= 0:
            body = rules[:fuse_index].strip()
            fuse_text = rules[fuse_index:].strip()
        else:
            body = rules
        name = face.get("name", "")
        blocks.append(f"{name} — {body}" if name and body else body or name)
    text = "\n\n".join(block for block in blocks if block)
    return f"{text}\n\n{fuse_text}" if fuse_text else text


def custom_display_title(design: CardDesign) -> tuple[str, str | None]:
    if not design.use_custom_name:
        return design.name.strip(), None
    display = design.custom_name.strip() or design.name.strip()
    oracle = design.real_name.strip()
    if oracle and oracle != display:
        return display, oracle
    return display, None


def uses_custom_display_name(design: CardDesign) -> bool:
    return design.use_custom_name and bool(custom_display_title(design)[0])


def ensure_real_name(design: CardDesign, fallback: str) -> None:
    if not design.real_name.strip() and fallback.strip():
        design.real_name = fallback.strip()


CHROME_FIELDS = (
    "plate_texture_id", "plate_style_id", "chrome_mode",
    "title_piece_path", "subtitle_piece_path", "type_piece_path", "text_piece_path",
    "head_opacity", "body_opacity",
    "center_title", "center_subtitle", "center_description",
    "title_color", "subtitle_color", "type_color", "rules_color", "pt_color",
    "artist_color", "legal_color", "art_zoom", "art_offset_x", "art_offset_y",
    "use_custom_name", "custom_name",
)

CHROME_STYLE = "style"
CHROME_PIECES = "pieces"
PIECE_FIELDS = {
    "title": "title_piece_path",
    "subtitle": "subtitle_piece_path",
    "type": "type_piece_path",
    "text": "text_piece_path",
}


def piece_path_for(design: CardDesign, kind: str) -> str:
    field = PIECE_FIELDS.get(kind)
    return getattr(design, field) if field else ""


def copy_maker_chrome(source: CardDesign, destination: CardDesign) -> None:
    for field_name in CHROME_FIELDS:
        setattr(destination, field_name, getattr(source, field_name))


def is_split_design(design: CardDesign) -> bool:
    return " // " in design.mana_cost and " // " in design.name


def split_design_parts(design: CardDesign) -> tuple[list[str], list[str], list[str]]:
    names = [part.strip() for part in design.name.split(" // ")]
    manas = [part.strip() for part in design.mana_cost.split(" // ")]
    types = [part.strip() for part in design.type_line.split(" // ")]
    while len(manas) < len(names):
        manas.append("")
    while len(types) < len(names):
        types.append(types[-1] if types else "")
    return names, manas, types


def front_face_data(card: dict) -> dict:
    faces = card.get("card_faces") or []
    return faces[0] if faces else card


def italicize_reminder_text(text: str) -> str:
    return REMINDER_TEXT.sub(_wrap_in_asterisks, text)


def _wrap_in_asterisks(match: re.Match) -> str:
    return f"*{match.group(0)}*"


def italicize_flavor_text(flavor: str) -> str:
    return "\n".join(italicize_imported_line(line) for line in flavor.splitlines())


def italicize_imported_line(line: str) -> str:
    stripped = line.strip()
    if not stripped or is_already_italic_line(stripped):
        return line
    return f"*{line}*"


def is_already_italic_line(stripped: str) -> bool:
    return stripped.startswith("*") and stripped.endswith("*") and len(stripped) > 1


def looks_like_flavor_line(stripped: str) -> bool:
    return stripped[:1] in {"\"", "“", "«"} or stripped.startswith(("—", "–"))


def italicize_flavor_looking_lines(text: str) -> str:
    return "\n".join(maybe_italicize_flavor_line(line) for line in text.splitlines())


def maybe_italicize_flavor_line(line: str) -> str:
    stripped = line.strip()
    if not stripped or is_already_italic_line(stripped) or not looks_like_flavor_line(stripped):
        return line
    return f"*{line}*"


def format_imported_rules(rules: str) -> str:
    return italicize_flavor_looking_lines(italicize_reminder_text(rules)).strip()


def rules_with_flavor(face: dict) -> str:
    oracle = format_imported_rules(face.get("oracle_text", ""))
    flavor = face.get("flavor_text", "")
    if not flavor:
        return oracle
    marked_flavor = italicize_flavor_text(flavor)
    if oracle:
        return f"{oracle}\n{marked_flavor}"
    return marked_flavor


def infer_frame_color(card: dict, face: dict) -> str:
    type_line = face.get("type_line", card.get("type_line", "")).lower()
    colors = face.get("colors") if face.get("colors") is not None else card.get("colors", [])
    if "vehicle" in type_line:
        return "vehicle"
    if "land" in type_line:
        return land_color(card.get("color_identity", []))
    if "artifact" in type_line and not colors:
        return "artifact"
    return spell_color(colors)


def land_color(color_identity: list[str]) -> str:
    if len(color_identity) == 1:
        return COLOR_NAMES[color_identity[0]] + "Land"
    if len(color_identity) > 1:
        return "goldLand"
    return "colorlessLand"


def spell_color(colors: list[str]) -> str:
    if len(colors) == 1:
        return COLOR_NAMES.get(colors[0], "colorless")
    if len(colors) > 1:
        return "gold"
    return "colorless"
