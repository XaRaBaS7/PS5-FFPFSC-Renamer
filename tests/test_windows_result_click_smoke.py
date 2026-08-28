from __future__ import annotations

import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows desktop interaction smoke test")
def test_windows_result_row_selection_has_no_callback_error(monkeypatch, tmp_path) -> None:
    from ps5_ffpfsc_renamer.desktop import RenamerApp
    from ps5_ffpfsc_renamer.library_view import ResultRow
    from ps5_ffpfsc_renamer.workspace_models import LibraryRecord

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    app = RenamerApp()
    callback_errors: list[tuple[object, object, object]] = []
    app.report_callback_exception = lambda exc_type, exc_value, tb: callback_errors.append(
        (exc_type, exc_value, tb)
    )
    try:
        source = Path(r"C:\FFPFSC\PPSA32785 - Nioh 3 - v1.04.20.ffpfsc")
        record = LibraryRecord(
            ResultRow(
                source=source,
                title_id="PPSA32785",
                title="Nioh 3",
                version="01.040.020",
                size=81_900_000_000,
                output=source.name,
                status="UNCHANGED",
            )
        )
        row = app.tree.insert(
            "",
            "end",
            values=(source.name, "PPSA32785", "Nioh 3", "01.040.020", "81.9 GB", source.name, "UNCHANGED"),
        )
        app._row_records[row] = record
        app._row_sources[row] = source

        app.tree.selection_set(row)
        app.tree.focus(row)
        app.update_idletasks()
        app.update()

        assert callback_errors == [], [f"{getattr(t, '__name__', t)}: {v}" for t, v, _tb in callback_errors]
    finally:
        app.destroy()
