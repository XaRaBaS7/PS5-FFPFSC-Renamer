from pathlib import Path

from ps5_ffpfsc_renamer.library_view import (
    ResultRow,
    duplicate_title_ids,
    human_size,
    matches_filter,
    matches_search,
)


def _row(**overrides) -> ResultRow:
    values = dict(
        source=Path(r"G:\PS5\Returnal\game.ffpfsc"),
        title_id="PPSA01285",
        title="Returnal",
        version="01.000.000",
        size=42 * 1024**3,
        output="Returnal - PPSA01285.ffpfsc",
        status="READY",
        duplicate=False,
    )
    values.update(overrides)
    return ResultRow(**values)


def test_human_size() -> None:
    assert human_size(None) == "-"
    assert human_size(0) == "0 B"
    assert human_size(1024) == "1.0 KB"
    assert human_size(5 * 1024**3) == "5.0 GB"


def test_search_matches_multiple_tokens_across_fields() -> None:
    row = _row()
    assert matches_search(row, "returnal ppsa01285")
    assert matches_search(row, "G: game")
    assert not matches_search(row, "spider man")


def test_status_and_duplicate_filters() -> None:
    row = _row(duplicate=True)
    assert matches_filter(row, "ALL")
    assert matches_filter(row, "READY")
    assert matches_filter(row, "DUPLICATES")
    assert not matches_filter(row, "ERROR")


def test_duplicate_title_ids_ignores_missing_ids() -> None:
    rows = [
        _row(source=Path("a.ffpfsc")),
        _row(source=Path("b.ffpfsc")),
        _row(source=Path("c.ffpfsc"), title_id="-"),
    ]
    assert duplicate_title_ids(rows) == {"PPSA01285"}
