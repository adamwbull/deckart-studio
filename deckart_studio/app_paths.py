"""Where the app finds its bundled resources and where it may write, both from source and as a frozen EXE."""
import ctypes
import os
import sys
from pathlib import Path

APP_FOLDER_NAME = "DeckArtStudio"
DOCUMENTS_FOLDER_NAME = "DeckArt Studio"
PORTABLE_MARKER = "portable.txt"
FOLDERID_DOCUMENTS = "{FDD39AD0-238F-46AF-ADB4-6D24FF10FE09}"


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def package_root() -> Path:
    return Path(__file__).resolve().parent


def project_root() -> Path:
    return package_root().parent


def resource_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "deckart_studio"
    return package_root()


def executable_directory() -> Path:
    return Path(sys.executable).resolve().parent if is_frozen() else project_root()


def data_directory() -> Path:
    override = os.environ.get("DECKART_STUDIO_DATA")
    if override:
        return Path(override)
    if not is_frozen():
        return project_root() / ".deckart_studio"
    if (executable_directory() / PORTABLE_MARKER).exists():
        return executable_directory() / "data"
    return local_app_data() / APP_FOLDER_NAME


def local_app_data() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))


def documents_folder() -> Path:
    return known_folder(FOLDERID_DOCUMENTS) or Path.home() / "Documents"


def known_folder(folder_id: str) -> Path | None:
    if sys.platform != "win32":
        return None
    try:
        return _query_known_folder(folder_id)
    except (OSError, AttributeError, ValueError):
        return None


def _query_known_folder(folder_id: str) -> Path | None:
    guid = ctypes.create_string_buffer(16)
    if ctypes.windll.ole32.CLSIDFromString(folder_id, guid) != 0:
        return None
    path_pointer = ctypes.c_wchar_p()
    if ctypes.windll.shell32.SHGetKnownFolderPath(guid, 0, None, ctypes.byref(path_pointer)) != 0:
        return None
    result = Path(path_pointer.value)
    ctypes.windll.ole32.CoTaskMemFree(path_pointer)
    return result


def default_deck_art_root() -> Path:
    development_root = project_root() / "DeckArt"
    if not is_frozen() and development_root.exists():
        return development_root
    return documents_folder() / DOCUMENTS_FOLDER_NAME / "DeckArt"


def default_saved_objects_folder() -> Path:
    relative = Path("My Games/Tabletop Simulator/Saves/Saved Objects")
    candidates = [documents_folder() / relative, Path.home() / "OneDrive" / "Documents" / relative,
                  Path.home() / "Documents" / relative]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]
