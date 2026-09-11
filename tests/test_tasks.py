from __future__ import annotations

import logging
import threading

from lite_smb_manager.presentation.tasks import TaskRunner


def test_task_runner_retains_delayed_task_until_gui_finished_callback(qtbot: object) -> None:
    release = threading.Event()
    completed: list[str] = []
    runner = TaskRunner(logging.getLogger("task-runner-test"))

    def delayed_operation() -> str:
        assert release.wait(timeout=1)
        return "done"

    runner.submit(
        delayed_operation,
        lambda value: completed.append(str(value)),
        lambda message: completed.append(message),
        lambda: completed.append("finished"),
    )
    assert runner.active_task_count == 1
    release.set()
    qtbot.waitUntil(lambda: completed == ["done", "finished"], timeout=3000)
    assert runner.active_task_count == 0
    assert runner.wait_for_done()
