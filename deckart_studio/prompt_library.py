from dataclasses import dataclass
from pathlib import Path

from deckart_studio.app_paths import project_root
from deckart_studio.original_art.original_art import normalize_card_name
from deckart_studio.tools.cyberpunk_prompts import (
    CardPrompt, clean_title, collect_prompt_lines, load_card_prompts, oracle_names_from, skip_line,
)

DEFAULT_PROMPT_FOLDER = Path(r"D:\MTG")
PROMPT_STEM_MARK = "prompt"
FALLBACK_PROMPT_FILE = "card-prompts.txt"


@dataclass(frozen=True)
class LocatedPrompt:
    path: Path
    card: CardPrompt


def default_prompt_folder() -> Path:
    if DEFAULT_PROMPT_FOLDER.is_dir():
        return DEFAULT_PROMPT_FOLDER
    return project_root()


def discover_prompt_files(folder: Path) -> list[Path]:
    if not Path(folder).is_dir():
        return []
    matches = [
        path for path in Path(folder).glob("*.txt")
        if PROMPT_STEM_MARK in path.stem.lower()
    ]
    return sorted(matches, key=lambda path: path.stat().st_mtime)


def load_prompt_index(folder: Path) -> dict[str, LocatedPrompt]:
    index: dict[str, LocatedPrompt] = {}
    for path in discover_prompt_files(folder):
        for card in load_card_prompts(path):
            located = LocatedPrompt(path, card)
            for name in (card.custom_name, *card.oracle_names):
                key = normalize_card_name(name)
                if key:
                    index[key] = located
    return index


def locate_prompt(folder: Path, *names: str) -> LocatedPrompt | None:
    index = load_prompt_index(folder)
    for name in names:
        found = index.get(normalize_card_name(name or ""))
        if found is not None:
            return found
    return None


def prompt_text_for(folder: Path, *names: str) -> str:
    found = locate_prompt(folder, *names)
    return found.card.prompt if found else ""


def prompt_source_name(folder: Path) -> str:
    files = discover_prompt_files(folder)
    return files[-1].name if files else ""


def save_card_prompt(folder: Path, names: list[str], prompt: str, custom_name: str, oracle_name: str) -> Path:
    text = " ".join(prompt.split())
    if not text:
        raise ValueError("Prompt is empty.")
    found = locate_prompt(folder, *names)
    if found is not None:
        replace_card_prompt(found.path, names, text)
        return found.path
    target = write_target_file(folder)
    append_card_prompt(target, custom_name or oracle_name, oracle_name or custom_name, text)
    return target


def write_target_file(folder: Path) -> Path:
    files = discover_prompt_files(folder)
    if files:
        return files[-1]
    Path(folder).mkdir(parents=True, exist_ok=True)
    target = Path(folder) / FALLBACK_PROMPT_FILE
    if not target.exists():
        target.write_text("COMMANDERS\n----------\n\nMAIN DECK\n---------\n\n", encoding="utf-8")
    return target


def replace_card_prompt(path: Path, names: list[str], prompt: str) -> None:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    keys = {normalize_card_name(name) for name in names if name}
    start = next((index for index, line in enumerate(lines) if line.strip() == "COMMANDERS"), 0)
    index = start
    while index < len(lines):
        if skip_line(lines[index].strip()):
            index += 1
            continue
        if index + 1 >= len(lines) or not lines[index + 1].strip().startswith("("):
            index += 1
            continue
        title = clean_title(lines[index].strip())
        oracle_names = oracle_names_from(lines[index + 1].strip())
        card_keys = {normalize_card_name(name) for name in (title, *oracle_names) if name}
        prompt_start = index + 2
        _prompt_lines, prompt_end = collect_prompt_lines(lines, prompt_start)
        if keys & card_keys:
            updated = lines[:prompt_start] + [prompt] + lines[prompt_end:]
            Path(path).write_text("\n".join(updated) + "\n", encoding="utf-8")
            return
        index = prompt_end if prompt_end > index else index + 1
    raise ValueError(f"No prompt block matched {names} in {path.name}")


def append_card_prompt(path: Path, custom_name: str, oracle_name: str, prompt: str) -> None:
    title = custom_name.strip() or oracle_name.strip()
    oracle = oracle_name.strip() or title
    block = f"\n{title}\n({oracle})\n{prompt}\n"
    text = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
    if "\nTOKENS\n" in text:
        text = text.replace("\nTOKENS\n", f"{block}\nTOKENS\n", 1)
    else:
        text = text.rstrip() + "\n" + block
    Path(path).write_text(text, encoding="utf-8")
