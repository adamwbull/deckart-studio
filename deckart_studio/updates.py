import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

from deckart_studio.net import download_file, fetch_json
from deckart_studio.version import APP_VERSION, GITHUB_REPOSITORY

GITHUB_API = "https://api.github.com/repos/{repo}/releases/latest"
INSTALL_KIND_FILE = "install_kind.txt"
MSI_INSTALL_KIND = "msi"


@dataclass(frozen=True)
class AppRelease:
    version: str
    tag: str
    zip_url: str
    html_url: str
    notes: str
    msi_url: str = ""


class UpdateError(RuntimeError):
    pass


def version_tuple(version: str) -> tuple[int, ...]:
    numbers = []
    for part in version.lstrip("v").split("."):
        digits = "".join(character for character in part if character.isdigit())
        numbers.append(int(digits) if digits else 0)
    return tuple(numbers)


def is_newer_version(candidate: str, current: str = APP_VERSION) -> bool:
    return version_tuple(candidate) > version_tuple(current)


def should_check_for_updates() -> bool:
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        return False
    if "--selftest" in sys.argv:
        return False
    return bool(GITHUB_REPOSITORY)


def should_auto_apply_update(silent: bool, install_folder: Path | None) -> bool:
    return bool(silent and install_folder is not None)


def latest_release(repository: str = GITHUB_REPOSITORY) -> AppRelease:
    if not repository:
        raise UpdateError("No GitHub repository is configured for updates.")
    payload = fetch_json(GITHUB_API.format(repo=repository))
    version = str(payload.get("tag_name") or "").lstrip("v")
    zip_url = release_zip_url(payload, version)
    if not version or not zip_url:
        raise UpdateError("The latest GitHub release has no Windows zip.")
    return AppRelease(
        version=version,
        tag=str(payload.get("tag_name") or version),
        zip_url=zip_url,
        html_url=str(payload.get("html_url") or ""),
        notes=str(payload.get("body") or ""),
        msi_url=release_msi_url(payload, version),
    )


def release_asset_url(payload: dict, version: str, suffix: str) -> str:
    expected = f"DeckArtStudio-{version}-{suffix}".lower()
    fallback = f"-{suffix}".lower()
    for asset in payload.get("assets") or []:
        name = str(asset.get("name") or "").lower()
        url = asset.get("browser_download_url")
        if url and (name == expected or name.endswith(fallback)):
            return str(url)
    return ""


def release_zip_url(payload: dict, version: str) -> str:
    return release_asset_url(payload, version, "win64.zip")


def release_msi_url(payload: dict, version: str) -> str:
    return release_asset_url(payload, version, "win64.msi")


def is_msi_install(install_folder: Path) -> bool:
    marker = Path(install_folder) / INSTALL_KIND_FILE
    try:
        return marker.read_text(encoding="utf-8").strip().lower() == MSI_INSTALL_KIND
    except OSError:
        return False


def download_release_zip(release: AppRelease, destination: Path) -> Path:
    return download_file(release.zip_url, destination)


def update_download_folder(preferred: Path | None = None) -> Path:
    folder = Path(preferred) if preferred and is_writable_directory(preferred) else Path(tempfile.gettempdir()) / "DeckArtStudioUpdates"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def is_writable_directory(folder: Path) -> bool:
    try:
        if folder.exists() and not folder.is_dir():
            return False
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".deckart_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def download_release_package(release: AppRelease, destination_folder: Path, install_folder: Path) -> Path:
    folder = update_download_folder(destination_folder)
    if is_msi_install(install_folder) and release.msi_url:
        return download_file(release.msi_url, folder / f"DeckArtStudio-{release.version}-win64.msi")
    return download_file(release.zip_url, folder / f"DeckArtStudio-{release.version}-win64.zip")


def updater_log_path() -> Path:
    return Path(tempfile.gettempdir()) / "deckart_update.log"


def updater_process_flags() -> int:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if os.name == "nt":
        flags |= subprocess.CREATE_NEW_PROCESS_GROUP
    return flags


def apply_downloaded_update(package_path: Path, install_folder: Path, restart_pid: int) -> Path:
    script = updater_script_for(package_path, install_folder, restart_pid)
    subprocess.Popen(["cmd", "/c", str(script)], creationflags=updater_process_flags())
    return script


def updater_script_for(package_path: Path, install_folder: Path, restart_pid: int) -> Path:
    if package_path.suffix.lower() == ".msi":
        return write_msi_updater_script(package_path, install_folder, restart_pid)
    return write_zip_updater_script(package_path, install_folder, restart_pid)


def write_zip_updater_script(zip_path: Path, install_folder: Path, restart_pid: int) -> Path:
    extract_root = Path(tempfile.mkdtemp(prefix="deckart_update_"))
    with ZipFile(zip_path) as archive:
        archive.extractall(extract_root)
    return write_updater_script(extracted_app_folder(extract_root), install_folder, restart_pid)


def extracted_app_folder(extract_root: Path) -> Path:
    nested = extract_root / "DeckArtStudio"
    if (nested / "DeckArtStudio.exe").exists():
        return nested
    for candidate in extract_root.iterdir():
        if candidate.is_dir() and (candidate / "DeckArtStudio.exe").exists():
            return candidate
    raise UpdateError("The downloaded zip did not contain DeckArtStudio.exe.")


def write_msi_updater_script(msi_path: Path, install_folder: Path, restart_pid: int) -> Path:
    exe = install_folder / "DeckArtStudio.exe"
    msi_log = Path(tempfile.gettempdir()) / "deckart_msiexec.log"
    return write_batch_updater([
        *wait_until_pid_exits(restart_pid),
        log_line(f"install {msi_path}"),
        powershell_msi_install(msi_path, msi_log),
        "if errorlevel 1 (",
        log_line("msiexec failed"),
        "  exit /b 1",
        ")",
        log_line("relaunch"),
        f'start "" "{exe}"',
    ])


def write_updater_script(source: Path, install_folder: Path, restart_pid: int) -> Path:
    exe = install_folder / "DeckArtStudio.exe"
    return write_batch_updater([
        *wait_until_pid_exits(restart_pid),
        log_line(f"copy {source} -> {install_folder}"),
        f'robocopy "{source}" "{install_folder}" /E /IS /IT /NFL /NDL /NJH /NJS /R:2 /W:1',
        log_line("relaunch"),
        f'start "" "{exe}"',
    ])


def write_batch_updater(commands: list[str]) -> Path:
    script = Path(tempfile.gettempdir()) / "deckart_apply_update.bat"
    script.write_text("\n".join(["@echo off", *commands, ""]), encoding="utf-8")
    return script


def wait_until_pid_exits(pid: int) -> list[str]:
    return [
        log_line(f"wait for pid {pid}"),
        ":wait",
        f'tasklist /FI "PID eq {pid}" | find "{pid}" >nul',
        "if not errorlevel 1 (",
        "  ping -n 2 127.0.0.1 >nul",
        "  goto wait",
        ")",
        log_line(f"pid {pid} exited"),
    ]


def powershell_msi_install(msi_path: Path, msi_log: Path) -> str:
    arguments = ",".join(
        f"'{part}'" for part in ("/i", str(msi_path), "/qb", "/norestart", "/l*v", str(msi_log))
    )
    return (
        'powershell -NoProfile -WindowStyle Hidden -Command '
        f'"Start-Process msiexec -ArgumentList {arguments} -Verb RunAs -Wait"'
    )


def log_line(message: str) -> str:
    return f'>>"{updater_log_path()}" echo {message}'


def frozen_install_folder() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).resolve().parent
