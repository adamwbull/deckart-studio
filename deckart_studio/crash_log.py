"""Windowed EXEs have no console, so unexpected errors are logged to disk and shown in a dialog."""
import logging
import sys
import traceback
from types import TracebackType

from PySide6.QtWidgets import QApplication, QMessageBox

from deckart_studio.settings import log_directory
from deckart_studio.version import APP_NAME, APP_VERSION

LOG_FILE_NAME = "deckart_studio.log"


def install_crash_logging() -> None:
    log_directory().mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_directory() / LOG_FILE_NAME, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger(__name__).info("%s %s starting", APP_NAME, APP_VERSION)
    sys.excepthook = report_uncaught_exception


def report_uncaught_exception(exception_type: type[BaseException], value: BaseException,
                              trace: TracebackType | None) -> None:
    details = "".join(traceback.format_exception(exception_type, value, trace))
    logging.getLogger(__name__).error("Uncaught exception:\n%s", details)
    if QApplication.instance() is not None:
        show_crash_dialog(details)


def show_crash_dialog(details: str) -> None:
    dialog = QMessageBox()
    dialog.setIcon(QMessageBox.Icon.Critical)
    dialog.setWindowTitle(f"{APP_NAME} — something went wrong")
    dialog.setText(f"An unexpected error occurred. Details were written to:\n{log_directory() / LOG_FILE_NAME}")
    dialog.setDetailedText(details)
    dialog.exec()
