from __future__ import annotations

from ps5_ffpfsc_renamer import gui


def test_gui_entrypoint_tracks_latest_desktop_shell() -> None:
    assert gui.RenamerApp.__module__.endswith("gui_v21")
    assert gui.__all__ == ["RenamerApp", "main"]
