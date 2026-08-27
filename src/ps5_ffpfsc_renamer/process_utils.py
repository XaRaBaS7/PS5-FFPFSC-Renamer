from __future__ import annotations

import os
import subprocess
from typing import Any


def hidden_subprocess_kwargs(*, low_priority: bool = False) -> dict[str, Any]:
    """Return subprocess kwargs that keep child consoles invisible on Windows.

    The packaged MkPFS helper is intentionally a console executable because its
    stdout/stderr are machine-readable by the GUI. When a GUI process launches a
    console executable directly, Windows normally creates a visible console
    window. CREATE_NO_WINDOW plus a hidden STARTUPINFO prevents that visual
    console while preserving captured stdout/stderr.

    ``low_priority`` adds BELOW_NORMAL_PRIORITY_CLASS when available. This does
    not change MkPFS correctness or cap its memory; it simply prevents metadata
    analysis from competing as aggressively with the desktop for CPU time.
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


def run_hidden(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Run a text subprocess without showing a console window on Windows."""
    options = hidden_subprocess_kwargs()
    options.update(kwargs)
    return subprocess.run(command, **options)
