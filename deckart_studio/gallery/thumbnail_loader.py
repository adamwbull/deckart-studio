import hashlib
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QImage, QImageReader, QPixmap

from deckart_studio.image_source import is_remote_url
from deckart_studio.net import download_file
from deckart_studio.settings import cache_directory


class _WorkerSignals(QObject):
    finished = Signal(str, int, QImage)


class _ThumbnailJob(QRunnable):
    def __init__(self, key: str, size: int, signals: _WorkerSignals):
        super().__init__()
        self.key = key
        self.size = size
        self.signals = signals

    def run(self) -> None:
        image = load_thumbnail_image(self.key, self.size)
        self.signals.finished.emit(self.key, self.size, image)


class ThumbnailLoader(QObject):
    """Asynchronously produces scaled thumbnails for local files or remote URLs, with a disk cache."""

    thumbnailReady = Signal(str, int)
    keyInvalidated = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(4)
        self._memory: dict[tuple[str, int], QPixmap] = {}
        self._in_flight: set[tuple[str, int]] = set()
        self._signals = _WorkerSignals()
        self._signals.finished.connect(self._on_job_finished)

    def pixmap(self, key: str, size: int) -> QPixmap | None:
        return self._memory.get((key, size))

    def request(self, key: str, size: int) -> QPixmap | None:
        cached = self.pixmap(key, size)
        if cached is not None or not key:
            return cached
        job_key = (key, size)
        if job_key not in self._in_flight:
            self._in_flight.add(job_key)
            self._pool.start(_ThumbnailJob(key, size, self._signals))
        return None

    def forget(self, key: str) -> None:
        for cached_key in [entry for entry in self._memory if entry[0] == key]:
            del self._memory[cached_key]
        self.keyInvalidated.emit(key)

    def forget_all(self) -> None:
        keys = {entry[0] for entry in self._memory}
        self._memory.clear()
        for key in keys:
            self.keyInvalidated.emit(key)

    @Slot(str, int, QImage)
    def _on_job_finished(self, key: str, size: int, image: QImage) -> None:
        self._in_flight.discard((key, size))
        self._memory[(key, size)] = QPixmap.fromImage(image)
        self.thumbnailReady.emit(key, size)


def load_thumbnail_image(key: str, size: int) -> QImage:
    try:
        source_path = resolve_source_path(key)
        return read_scaled_image(source_path, size)
    except Exception:
        return QImage()


def keys_match(first: str, second: str) -> bool:
    if first == second:
        return True
    if not first or not second or is_remote_url(first) or is_remote_url(second):
        return False
    try:
        return Path(first).resolve() == Path(second).resolve()
    except OSError:
        return False


def resolve_source_path(key: str) -> Path:
    if is_remote_url(key):
        return download_file(key, remote_cache_path(key))
    return Path(key)


def remote_cache_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    suffix = Path(url.split("?")[0]).suffix or ".img"
    return cache_directory() / "remote" / f"{digest}{suffix}"


def read_scaled_image(path: Path, size: int) -> QImage:
    thumb_path = thumbnail_cache_path(path, size)
    if thumb_path.exists():
        return QImage(str(thumb_path))
    image = decode_scaled(path, size)
    if not image.isNull():
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(thumb_path), "JPG", 88)
    return image


def thumbnail_cache_path(path: Path, size: int) -> Path:
    stat = path.stat()
    digest = hashlib.sha1(f"{path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}|{size}".encode("utf-8")).hexdigest()
    return cache_directory() / "thumbs" / f"{digest}.jpg"


def decode_scaled(path: Path, size: int) -> QImage:
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    original = reader.size()
    if original.isValid() and max(original.width(), original.height()) > size:
        reader.setScaledSize(fit_within(original, size))
    return reader.read()


def fit_within(original: QSize, size: int) -> QSize:
    return original.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio)
