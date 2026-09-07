from pathlib import Path

from PySide6.QtCore import QMimeData, QUrl

from deckart_studio.image_source import ImageSource, is_image_file

SOURCE_MIME_TYPE = "application/x-deckart-image-source"


def mime_for_source(source: ImageSource) -> QMimeData:
    mime = QMimeData()
    mime.setData(SOURCE_MIME_TYPE, source_to_bytes(source))
    if source.local_path is not None:
        mime.setUrls([QUrl.fromLocalFile(str(source.local_path))])
    elif source.remote_url:
        mime.setUrls([QUrl(source.remote_url)])
    return mime


def source_to_bytes(source: ImageSource) -> bytes:
    return "\n".join([str(source.local_path or ""), source.remote_url or "", source.label]).encode("utf-8")


def source_from_bytes(payload: bytes) -> ImageSource:
    local, remote, label = (payload.decode("utf-8").split("\n") + ["", "", ""])[:3]
    return ImageSource(local_path=Path(local) if local else None, remote_url=remote or None, label=label)


def accepts_image_drop(mime: QMimeData) -> bool:
    return mime.hasFormat(SOURCE_MIME_TYPE) or any_image_or_folder(mime)


def any_image_or_folder(mime: QMimeData) -> bool:
    return any(is_image_url(url) or is_folder_url(url) for url in mime.urls())


def is_image_url(url: QUrl) -> bool:
    if url.isLocalFile():
        return is_image_file(Path(url.toLocalFile()))
    return url.scheme() in ("http", "https")


def is_folder_url(url: QUrl) -> bool:
    return url.isLocalFile() and Path(url.toLocalFile()).is_dir()


def sources_from_mime(mime: QMimeData) -> list[ImageSource]:
    if mime.hasFormat(SOURCE_MIME_TYPE):
        return [source_from_bytes(bytes(mime.data(SOURCE_MIME_TYPE)))]
    return [source for source in (source_from_url(url) for url in mime.urls()) if source is not None]


def source_from_url(url: QUrl) -> ImageSource | None:
    if url.isLocalFile():
        path = Path(url.toLocalFile())
        return ImageSource.from_local(path) if is_image_file(path) else None
    if url.scheme() in ("http", "https"):
        return ImageSource.from_url(url.toString())
    return None


def local_paths_from_mime(mime: QMimeData) -> list[Path]:
    return [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]
