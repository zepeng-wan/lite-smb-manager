"""Qt task runner that keeps SMB and status work off the GUI thread."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from lite_smb_manager.application.ports import ApplicationError


class TaskSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()


class _Task(QRunnable):
    def __init__(self, operation: Callable[[], Any], logger: logging.Logger) -> None:
        super().__init__()
        self.signals = TaskSignals()
        self._operation = operation
        self._logger = logger

    @Slot()
    def run(self) -> None:
        try:
            self.signals.succeeded.emit(self._operation())
        except ApplicationError as error:
            self.signals.failed.emit(error.message)
        except Exception:
            self._logger.exception("Unexpected background task failure")
            self.signals.failed.emit("操作失败，请查看诊断日志后重试。")
        finally:
            self.signals.finished.emit()


class TaskRunner:
    """Owns a QThreadPool and dispatches result signals to the GUI event loop."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(4)
        self._active_tasks: set[_Task] = set()

    def submit(
        self,
        operation: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_failure: Callable[[str], None],
        on_finished: Callable[[], None],
    ) -> None:
        task = _Task(operation, self._logger)
        self._active_tasks.add(task)
        task.signals.succeeded.connect(on_success)
        task.signals.failed.connect(on_failure)

        def finish_and_release() -> None:
            try:
                on_finished()
            finally:
                self._active_tasks.discard(task)

        task.signals.finished.connect(finish_and_release)
        self._pool.start(task)

    @property
    def active_task_count(self) -> int:
        """Return retained tasks; useful for orderly shutdown and UI tests."""
        return len(self._active_tasks)

    def wait_for_done(self, timeout_ms: int = 3000) -> bool:
        return self._pool.waitForDone(timeout_ms)
