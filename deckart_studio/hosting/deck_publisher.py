import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

from deckart_studio.hosting.steam_cloud import SteamCloud, cloud_filename_for
from deckart_studio.hosting.upload_index import UploadIndex
from deckart_studio.image_source import url_to_local_path
from deckart_studio.net import download_file
from deckart_studio.settings import mirror_directory

ProgressCallback = Callable[[str], None]
TTS_NATIVE_SUFFIXES = {".jpg", ".jpeg", ".png"}
MAX_UPLOAD_WIDTH = 1500
JPEG_QUALITY = 92
PNG_KEEP_LIMIT_BYTES = 1_500_000


@dataclass
class PublishResult:
    url_replacements: dict[str, str]
    uploaded: int
    reused: int
    failed: list[str]


@dataclass
class PublishItem:
    """One deck image link to make public: the URL as written in the deck and the local file holding its bytes."""

    deck_url: str
    local_path: Path

    @property
    def display_name(self) -> str:
        return self.local_path.name if url_to_local_path(self.deck_url) is not None else self.deck_url


class DeckPublisher:
    """Puts every image a deck references that TTS cannot show to others onto Steam Cloud and maps the links."""

    def __init__(self, index: UploadIndex, steam_api_dll: Path | None, mirror_folder: Path | None = None):
        self.index = index
        self.steam_api_dll = steam_api_dll
        self.mirror_folder = mirror_folder or mirror_directory()

    def publish(self, deck_name: str, deck_urls: list[str], report: ProgressCallback) -> PublishResult:
        result = PublishResult({}, 0, 0, [])
        items = self._materialize(deck_urls, result, report)
        pending = [item for item in items if not self._reuse_known_upload(item, result)]
        if pending:
            self._upload_all(deck_name, pending, result, report)
        return result

    def _materialize(self, deck_urls: list[str], result: PublishResult, report: ProgressCallback) -> list[PublishItem]:
        items: list[PublishItem] = []
        remote = [url for url in deck_urls if url_to_local_path(url) is None]
        for position, url in enumerate(deck_urls, start=1):
            local = url_to_local_path(url)
            if local is None:
                report(f"Fetching {remote.index(url) + 1}/{len(remote)} image(s) TTS cannot load: {Path(url).name}")
                local = self._mirror(url, result)
            if local is not None:
                items.append(PublishItem(url, local))
        return items

    def _mirror(self, url: str, result: PublishResult) -> Path | None:
        try:
            return download_file(url, self.mirror_folder / mirror_filename_for(url))
        except Exception as error:
            result.failed.append(f"{url}: could not download ({error})")
            return None

    def _reuse_known_upload(self, item: PublishItem, result: PublishResult) -> bool:
        known = self.index.url_for(item.local_path)
        if known is None:
            return False
        result.url_replacements[item.deck_url] = known
        result.reused += 1
        return True

    def _upload_all(self, deck_name: str, items: list[PublishItem], result: PublishResult, report: ProgressCallback) -> None:
        report("Connecting to Steam…")
        with SteamCloud(self.steam_api_dll) as cloud:
            for position, item in enumerate(items, start=1):
                report(f"Uploading {position}/{len(items)}: {item.display_name}")
                self._upload_one(cloud, deck_name, item, result)

    def _upload_one(self, cloud: SteamCloud, deck_name: str, item: PublishItem, result: PublishResult) -> None:
        if not item.local_path.exists():
            result.failed.append(f"{item.display_name}: file is missing on this PC - pick or re-render its art, then publish again")
            return
        try:
            payload, suffix = prepare_payload(item.local_path)
            url = cloud.upload(cloud_filename_for(deck_name, item.local_path.with_suffix(suffix), payload), payload)
        except Exception as error:
            result.failed.append(f"{item.display_name}: {error}")
            return
        self.index.record(item.local_path, url)
        result.url_replacements[item.deck_url] = url
        result.uploaded += 1


def mirror_filename_for(url: str) -> str:
    suffix = Path(url.split("?")[0]).suffix.lower() or ".jpg"
    return hashlib.sha1(url.encode("utf-8")).hexdigest() + suffix


def prepare_payload(path: Path) -> tuple[bytes, str]:
    """Return upload bytes and their suffix: TTS-native formats pass through, everything else becomes JPEG."""
    if path.suffix.lower() in TTS_NATIVE_SUFFIXES and path.stat().st_size <= PNG_KEEP_LIMIT_BYTES:
        return path.read_bytes(), path.suffix.lower()
    image = QImage(str(path))
    if image.isNull():
        raise ValueError("not a readable image")
    if image.width() > MAX_UPLOAD_WIDTH:
        image = image.scaledToWidth(MAX_UPLOAD_WIDTH, Qt.TransformationMode.SmoothTransformation)
    return encode_jpeg(image), ".jpg"


def encode_jpeg(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.convertToFormat(QImage.Format.Format_RGB32).save(buffer, "JPG", JPEG_QUALITY)
    return bytes(buffer.data())
