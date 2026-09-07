from pathlib import Path

from PySide6.QtCore import QObject, Signal

from deckart_studio.hosting.tts_compat import describe_unreachable_hosts
from deckart_studio.hosting.upload_index import UploadIndex
from deckart_studio.image_source import ImageSource
from deckart_studio.settings import AppSettings
from deckart_studio.tts.board import Board
from deckart_studio.tts.card_face import CardFace
from deckart_studio.tts.deck_document import DeckDocument
from deckart_studio.tts.object_factory import BuiltCard


class DeckSession(QObject):
    """The currently open deck, the stack being viewed, and change notifications for every view that renders it."""

    deckLoaded = Signal()
    cardsReset = Signal()
    boardsChanged = Signal()
    facesChanged = Signal(list)
    backsChanged = Signal()
    dirtyChanged = Signal(bool)
    statusMessage = Signal(str)

    def __init__(self, settings: AppSettings, uploads: UploadIndex, parent: QObject | None = None):
        super().__init__(parent)
        self.settings = settings
        self.uploads = uploads
        self.document: DeckDocument | None = None
        self.active_board_index = 0

    def open_deck(self, path: Path) -> None:
        self.document = DeckDocument.load(path)
        self.active_board_index = 0
        self.settings.last_deck_path = str(path)
        self.settings.save()
        repaired = self.document.sanitize_image_urls()
        self._announce_structure_change()
        self.deckLoaded.emit()
        self.dirtyChanged.emit(repaired > 0)
        self.statusMessage.emit(self._opened_message(path, repaired))

    def _opened_message(self, path: Path, repaired: int) -> str:
        message = f"Opened {path.name} ({len(self.all_cards())} cards in {len(self.boards())} stack(s))"
        if repaired:
            message += f" — fixed {repaired} image link(s) TTS could not load; press Save to keep the fix"
        warning = self.publish_warning()
        return f"{message}. {warning}" if warning else message

    def close_deck(self) -> None:
        self.document = None
        self.active_board_index = 0
        self._announce_structure_change()
        self.deckLoaded.emit()

    def has_deck(self) -> bool:
        return self.document is not None

    def boards(self) -> list[Board]:
        return self.document.boards() if self.document else []

    def board_names(self) -> list[str]:
        return [board.name for board in self.boards()]

    def active_board(self) -> Board | None:
        boards = self.boards()
        if not boards:
            return None
        self.active_board_index = min(self.active_board_index, len(boards) - 1)
        return boards[self.active_board_index]

    def set_active_board(self, index: int) -> None:
        if index != self.active_board_index and 0 <= index < len(self.boards()):
            self.active_board_index = index
            self.cardsReset.emit()

    def add_board(self, name: str) -> None:
        if self.document is None or not name.strip():
            return
        self.document.add_board(name.strip())
        self.active_board_index = len(self.boards()) - 1
        self._announce_structure_change()
        self._announce_dirty(f"Added stack {name.strip()}")

    def rename_active_board(self, name: str) -> None:
        board = self.active_board()
        if board is None or board.is_loose or not name.strip():
            return
        self.document.rename_board(board, name.strip())
        self.boardsChanged.emit()
        self._announce_dirty(f"Renamed stack to {name.strip()}")

    def delete_active_board(self) -> None:
        board = self.active_board()
        if board is None:
            return
        self.document.delete_board(board)
        self.active_board_index = max(0, self.active_board_index - 1)
        self._announce_structure_change()
        self._announce_dirty(f"Removed stack {board.name} ({board.card_count()} cards)")

    def cards(self) -> list[CardFace]:
        board = self.active_board()
        return board.cards if board else []

    def all_cards(self) -> list[CardFace]:
        return self.document.cards() if self.document else []

    def card(self, index: int) -> CardFace | None:
        cards = self.cards()
        return cards[index] if 0 <= index < len(cards) else None

    def face_key(self, index: int) -> str:
        card = self.card(index)
        return self.face_source(card).display_key() if card else ""

    def face_source(self, card: CardFace) -> ImageSource:
        """The card's face, preferring the local original of an image we uploaded to the cloud."""
        source = card.face_source()
        if source.local_path is not None or not source.remote_url:
            return source
        local = self.uploads.local_path_for(source.remote_url)
        if local is None:
            return source
        return ImageSource(local_path=local, remote_url=source.remote_url, label=local.name)

    def common_back_source(self) -> ImageSource:
        """The back image shared by most cards in the whole save, resolved to a local file when we uploaded it."""
        boards = self.boards()
        if not boards:
            return ImageSource()
        back_url = boards[0].common_back_url()
        source = ImageSource.from_tts_url(back_url)
        local = self.uploads.local_path_for(back_url) if source.local_path is None else None
        return ImageSource(local_path=local, remote_url=back_url, label=local.name) if local else source

    def local_image_count(self) -> int:
        return len(self.document.local_image_paths()) if self.document else 0

    def unreachable_image_count(self) -> int:
        return len(self.document.unreachable_image_urls()) if self.document else 0

    def unpublished_image_urls(self) -> list[str]:
        return self.document.unpublished_image_urls() if self.document else []

    def publish_warning(self) -> str:
        """One line telling the user why Publish is still needed, or an empty string when the deck is table-ready."""
        local, unreachable = self.local_image_count(), self.unreachable_image_count()
        if not local and not unreachable:
            return ""
        parts = [f"{local} image(s) only exist on this PC" if local else "",
                 f"{unreachable} image(s) are on a host TTS cannot load ({describe_unreachable_hosts()})" if unreachable else ""]
        return " and ".join(part for part in parts if part) + " — use Publish to Steam Cloud."

    def deck_name(self) -> str:
        return self.document.name if self.document else "loose"

    def render_scope_name(self) -> str:
        """Folder-safe name for rendered faces: the deck for the first stack, deck + stack for the others."""
        return self.render_scope_name_for(self.active_board_index)

    def render_scope_name_for(self, board_index: int) -> str:
        if board_index <= 0:
            return self.deck_name()
        boards = self.boards()
        if board_index >= len(boards):
            return self.deck_name()
        return f"{self.deck_name()} - {boards[board_index].name}"

    def add_cards(self, built: BuiltCard, quantity: int = 1) -> None:
        board = self.active_board()
        if board is None or self.document is None:
            return
        for _ in range(max(1, quantity)):
            self.document.add_card(board, built)
        self._announce_structure_change()
        self._announce_dirty(f"Added {quantity}× {built.name} to {board.name}")

    def remove_card(self, index: int) -> None:
        card = self.card(index)
        if card is None:
            return
        self.document.remove_card(card)
        self._announce_structure_change()
        self._announce_dirty(f"Removed {card.nickname}")

    def make_commander(self, index: int) -> None:
        """Move the card into the commander stack (created beside the main deck when missing) and show that stack."""
        card = self.card(index)
        if card is None:
            return
        target = self.document.split_commanders([card])
        self.active_board_index = next(index for index, board in enumerate(self.boards()) if board.container is target.container)
        self._announce_structure_change()
        self._announce_dirty(f"{card.nickname} is now in the {target.name} stack")

    def move_card(self, index: int, target_board_index: int) -> None:
        card = self.card(index)
        boards = self.boards()
        if card is None or not 0 <= target_board_index < len(boards) or target_board_index == self.active_board_index:
            return
        self.document.move_card(card, boards[target_board_index])
        self._announce_structure_change()
        self._announce_dirty(f"Moved {card.nickname} to {boards[target_board_index].name}")

    def assign_face(self, index: int, source: ImageSource) -> None:
        card = self.card(index)
        if card is None or source.is_empty() or self._already_shows(card, source):
            return
        self.document.set_face(card, self._url_for(source))
        self._announce_change([index], f"Set face of {card.nickname} to {source.label}")

    def assign_faces(self, sources_by_index: dict[int, ImageSource]) -> None:
        changed = [index for index, source in sources_by_index.items() if self._set_face_silently(index, source)]
        if changed:
            self._announce_change(changed, f"Replaced {len(changed)} card faces")

    def assign_board_faces(self, assignments: list[tuple[int, int, ImageSource]]) -> None:
        if self.document is None:
            return
        boards = self.boards()
        changed = 0
        for board_index, card_index, source in assignments:
            if source.is_empty() or board_index >= len(boards) or card_index >= len(boards[board_index].cards):
                continue
            self.document.set_face(boards[board_index].cards[card_index], self._url_for(source))
            changed += 1
        if changed:
            self.cardsReset.emit()
            self._announce_dirty(f"Replaced {changed} card faces")

    def _set_face_silently(self, index: int, source: ImageSource) -> bool:
        card = self.card(index)
        if card is None or source.is_empty():
            return False
        self.document.set_face(card, self._url_for(source))
        return True

    def _already_shows(self, card: CardFace, source: ImageSource) -> bool:
        return self._url_for(card.face_source()) == self._url_for(source)

    def assign_all_faces(self, source: ImageSource) -> None:
        if self.document is None or source.is_empty():
            return
        self.document.set_all_faces(self._url_for(source))
        self._announce_change([], f"Set every face to {source.label}")

    def assign_all_backs(self, source: ImageSource) -> None:
        if self.document is None or source.is_empty():
            return
        self.document.set_all_backs(self._url_for(source))
        self.backsChanged.emit()
        self._announce_change([], f"Set every card back to {source.label}")

    def apply_url_replacements(self, replacements: dict[str, str]) -> int:
        if self.document is None or not replacements:
            return 0
        replaced = self.document.replace_image_urls(replacements)
        if replaced:
            self.facesChanged.emit([])
            self.backsChanged.emit()
            self.dirtyChanged.emit(True)
        return replaced

    def save(self) -> None:
        if self.document is None:
            return
        self.document.sanitize_image_urls()
        self.document.save()
        self.dirtyChanged.emit(False)
        self.statusMessage.emit(f"Saved {self.document.path.name}")

    def save_as(self, path: Path) -> None:
        if self.document is None:
            return
        self.document.save_as(path)
        self.settings.last_deck_path = str(path)
        self.settings.save()
        self.dirtyChanged.emit(False)
        self.statusMessage.emit(f"Saved as {path.name}")

    def _url_for(self, source: ImageSource) -> str:
        return source.to_tts_url(prefer_remote=self.settings.prefer_remote_original_urls)

    def _announce_structure_change(self) -> None:
        self.boardsChanged.emit()
        self.cardsReset.emit()
        self.backsChanged.emit()

    def _announce_dirty(self, message: str) -> None:
        self.dirtyChanged.emit(True)
        self.statusMessage.emit(message)

    def _announce_change(self, indices: list[int], message: str) -> None:
        self.facesChanged.emit(indices)
        self._announce_dirty(message)
