from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from deckart_studio.gallery.thumbnail_loader import remote_cache_path
from deckart_studio.net import download_file

THUMBNAIL_WIDTH = 256


def write_save_thumbnail(saved_json_path: Path, face_url: str) -> Path | None:
    """Give a freshly imported saved object the .png preview Tabletop Simulator shows in its object browser."""
    if not face_url:
        return None
    image = QImage(str(download_file(face_url, remote_cache_path(face_url))))
    if image.isNull():
        return None
    thumbnail_path = saved_json_path.with_suffix(".png")
    image.scaledToWidth(THUMBNAIL_WIDTH, Qt.TransformationMode.SmoothTransformation).save(str(thumbnail_path), "PNG")
    return thumbnail_path
