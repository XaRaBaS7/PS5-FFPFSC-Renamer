from __future__ import annotations

from types import SimpleNamespace

from ps5_ffpfsc_renamer.ui.game_details_mixin import GameDetailsMixin


class _Tree:
    def __init__(self, rows=("row-1",)) -> None:
        self._rows = rows

    def selection(self):
        return self._rows


def test_row_selection_does_not_load_details_while_panel_is_hidden() -> None:
    ui = object.__new__(GameDetailsMixin)
    ui.tree = _Tree()
    record = SimpleNamespace(view=SimpleNamespace(source="game.ffpfsc"))
    ui._row_records = {"row-1": record}
    ui._details_visible = False
    calls = []
    ui._activate_details_record = lambda selected, **kwargs: calls.append((selected, kwargs))

    GameDetailsMixin._on_details_selection(ui)

    assert calls == [(record, {"load": False})]


def test_row_selection_loads_details_only_after_panel_is_visible() -> None:
    ui = object.__new__(GameDetailsMixin)
    ui.tree = _Tree()
    record = SimpleNamespace(view=SimpleNamespace(source="game.ffpfsc"))
    ui._row_records = {"row-1": record}
    ui._details_visible = True
    calls = []
    ui._activate_details_record = lambda selected, **kwargs: calls.append((selected, kwargs))

    GameDetailsMixin._on_details_selection(ui)

    assert calls == [(record, {"load": True})]
