import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from deckart_studio.app_paths import data_directory, default_deck_art_root, default_saved_objects_folder
from deckart_studio.gemini.art_styles import merge_default_art_styles
from deckart_studio.prompt_library import default_prompt_folder

AI_FOLDER_SUFFIX = "_ai"
ORIGINAL_SUBFOLDER = "original"
GENERATED_AI_FOLDER = "generated_ai"
DECK_ART_README = """DeckArt Studio gallery folder

Drop image folders or files in here (or anywhere, then add them in the app's Gallery panel).
  * Any folder whose name ends in _ai shows up under "AI Recommended" when picking art.
  * original/  is where original card art from Scryfall is cached.
  * rendered/  is where Card Maker writes the custom faces it renders (one folder per deck).
"""


def settings_directory() -> Path:
    return data_directory()


def settings_file() -> Path:
    return settings_directory() / "settings.json"


def cache_directory() -> Path:
    return settings_directory() / "cache"


def backup_directory() -> Path:
    return settings_directory() / "backups"


def log_directory() -> Path:
    return settings_directory() / "logs"


def mirror_directory() -> Path:
    return cache_directory() / "mirror"


@dataclass
class AppSettings:
    saved_objects_folder: str = ""
    deck_art_folder: str = ""
    original_art_folder: str = ""
    tts_install_folder: str = ""
    gallery_folders: list[str] = field(default_factory=list)
    gallery_files: list[str] = field(default_factory=list)
    last_deck_path: str = ""
    last_artist_credit: str = ""
    gemini_api_key: str = ""
    gemini_model_id: str = "nano-banana-2"
    prompt_folder: str = ""
    art_styles: list[str] = field(default_factory=list)
    last_art_style: str = ""
    check_for_updates: bool = True
    auto_advance: bool = True
    prefer_remote_original_urls: bool = True
    slot_size: int = 180
    window_geometry_hex: str = ""

    @staticmethod
    def load() -> "AppSettings":
        settings = AppSettings.from_file(settings_file())
        settings.apply_defaults()
        return settings

    @staticmethod
    def from_file(path: Path) -> "AppSettings":
        if not path.exists():
            return AppSettings()
        try:
            return AppSettings.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return AppSettings()

    @staticmethod
    def from_dict(raw: dict) -> "AppSettings":
        known_fields = AppSettings.__dataclass_fields__.keys()
        return AppSettings(**{key: value for key, value in raw.items() if key in known_fields})

    def apply_defaults(self) -> None:
        if not self.saved_objects_folder:
            self.saved_objects_folder = str(default_saved_objects_folder())
        if not self.deck_art_folder:
            self.deck_art_folder = str(default_deck_art_root())
        if not self.original_art_folder:
            self.original_art_folder = str(self.deck_art_root() / ORIGINAL_SUBFOLDER)
        self.art_styles = merge_default_art_styles(self.art_styles)
        if not self.last_art_style or self.last_art_style not in self.art_styles:
            self.last_art_style = self.art_styles[0]
        if not self.prompt_folder:
            self.prompt_folder = str(default_prompt_folder())
        self.ensure_deck_art_root()
        self.add_gallery_folder(self.deck_art_root())

    def generated_ai_folder(self) -> Path:
        return self.deck_art_root() / GENERATED_AI_FOLDER

    def deck_art_root(self) -> Path:
        return Path(self.deck_art_folder)

    def ensure_deck_art_root(self) -> None:
        root = self.deck_art_root()
        root.mkdir(parents=True, exist_ok=True)
        self.generated_ai_folder().mkdir(parents=True, exist_ok=True)
        readme = root / "README.txt"
        if not readme.exists():
            readme.write_text(DECK_ART_README, encoding="utf-8")

    def change_deck_art_root(self, new_root: Path) -> None:
        old_root = self.deck_art_root()
        self.remove_gallery_source(str(old_root))
        if Path(self.original_art_folder) == old_root / ORIGINAL_SUBFOLDER:
            self.original_art_folder = str(Path(new_root) / ORIGINAL_SUBFOLDER)
        self.deck_art_folder = str(new_root)
        self.ensure_deck_art_root()
        self.add_gallery_folder(new_root)

    def save(self) -> None:
        settings_file().parent.mkdir(parents=True, exist_ok=True)
        settings_file().write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def add_gallery_folder(self, folder: Path) -> bool:
        return self._add_unique(self.gallery_folders, folder)

    def add_gallery_file(self, file: Path) -> bool:
        return self._add_unique(self.gallery_files, file)

    def remove_gallery_source(self, source: str) -> None:
        normalized = self._normalize(Path(source))
        self.gallery_folders = [entry for entry in self.gallery_folders if entry != normalized]
        self.gallery_files = [entry for entry in self.gallery_files if entry != normalized]

    def gallery_sources(self) -> list[str]:
        return list(self.gallery_folders) + list(self.gallery_files)

    def _add_unique(self, collection: list[str], path: Path) -> bool:
        normalized = self._normalize(path)
        if normalized in collection:
            return False
        collection.append(normalized)
        return True

    @staticmethod
    def _normalize(path: Path) -> str:
        return str(Path(path).resolve())
