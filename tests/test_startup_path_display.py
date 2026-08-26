from __future__ import annotations

import os
from pathlib import Path

from ps5_ffpfsc_renamer.ui.startup_preferences_mixin import StartupPreferencesMixin


def test_full_path_display_does_not_resolve_filesystem(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "Library" / "Returnal" / "game.ffpfsc"
    harness = object.__new__(StartupPreferencesMixin)
    harness._show_relative_paths = False

    def fail_resolve(*_args, **_kwargs):
        raise AssertionError("full path display must not resolve filesystem paths")

    monkeypatch.setattr(Path, "resolve", fail_resolve)

    displayed = harness._display_source(source)
    expected = os.path.normpath(os.path.abspath(os.path.expanduser(str(source))))

    assert displayed == expected
