import sys

from PySide6.QtWidgets import QApplication

from deckart_studio.crash_log import install_crash_logging
from deckart_studio.selftest import run_selftest
from deckart_studio.settings import AppSettings
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.app_icon import application_icon, register_windows_app_id
from deckart_studio.ui.main_window import MainWindow
from deckart_studio.version import APP_NAME, APP_VERSION

DARK_STYLESHEET = """
QWidget { background: #1b1d22; color: #d7dde5; font-size: 13px; }
QToolBar { background: #23262d; spacing: 6px; padding: 4px; }
QTabWidget::pane { border: 1px solid #333; }
QTabBar::tab { background: #23262d; padding: 8px 14px; }
QTabBar::tab:selected { background: #2f3542; }
QFrame[frameShape="6"] { border: 1px solid #333; border-radius: 6px; background: #23262d; }
QScrollArea { border: none; }
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QListWidget { background: #14161a; border: 1px solid #333; padding: 4px; }
QPushButton { background: #2f3542; border: 1px solid #444; padding: 6px 10px; border-radius: 4px; }
QPushButton:hover { background: #3a4152; }
QDockWidget::title { background: #23262d; padding: 6px; }
"""


def main() -> int:
    if "--selftest" in sys.argv:
        return run_selftest(sys.argv[1:])
    return run_gui()


def run_gui() -> int:
    install_crash_logging()
    register_windows_app_id()
    application = QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setApplicationVersion(APP_VERSION)
    application.setWindowIcon(application_icon())
    application.setStyleSheet(DARK_STYLESHEET)
    context = AppContext(AppSettings.load())
    context.refresh_gallery()
    window = MainWindow(context)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
