import json
from dataclasses import asdict, dataclass
from pathlib import Path

from deckart_studio.settings import settings_directory

INDEX_FILE_NAME = "uploads.json"


@dataclass
class UploadRecord:
    local_path: str
    url: str
    mtime_ns: int
    size: int

    def matches(self, path: Path) -> bool:
        try:
            stat = path.stat()
        except OSError:
            return False
        return stat.st_mtime_ns == self.mtime_ns and stat.st_size == self.size


class UploadIndex:
    """Remembers which local images were uploaded where, so unchanged files are never uploaded twice."""

    def __init__(self, path: Path | None = None):
        self.path = path or settings_directory() / INDEX_FILE_NAME
        self._records: dict[str, UploadRecord] = self._load()

    def url_for(self, path: Path) -> str | None:
        record = self._records.get(normalized(path))
        return record.url if record is not None and record.matches(path) else None

    def local_path_for(self, url: str) -> Path | None:
        for record in self._records.values():
            if record.url == url and Path(record.local_path).exists():
                return Path(record.local_path)
        return None

    def record(self, path: Path, url: str) -> None:
        stat = path.stat()
        self._records[normalized(path)] = UploadRecord(normalized(path), url, stat.st_mtime_ns, stat.st_size)
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(record) for record in self._records.values()]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load(self) -> dict[str, UploadRecord]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        records = (UploadRecord(**entry) for entry in raw if isinstance(entry, dict))
        return {record.local_path: record for record in records}


def normalized(path: Path) -> str:
    return str(Path(path).resolve())
