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
