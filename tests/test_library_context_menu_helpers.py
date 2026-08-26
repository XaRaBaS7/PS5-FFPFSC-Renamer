from pathlib import Path

from ps5_ffpfsc_renamer.library_view import ResultRow
from ps5_ffpfsc_renamer.ui.library_context_menu_mixin import LibraryContextMenuMixin
from ps5_ffpfsc_renamer.workspace_models import LibraryRecord


def _record(title_id: str, title: str) -> LibraryRecord:
    return LibraryRecord(
        ResultRow(
            source=Path(f"{title_id or 'missing'}.ffpfsc"),
            title_id=title_id,
            title=title,
            version="1.0",
            size=1,
            output="-",
            status="READY",
        )
    )


def test_selected_title_ids_are_unique_and_ignore_missing() -> None:
    records = [
        _record("PPSA01285", "Returnal"),
        _record("ppsa01285", "Returnal duplicate"),
        _record("PPSA05366", "A Plague Tale: Requiem"),
        _record("-", "Unknown"),
    ]

    assert LibraryContextMenuMixin._selected_title_ids(records) == [
        "PPSA01285",
        "PPSA05366",
    ]


def test_selected_catalog_lines_keep_first_title_per_id() -> None:
    records = [
        _record("PPSA01285", "Returnal"),
        _record("PPSA01285", "Duplicate title"),
        _record("PPSA05366", "A Plague Tale: Requiem"),
    ]

    assert LibraryContextMenuMixin._selected_catalog_lines(records) == [
        "PPSA01285 - Returnal",
        "PPSA05366 - A Plague Tale: Requiem",
    ]
