"""Finds the Steam client, whether it is running, and Tabletop Simulator's bundled steam_api64.dll."""
import ctypes
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

TABLETOP_SIMULATOR_APP_ID = 286160
TABLETOP_SIMULATOR_FOLDER = Path("steamapps/common/Tabletop Simulator")
STEAM_API_DLL_RELATIVE = Path("Tabletop Simulator_Data/Plugins/x86_64/steam_api64.dll")
LIBRARY_PATH_PATTERN = re.compile(r'"path"\s+"([^"]+)"')
DEFAULT_STEAM_FOLDERS = (
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Steam",
)
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


@dataclass
class SteamStatus:
    """What the publish step needs to know before trying an upload."""

    steam_folder: Path | None
    steam_running: bool
    api_dll: Path | None

    def is_ready(self) -> bool:
        return self.steam_running and self.api_dll is not None

    def describe(self) -> str:
        return "\n".join([describe_client(self.steam_folder, self.steam_running), describe_tts(self.api_dll)])


def steam_status(tts_folder_override: str = "") -> SteamStatus:
    return SteamStatus(steam_install_path(), is_steam_running(), find_steam_api_dll(tts_folder_override))


def describe_client(steam_folder: Path | None, running: bool) -> str:
    if running:
        return f"Steam client: running ({steam_folder or 'location unknown'})"
    if steam_folder is None:
        return "Steam client: not found on this PC - install Steam and log in"
    return f"Steam client: installed at {steam_folder} but NOT running - start Steam and log in"


def describe_tts(api_dll: Path | None) -> str:
    if api_dll is None:
        return ("Tabletop Simulator: not found in any Steam library - install it, or point Settings at its folder")
    return f"Tabletop Simulator: {api_dll.parents[3]}"


def find_steam_api_dll(tts_folder_override: str = "") -> Path | None:
    for tts_folder in candidate_tts_folders(tts_folder_override):
        candidate = tts_folder / STEAM_API_DLL_RELATIVE
        if candidate.exists():
            return candidate
    return None


def candidate_tts_folders(tts_folder_override: str) -> list[Path]:
    folders = [Path(tts_folder_override)] if tts_folder_override.strip() else []
    folders.extend(library / TABLETOP_SIMULATOR_FOLDER for library in steam_library_folders())
    return folders


def steam_library_folders() -> list[Path]:
    steam_root = steam_install_path()
    if steam_root is None:
        return []
    folders = [steam_root]
    manifest = steam_root / "steamapps" / "libraryfolders.vdf"
    if manifest.exists():
        folders.extend(Path(match.replace("\\\\", "\\")) for match in LIBRARY_PATH_PATTERN.findall(
            manifest.read_text(encoding="utf-8", errors="ignore")))
    return list(dict.fromkeys(folders))


def steam_install_path() -> Path | None:
    for candidate in registry_steam_paths() + list(DEFAULT_STEAM_FOLDERS):
        if candidate is not None and (candidate / "steam.exe").exists():
            return candidate
    return None


def registry_steam_paths() -> list[Path | None]:
    if sys.platform != "win32":
        return []
    import winreg
    return [
        read_registry_path(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        read_registry_path(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        read_registry_path(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    ]


def read_registry_path(hive, key_path: str, value_name: str) -> Path | None:
    import winreg
    try:
        with winreg.OpenKey(hive, key_path) as key:
            return Path(winreg.QueryValueEx(key, value_name)[0])
    except OSError:
        return None


def is_steam_running() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam\ActiveProcess") as key:
            pid = int(winreg.QueryValueEx(key, "pid")[0])
    except (OSError, ValueError):
        return False
    return pid > 0 and process_exists(pid)


def process_exists(pid: int) -> bool:
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    ctypes.windll.kernel32.CloseHandle(handle)
    return True
