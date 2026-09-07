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


def download_release_package(release: AppRelease, destination_folder: Path, install_folder: Path) -> Path:
    if is_msi_install(install_folder) and release.msi_url:
        return download_file(release.msi_url, destination_folder / f"DeckArtStudio-{release.version}-win64.msi")
    return download_file(release.zip_url, destination_folder / f"DeckArtStudio-{release.version}-win64.zip")


def apply_downloaded_update(package_path: Path, install_folder: Path, restart_pid: int) -> Path:
    script = updater_script_for(package_path, install_folder, restart_pid)
    subprocess.Popen(["cmd", "/c", str(script)], creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
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
    script = Path(tempfile.gettempdir()) / "deckart_apply_update.bat"
    exe = install_folder / "DeckArtStudio.exe"
    script.write_text(
        "\n".join([
            "@echo off",
            ":wait",
            f'tasklist /FI "PID eq {restart_pid}" | find "{restart_pid}" >nul',
            "if not errorlevel 1 (",
            "  timeout /t 1 /nobreak >nul",
            "  goto wait",
            ")",
            f'msiexec /i "{msi_path}" /passive /norestart',
            f'start "" "{exe}"',
            "",
        ]),
        encoding="utf-8",
    )
    return script


def write_updater_script(source: Path, install_folder: Path, restart_pid: int) -> Path:
    script = Path(tempfile.gettempdir()) / "deckart_apply_update.bat"
    exe = install_folder / "DeckArtStudio.exe"
    script.write_text(
        "\n".join([
            "@echo off",
            f":wait",
            f'tasklist /FI "PID eq {restart_pid}" | find "{restart_pid}" >nul',
            "if not errorlevel 1 (",
            "  timeout /t 1 /nobreak >nul",
            "  goto wait",
            ")",
            f'robocopy "{source}" "{install_folder}" /E /IS /IT /NFL /NDL /NJH /NJS /R:2 /W:1',
            f'start "" "{exe}"',
            "",
        ]),
        encoding="utf-8",
    )
    return script


def frozen_install_folder() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).resolve().parent
