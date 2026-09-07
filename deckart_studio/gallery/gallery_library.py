import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from deckart_studio.cardmaker.design_store import RENDERED_FOLDER_NAME
from deckart_studio.image_source import is_image_file
from deckart_studio.settings import AI_FOLDER_SUFFIX, AppSettings

EXCLUDED_FOLDER_NAMES = {RENDERED_FOLDER_NAME}


class GallerySection(Enum):
    HANDPICKED = "Handpicked"
    AI_RECOMMENDED = "AI Recommended"
    ORIGINAL = "Original"


LOOSE_FILES_GROUP = "Added files"
GROUP_SEPARATOR = " / "


@dataclass(frozen=True)
class GalleryImage:
    path: Path
    section: GallerySection
    group: str = ""

    @property
    def label(self) -> str:
        return self.path.stem


class GalleryLibrary:
    """All images registered from the user's gallery sources, bucketed into picker sections and folder groups."""

    def __init__(self, settings: AppSettings):
        self.settings = settings
        self._images: list[GalleryImage] = []

    def rescan(self) -> None:
        original_root = Path(self.settings.original_art_folder).resolve()
        unique: dict[Path, str] = {}
        for path, group in self._iter_source_paths():
            unique.setdefault(path, group)
        self._images = [GalleryImage(path, classify_section(path, original_root), group) for path, group in unique.items()]

    def images(self, section: GallerySection) -> list[GalleryImage]:
        return [image for image in self._images if image.section == section]

    def all_images(self) -> list[GalleryImage]:
        return list(self._images)

    def contains(self, path: Path) -> bool:
        resolved = Path(path).resolve()
        return any(image.path == resolved for image in self._images)

    def _iter_source_paths(self):
        for folder in self.settings.gallery_folders:
            root = Path(folder).resolve()
            for path in iter_images_recursively(root):
                yield path, group_name_for(path, root)
        for file in self.settings.gallery_files:
            path = Path(file)
            if path.is_file() and is_image_file(path):
                yield path.resolve(), LOOSE_FILES_GROUP


def group_name_for(path: Path, root: Path) -> str:
    """"doctorwho / companions" for a file two folders below the gallery root; the root's own name at the top."""
    relative_parts = path.parent.relative_to(root).parts if is_inside(path, root) else ()
    return GROUP_SEPARATOR.join(relative_parts) if relative_parts else root.name


def iter_images_recursively(folder: Path):
    if not folder.is_dir():
        return
    for root, directories, files in os.walk(folder):
        directories[:] = [name for name in directories if name.lower() not in EXCLUDED_FOLDER_NAMES]
        for filename in sorted(files, key=str.lower):
            path = Path(root) / filename
            if is_image_file(path):
                yield path.resolve()


def classify_section(path: Path, original_root: Path) -> GallerySection:
    if is_inside(path, original_root):
        return GallerySection.ORIGINAL
    if any(part.lower().endswith(AI_FOLDER_SUFFIX) for part in path.parent.parts):
        return GallerySection.AI_RECOMMENDED
    return GallerySection.HANDPICKED


def is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
