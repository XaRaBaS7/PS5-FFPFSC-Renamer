from __future__ import annotations

import os
import subprocess

from ps5_ffpfsc_renamer.process_utils import (
    active_child_process_count,
    hidden_subprocess_kwargs,
    register_child_process,
    terminate_registered_processes,
    unregister_child_process,
)


def test_hidden_subprocess_kwargs_are_platform_safe() -> None:
    options = hidden_subprocess_kwargs()
    if os.name == "nt":
        assert options.get("creationflags", 0) & getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = options.get("startupinfo")
        assert startupinfo is not None
        assert startupinfo.dwFlags & getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    else:
        assert options == {}


def test_low_priority_subprocess_mode_is_safe() -> None:
    options = hidden_subprocess_kwargs(low_priority=True)
    if os.name == "nt":
        flags = options.get("creationflags", 0)
        assert flags & getattr(subprocess, "CREATE_NO_WINDOW", 0)
        below_normal = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
        if below_normal:
            assert flags & below_normal
    else:
        assert options == {}


def test_registered_helpers_are_terminated_and_unregistered() -> None:
    class FakeProcess:
        pid = 9191

        def __init__(self) -> None:
            self.returncode = None
            self.terminated = False

        def poll(self):
            return self.returncode

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = -15

        def wait(self, timeout=None):
            return self.returncode

        def kill(self) -> None:
            self.returncode = -9

    process = FakeProcess()
    register_child_process(process)
    try:
        assert active_child_process_count() >= 1
        assert terminate_registered_processes() >= 1
        assert process.terminated is True
        assert active_child_process_count() == 0
    finally:
        unregister_child_process(process)
