from dataclasses import dataclass
from pathlib import Path

PROMPT_PATH = Path(__file__).resolve().parents[2] / "david-mendez-rw-2.0-SeaArt-Prompts.txt"
SPLIT_ALIASES = {
    "Needleverge Pathway": ("Needleverge Pathway // Pillarverge Pathway",),
}
USE_MARKER = " (use for all"


@dataclass(frozen=True)
class CardPrompt:
    custom_name: str
    prompt: str
    oracle_names: tuple[str, ...]


def prompt_file() -> Path:
    return PROMPT_PATH


def load_card_prompts(path: Path | None = None) -> list[CardPrompt]:
    text = (path or prompt_file()).read_text(encoding="utf-8")
    body = text.split("COMMANDERS", 1)[-1]
    cards: list[CardPrompt] = []
    lines = body.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if skip_line(line):
            index += 1
            continue
        if index + 1 >= len(lines) or not lines[index + 1].strip().startswith("("):
            index += 1
            continue
        title = clean_title(line)
        oracle_line = lines[index + 1].strip()
        prompt_lines, index = collect_prompt_lines(lines, index + 2)
        cards.append(CardPrompt(title, " ".join(prompt_lines), oracle_names_from(oracle_line)))
    return cards


def skip_line(line: str) -> bool:
    if not line or set(line) <= {"-"}:
        return True
    return line.isupper() and " " in line and "(" not in line


def clean_title(line: str) -> str:
    if USE_MARKER in line:
        return line.split(USE_MARKER, 1)[0].strip()
    return line.strip()


def collect_prompt_lines(lines: list[str], start: int) -> tuple[list[str], int]:
    prompt_lines: list[str] = []
    index = start
    while index < len(lines) and lines[index].strip():
        prompt_lines.append(lines[index].strip())
        index += 1
    return prompt_lines, index


def oracle_names_from(line: str) -> tuple[str, ...]:
    inner = line.strip()
    if inner.startswith("(") and inner.endswith(")"):
        inner = inner[1:-1]
    names: list[str] = []
    for chunk in inner.split(" / "):
        name = chunk.split(" — ", 1)[0].strip()
        if name:
            names.append(name)
            names.extend(SPLIT_ALIASES.get(name, ()))
    return tuple(dict.fromkeys(names))


def prompts_by_oracle(path: Path | None = None) -> dict[str, CardPrompt]:
    mapping: dict[str, CardPrompt] = {}
    for card in load_card_prompts(path):
        for oracle_name in card.oracle_names:
            mapping[oracle_name] = card
    return mapping
