import traceback
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class TaskSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    progressed = Signal(str)


class _CallableTask(QRunnable):
    def __init__(self, work: Callable[[Callable[[str], None]], object], signals: TaskSignals):
        super().__init__()
        self.work = work
        self.signals = signals

    def run(self) -> None:
        try:
            result = self.work(self._report_progress)
        except Exception:
            self._emit_if_owner_alive(self.signals.failed, traceback.format_exc(limit=3))
            return
        self._emit_if_owner_alive(self.signals.succeeded, result)

    def _report_progress(self, message: str) -> None:
        self._emit_if_owner_alive(self.signals.progressed, message)

    @staticmethod
    def _emit_if_owner_alive(signal, payload) -> None:
        try:
            signal.emit(payload)
        except RuntimeError:
            return


def run_in_background(work: Callable[[Callable[[str], None]], object],
                      on_success: Callable[[object], None],
                      on_failure: Callable[[str], None],
                      on_progress: Callable[[str], None] | None = None,
                      owner: QObject | None = None) -> TaskSignals:
    """Run `work(report)` on the global thread pool and deliver its outcome on the GUI thread."""
    signals = TaskSignals(owner)
    signals.succeeded.connect(on_success)
    signals.failed.connect(on_failure)
    if on_progress is not None:
        signals.progressed.connect(on_progress)
    QThreadPool.globalInstance().start(_CallableTask(work, signals))
    return signals
