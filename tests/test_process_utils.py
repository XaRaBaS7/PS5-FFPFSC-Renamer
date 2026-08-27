from __future__ import annotations

import os
import subprocess

from ps5_ffpfsc_renamer.process_utils import hidden_subprocess_kwargs


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
