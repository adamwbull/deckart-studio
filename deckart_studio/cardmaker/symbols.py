import re
from pathlib import Path

SYMBOL_TOKEN = re.compile(r"\{([^}]+)\}")
HYBRID_ORDER = ["wu", "wb", "ub", "ur", "br", "bg", "rg", "rw", "gw", "gu"]
SPECIAL_CODES = {
    "T": "t", "Q": "untap", "S": "snow", "C": "c", "X": "x", "Y": "y", "Z": "z", "E": "e",
    "½": "half", "HALF": "half", "∞": "infinity", "INFINITY": "infinity",
}
COLOR_LETTERS = set("WUBRG")

PALETTE_SYMBOLS = ["{W}", "{U}", "{B}", "{R}", "{G}", "{C}", "{T}", "{Q}", "{X}", "{S}", "{E}",
                   "{0}", "{1}", "{2}", "{3}", "{4}", "{5}", "{6}", "{7}", "{8}", "{9}", "{10}",
                   "{W/U}", "{W/B}", "{U/B}", "{U/R}", "{B/R}", "{B/G}", "{R/G}", "{R/W}", "{G/W}", "{G/U}",
                   "{2/W}", "{2/U}", "{2/B}", "{2/R}", "{2/G}", "{W/P}", "{U/P}", "{B/P}", "{R/P}", "{G/P}"]


class SymbolLibrary:
    """Maps Scryfall-style symbol tokens like {U} or {W/P} to the bundled symbol images."""

    def __init__(self, symbols_folder: Path):
        self.folder = Path(symbols_folder)
        self._available = {path.stem for path in self.folder.glob("*.png")}

    def image_path(self, token_body: str) -> Path | None:
        code = symbol_code(token_body)
        return self.folder / f"{code}.png" if code in self._available else None

    def has_symbol(self, token_body: str) -> bool:
        return symbol_code(token_body) in self._available

    def count(self) -> int:
        return len(self._available)


def symbol_code(token_body: str) -> str:
    body = token_body.strip().upper()
    if body in SPECIAL_CODES:
        return SPECIAL_CODES[body]
    if body.isdigit():
        return body
    if body in COLOR_LETTERS:
        return body.lower()
    return hybrid_code(body)


def hybrid_code(body: str) -> str:
    parts = body.split("/")
    if len(parts) == 2 and parts[1] == "P" and parts[0] in COLOR_LETTERS:
        return f"p{parts[0].lower()}"
    if len(parts) == 2 and parts[0] == "2" and parts[1] in COLOR_LETTERS:
        return f"2{parts[1].lower()}"
    if len(parts) == 2 and all(part in COLOR_LETTERS for part in parts):
        return canonical_hybrid(parts[0].lower() + parts[1].lower())
    return body.lower()


def canonical_hybrid(pair: str) -> str:
    reversed_pair = pair[1] + pair[0]
    if pair in HYBRID_ORDER:
        return pair
    return reversed_pair if reversed_pair in HYBRID_ORDER else pair


def mana_cost_tokens(mana_cost: str) -> list[str]:
    return SYMBOL_TOKEN.findall(mana_cost or "")
