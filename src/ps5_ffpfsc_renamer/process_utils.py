from __future__ import annotations

import os
import subprocess
from typing import Any


def hidden_subprocess_kwargs() -> dict[str, Any]:
    """Return subprocess kwargs that keep child consoles invisible on Windows.

    The packaged MkPFS helper is intentionally a console executable because its
    stdout/stderr are machine-readable by the GUI. When a GUI process launches a
    console executable directly, Windows normally creates a visible console
    window. CREATE_NO_WINDOW plus a hidden STARTUPINFO prevents that visual
    console while preserving captured stdout/stderr.
    """
    if os.name != "nt":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
    return {
        "startupinfo": startupinfo,
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }


def run_hidden(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Run a text subprocess without showing a console window on Windows."""
    options = hidden_subprocess_kwargs()
    options.update(kwargs)
    return subprocess.run(command, **options)
