from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def is_remote_url(value: str) -> bool:
    return value.lower().startswith(("http://", "https://"))


def local_path_to_url(path: Path) -> str:
    return Path(path).resolve().as_uri()


def url_to_local_path(url: str) -> Path | None:
    if not url.lower().startswith("file:"):
        return None
    parsed = urlparse(url)
    host_prefix = f"//{parsed.netloc}" if parsed.netloc else ""
    return Path(url2pathname(host_prefix + parsed.path))


def clean_tts_url(url: str) -> str:
    return url.strip().rstrip('"').rstrip("\\").rstrip('"')


def tts_safe_url(url: str) -> str:
    """TTS sniffs the image format from the URL's extension, so cache-buster queries (Scryfall's ?123) must go."""
    if not is_remote_url(url):
        return url
    parsed = urlparse(url)
    if not is_image_file(Path(parsed.path)):
        return url
    return parsed._replace(query="", fragment="").geturl()


@dataclass(frozen=True)
class ImageSource:
    """An image the user can assign to a card face: a local file, a remote URL, or both."""

    local_path: Path | None = None
    remote_url: str | None = None
    label: str = ""

    @staticmethod
    def from_local(path: Path, label: str = "") -> "ImageSource":
        return ImageSource(local_path=Path(path), label=label or Path(path).name)

    @staticmethod
    def from_url(url: str, label: str = "") -> "ImageSource":
        return ImageSource(remote_url=url, label=label or url)

    @staticmethod
    def from_tts_url(url: str) -> "ImageSource":
        cleaned = clean_tts_url(url)
        local = url_to_local_path(cleaned)
        if local is not None:
            return ImageSource(local_path=local, label=local.name)
        return ImageSource(remote_url=cleaned, label=cleaned)

    def display_key(self) -> str:
        if self.local_path is not None:
            return str(self.local_path)
        return self.remote_url or ""

    def to_tts_url(self, prefer_remote: bool) -> str:
        if prefer_remote and self.remote_url:
            return tts_safe_url(self.remote_url)
        if self.local_path is not None:
            return local_path_to_url(self.local_path)
        return tts_safe_url(self.remote_url or "")

    def is_empty(self) -> bool:
        return self.local_path is None and not self.remote_url
