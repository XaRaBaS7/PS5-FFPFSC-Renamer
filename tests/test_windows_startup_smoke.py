from __future__ import annotations

import sys
import tkinter as tk

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows desktop smoke test")
def test_windows_desktop_startup_runs_idle_shell_without_callback_errors(monkeypatch, tmp_path) -> None:
    from ps5_ffpfsc_renamer.desktop import RenamerApp

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    try:
        app = RenamerApp()
    except tk.TclError as exc:
        pytest.skip(f"Tk runtime unavailable on this Windows runner: {exc}")

    callback_errors: list[tuple[object, object, object]] = []
    app.report_callback_exception = lambda exc_type, exc_value, tb: callback_errors.append(
        (exc_type, exc_value, tb)
    )
    try:
        app.update_idletasks()
        app.update()
        assert callback_errors == []
        assert app.winfo_exists()
    finally:
        app.destroy()
