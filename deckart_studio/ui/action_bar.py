from typing import Callable

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from deckart_studio.ui.styles import ACTION_BAR_BUTTON_STYLE


class ActionBar(QFrame):
    """Deck-wide actions that are not tied to the card currently on screen."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(10, 6, 10, 6)
        self._deck_dependent: list[QPushButton] = []
        self._publish_hint = warning_label()

    def add_action(self, text: str, handler: Callable[[], None], tooltip: str = "",
                   needs_deck: bool = True) -> QPushButton:
        button = QPushButton(text)
        button.setStyleSheet(ACTION_BAR_BUTTON_STYLE)
        button.setToolTip(tooltip)
        button.clicked.connect(handler)
        self._layout.addWidget(button)
        if needs_deck:
            self._deck_dependent.append(button)
        return button

    def add_trailing(self, widget: QWidget) -> None:
        self._layout.addWidget(self._publish_hint, 1)
        self._layout.addWidget(widget)

    def set_deck_open(self, is_open: bool) -> None:
        for button in self._deck_dependent:
            button.setEnabled(is_open)

    def set_publish_hint(self, text: str) -> None:
        self._publish_hint.setText(f"⚠ {text}" if text else "")
        self._publish_hint.setVisible(bool(text))


def hint_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("color: #888;")
    return label


def warning_label() -> QLabel:
    label = QLabel()
    label.setStyleSheet("color: #ffb74d; font-weight: bold; padding-left: 12px;")
    label.setWordWrap(True)
    label.hide()
    return label
