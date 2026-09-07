from pathlib import Path

from PySide6.QtCore import QObject, Signal

from deckart_studio.cardmaker.asset_library import CardAssetLibrary
from deckart_studio.cardmaker.card_lookup import CardLookup
from deckart_studio.cardmaker.card_renderer import CardRenderer
from deckart_studio.cardmaker.deck_batch import DeckFaceBatch
from deckart_studio.cardmaker.design_store import DesignStore
from deckart_studio.gallery.gallery_library import GalleryLibrary
from deckart_studio.gallery.thumbnail_loader import ThumbnailLoader
from deckart_studio.hosting.deck_publisher import DeckPublisher
from deckart_studio.hosting.steam_install import SteamStatus, steam_status
from deckart_studio.hosting.upload_index import UploadIndex
from deckart_studio.image_source import ImageSource, is_image_file
from deckart_studio.original_art.original_art_index import OriginalArtIndex
from deckart_studio.original_art.scryfall_client import ScryfallClient
from deckart_studio.settings import AppSettings
from deckart_studio.ui.deck_session import DeckSession


class AppContext(QObject):
    """Everything the widgets share: settings, the open deck, the gallery, art lookups, and thumbnails."""

    galleryChanged = Signal()

    def __init__(self, settings: AppSettings, parent: QObject | None = None):
        super().__init__(parent)
        self.settings = settings
        self.uploads = UploadIndex()
        self.session = DeckSession(settings, self.uploads, self)
        self.gallery = GalleryLibrary(settings)
        self.original_index = OriginalArtIndex(Path(settings.original_art_folder))
        self.scryfall = ScryfallClient()
        self.thumbnails = ThumbnailLoader(self)
        self.card_assets = CardAssetLibrary().load()
        self.card_renderer = CardRenderer(self.card_assets)
        self.design_store = DesignStore(settings.deck_art_root())

    def apply_folder_settings(self) -> None:
        self.settings.save()
        self.original_index = OriginalArtIndex(Path(self.settings.original_art_folder))
        self.design_store = DesignStore(self.settings.deck_art_root())
        self.refresh_gallery()

    def deck_face_batch(self) -> DeckFaceBatch:
        return DeckFaceBatch(CardLookup(self.scryfall), self.card_renderer, self.design_store, self.gallery)

    def deck_publisher(self) -> DeckPublisher:
        return DeckPublisher(self.uploads, self.steam_status().api_dll)

    def steam_status(self) -> SteamStatus:
        return steam_status(self.settings.tts_install_folder)

    def refresh_gallery(self) -> None:
        self.gallery.rescan()
        self.original_index.reload()
        self.galleryChanged.emit()

    def register_dropped_paths(self, paths: list[Path]) -> int:
        added = sum(self._register_path(path) for path in paths)
        if added:
            self.settings.save()
            self.refresh_gallery()
        return added

    def remove_gallery_source(self, source: str) -> None:
        self.settings.remove_gallery_source(source)
        self.settings.save()
        self.refresh_gallery()

    def downloaded_originals_folder(self) -> Path:
        return Path(self.settings.original_art_folder) / "downloaded"

    def source_from_dropped_path(self, path: Path) -> ImageSource | None:
        return ImageSource.from_local(path) if path.is_file() and is_image_file(path) else None

    def _register_path(self, path: Path) -> bool:
        if path.is_dir():
            return self.settings.add_gallery_folder(path)
        if path.is_file() and is_image_file(path):
            return self.settings.add_gallery_file(path)
        return False
