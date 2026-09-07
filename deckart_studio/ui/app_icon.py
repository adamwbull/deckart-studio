import ctypes
import sys

from PySide6.QtGui import QIcon, QPixmap

from deckart_studio.tools.make_icon import ICON_SIZES, draw_icon

WINDOWS_APP_USER_MODEL_ID = "DeckArtStudio.App"


def application_icon() -> QIcon:
    """The same card-stack icon the EXE carries, rendered at every size Windows asks for."""
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(QPixmap.fromImage(draw_icon(size)))
    return icon


def register_windows_app_id() -> None:
    """Give the process its own taskbar identity so Windows shows our icon instead of the host interpreter's."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        return
