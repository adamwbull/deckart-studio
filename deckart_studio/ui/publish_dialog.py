from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from deckart_studio.hosting.deck_publisher import PublishResult
from deckart_studio.hosting.tts_compat import describe_unreachable_hosts
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.styles import PRIMARY_BUTTON_STYLE
from deckart_studio.ui.workers import run_in_background


class PublishDialog(QDialog):
    """Upload every local image in the deck to Steam Cloud so other players can see it, then save the deck."""

    def __init__(self, context: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self._progress = QProgressBar()
        self._status = QLabel()
        self._start_button = QPushButton("Upload to Steam Cloud and save deck")
        self._close_button = QPushButton("Cancel")
        self.setWindowTitle("Publish deck images to Steam Cloud")
        self.resize(600, 300)
        self._build()

    def _build(self) -> None:
        self._progress.setRange(0, 0)
        self._progress.hide()
        self._status.setWordWrap(True)
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._start_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self._start_button.setDefault(True)
        self._start_button.clicked.connect(self._start)
        self._close_button.clicked.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self._explanation())
        layout.addWidget(self._steam_check())
        layout.addWidget(self._progress)
        layout.addWidget(self._status)
        layout.addStretch(1)
        layout.addLayout(self._button_row())

    def _explanation(self) -> QLabel:
        label = QLabel(explain_publish(self.context.session.local_image_count(), self.context.session.unreachable_image_count()))
        label.setWordWrap(True)
        return label

    def _steam_check(self) -> QLabel:
        status = self.context.steam_status()
        self._start_button.setEnabled(status.is_ready() and bool(self.context.session.unpublished_image_urls()))
        label = QLabel(status.describe())
        label.setWordWrap(True)
        label.setStyleSheet("color: #7fd18a;" if status.is_ready() else "color: #ff8a80; font-weight: bold;")
        return label

    def _button_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self._close_button)
        row.addWidget(self._start_button)
        return row

    def _start(self) -> None:
        deck_name = self.context.session.deck_name()
        deck_urls = self.context.session.unpublished_image_urls()
        publisher = self.context.deck_publisher()
        self._set_busy(True)
        run_in_background(lambda report: publisher.publish(deck_name, deck_urls, report),
                          self._on_published, self._on_failed, self._status.setText, owner=self)

    def _set_busy(self, busy: bool) -> None:
        self._start_button.setEnabled(not busy)
        self._close_button.setEnabled(not busy)
        self._progress.setVisible(busy)

    def _on_published(self, outcome: object) -> None:
        result: PublishResult = outcome
        replaced = self.context.session.apply_url_replacements(result.url_replacements)
        self.context.session.save()
        self._set_busy(False)
        self._close_button.setText("Close")
        self._close_button.setEnabled(True)
        self._start_button.setEnabled(bool(result.failed))
        self._status.setText(summarize(result, replaced))

    def _on_failed(self, error: str) -> None:
        self._set_busy(False)
        self._status.setText(f"Upload failed:\n{error.strip().splitlines()[-1]}")


def explain_publish(local_count: int, unreachable_count: int) -> str:
    if not local_count and not unreachable_count:
        return "Every image in this deck is already on a host Tabletop Simulator can load - nothing to upload."
    reasons = []
    if local_count:
        reasons.append(f"{local_count} image file(s) live on this PC, so only you can see them")
    if unreachable_count:
        reasons.append(f"{unreachable_count} image(s) are on {describe_unreachable_hosts()}, which Tabletop Simulator "
                       "cannot download at all (its old TLS stack fails the handshake) - cards show as blank or poker "
                       "cards for everyone, including you")
    return ("This deck has " + "; ".join(reasons) + ".\n\nPublishing fetches them, puts them on Steam Cloud under "
            "Tabletop Simulator (the same place TTS's own Cloud Manager uses) and rewrites the deck to the public links "
            "so everyone at the table sees the art.\n\nSteam must be running and logged in. Images already uploaded are "
            "reused, not re-sent.")


def summarize(result: PublishResult, replaced: int) -> str:
    lines = [f"Uploaded {result.uploaded} new image(s), reused {result.reused} earlier upload(s), "
             f"rewrote {replaced} link(s) in the deck. Saved."]
    if result.failed:
        lines.append(f"{len(result.failed)} failed - press Upload again to retry them:")
        lines.extend(result.failed)
    return "\n".join(lines)


def publish_deck(context: AppContext, parent: QWidget | None) -> None:
    if context.session.has_deck():
        PublishDialog(context, parent).exec()
