from __future__ import annotations

import subprocess
import sys


def test_gui_v9_record_alias_does_not_load_legacy_gui_chain() -> None:
    code = r'''
import sys
from ps5_ffpfsc_renamer.gui_v9 import _Record
assert _Record.__module__ == "ps5_ffpfsc_renamer.workspace_models"
for name in (
    "ps5_ffpfsc_renamer.gui_v9_legacy",
    "ps5_ffpfsc_renamer.gui_v8",
    "ps5_ffpfsc_renamer.gui_v7",
    "ps5_ffpfsc_renamer.gui_v6",
):
    assert name not in sys.modules, name
'''
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_gui_v9_legacy_class_is_still_available_on_demand() -> None:
    code = r'''
from ps5_ffpfsc_renamer.gui_v9 import RenamerApp
assert RenamerApp.__module__ == "ps5_ffpfsc_renamer.gui_v9_legacy"
'''
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
