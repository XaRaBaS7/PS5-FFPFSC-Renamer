from __future__ import annotations

import ctypes
import os
import subprocess
import threading
from typing import Any


DEFAULT_MKPFS_MEMORY_LIMIT_BYTES = 1024 * 1024 * 1024

_active_processes_lock = threading.Lock()
_active_processes: dict[int, subprocess.Popen[Any]] = {}


def hidden_subprocess_kwargs(*, low_priority: bool = False) -> dict[str, Any]:
    """Return subprocess kwargs that keep child consoles invisible on Windows.

    The packaged MkPFS helper is intentionally a console executable because its
    stdout/stderr are machine-readable by the GUI. When a GUI process launches a
    console executable directly, Windows normally creates a visible console
    window. CREATE_NO_WINDOW plus a hidden STARTUPINFO prevents that visual
    console while preserving captured stdout/stderr.

    ``low_priority`` adds BELOW_NORMAL_PRIORITY_CLASS when available. Memory is
    guarded separately by the MkPFS polling loop so an unexpected image layout
    cannot consume the machine's available RAM.
    """
    if os.name != "nt":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if low_priority:
        flags |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)

    return {
        "startupinfo": startupinfo,
        "creationflags": flags,
    }


def register_child_process(process: subprocess.Popen[Any]) -> None:
    """Track a helper process so application shutdown can never orphan it."""
    pid = int(getattr(process, "pid", 0) or 0)
    if pid <= 0:
        return
    with _active_processes_lock:
        _active_processes[pid] = process


def unregister_child_process(process: subprocess.Popen[Any]) -> None:
    pid = int(getattr(process, "pid", 0) or 0)
    if pid <= 0:
        return
    with _active_processes_lock:
        current = _active_processes.get(pid)
        if current is process:
            _active_processes.pop(pid, None)


def active_child_process_count() -> int:
    """Return the number of registered helper processes that are still alive."""
    with _active_processes_lock:
        processes = list(_active_processes.values())
    return sum(1 for process in processes if process.poll() is None)


def terminate_registered_processes() -> int:
    """Terminate any helper left alive during application shutdown."""
    with _active_processes_lock:
        processes = list(_active_processes.values())

    terminated = 0
    for process in processes:
        try:
            if process.poll() is not None:
                unregister_child_process(process)
                continue
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
            terminated += 1
        except Exception:
            try:
                process.kill()
            except Exception:
                pass
        finally:
            unregister_child_process(process)
    return terminated


def process_working_set_bytes(process: subprocess.Popen[Any]) -> int | None:
    """Return current resident memory for a Windows child process.

    ``None`` means the metric is unavailable. The function intentionally uses
    the handle already owned by ``subprocess.Popen`` and never opens a broader
    process handle. Non-Windows platforms simply return ``None``.
    """
    if os.name != "nt":
        return None

    handle = getattr(process, "_handle", None)
    if handle is None:
        return None

    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(counters)
    try:
        get_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
        ok = get_memory_info(
            ctypes.c_void_p(int(handle)),
            ctypes.byref(counters),
            counters.cb,
        )
    except (AttributeError, OSError, TypeError, ValueError):
        return None
    if not ok:
        return None
    return int(counters.WorkingSetSize)


def run_hidden(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Run a text subprocess without showing a console window on Windows."""
    options = hidden_subprocess_kwargs()
    options.update(kwargs)
    return subprocess.run(command, **options)
