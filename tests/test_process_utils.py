from __future__ import annotations

import os
import subprocess
import sys
import time

from ps5_ffpfsc_renamer.process_utils import (
    active_child_process_count,
    hidden_subprocess_kwargs,
    process_working_set_bytes,
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


def test_windows_working_set_telemetry_reads_a_live_process() -> None:
    if os.name != "nt":
        return

    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import time; payload=bytearray(8*1024*1024); time.sleep(3)",
        ],
        **hidden_subprocess_kwargs(),
    )
    try:
        measured = None
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline and process.poll() is None:
            measured = process_working_set_bytes(process)
            if measured is not None and measured > 0:
                break
            time.sleep(0.05)
        assert measured is not None
        assert measured > 0
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=3)
