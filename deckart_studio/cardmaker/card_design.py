import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

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
    head_opacity: float = 0.92
    body_opacity: float = 0.92
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


def rules_with_flavor(face: dict) -> str:
    oracle = face.get("oracle_text", "")
    flavor = face.get("flavor_text", "")
    if flavor:
        return f"{oracle}\n*{flavor}*" if oracle else f"*{flavor}*"
    return oracle


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
