from __future__ import annotations

from pathlib import Path

import ps5_ffpfsc_renamer.ui.rename_journal_mixin as journal_module
from ps5_ffpfsc_renamer.renamer import RenameStep
from ps5_ffpfsc_renamer.ui.rename_journal_mixin import RenameJournalMixin


class _Var:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


class _Cache:
    def __init__(self) -> None:
        self.updated: list[tuple[Path, Path]] = []

    def update_path_after_rename(self, old: Path, new: Path) -> None:
        self.updated.append((old, new))

    def entry_count(self) -> int:
        return 1


class _History:
    def __init__(self, *, result: str | None = "tx", error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    def record(self, **_kwargs):
        if self.error is not None:
            raise self.error
        return self.result


class _Harness:
    _finalize_completed_rename = RenameJournalMixin._finalize_completed_rename

    def __init__(self, history: _History) -> None:
        self.cache = _Cache()
        self.history = history
        self.cache_entries_var = _Var()
        self.status_var = _Var()
        self.updated_mapping: dict[Path, Path] | None = None
        self.rebuild_calls = 0

    def _update_in_memory_paths(self, mapping: dict[Path, Path]) -> None:
        self.updated_mapping = mapping

    def _rebuild_output_plan(self, *, option_change: bool = False) -> None:
        assert option_change is True
        self.rebuild_calls += 1


def _rename_inputs(tmp_path: Path):
    old = tmp_path / "old.ffpfsc"
    new = tmp_path / "new.ffpfsc"
    completed = [(old, new)]
    steps = [RenameStep("rename_file", old, new)]
    return old, new, completed, steps


def test_finalize_reports_ctrl_z_only_when_history_was_saved(tmp_path: Path, monkeypatch) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(
        journal_module.messagebox,
        "showwarning",
        lambda _title, message, **_kwargs: warnings.append(message),
    )
    old, new, completed, steps = _rename_inputs(tmp_path)
    harness = _Harness(_History(result="transaction-id"))

    harness._finalize_completed_rename(label="Batch rename", completed=completed, steps=steps)

    assert harness._last_rename_undo_available is True
    assert "Ctrl+Z can undo" in harness.status_var.value
    assert "Undo journal unavailable" not in harness.status_var.value
    assert warnings == []
    assert harness.cache.updated == [(old, new)]
    assert harness.updated_mapping == {old: new}
    assert harness.rebuild_calls == 1


def test_finalize_never_promises_ctrl_z_when_history_save_fails(tmp_path: Path, monkeypatch) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(
        journal_module.messagebox,
        "showwarning",
        lambda _title, message, **_kwargs: warnings.append(message),
    )
    _old, _new, completed, steps = _rename_inputs(tmp_path)
    harness = _Harness(_History(error=OSError("history database locked")))

    harness._finalize_completed_rename(label="Batch rename", completed=completed, steps=steps)

    assert harness._last_rename_undo_available is False
    assert "Undo journal unavailable" in harness.status_var.value
    assert "Ctrl+Z can undo" not in harness.status_var.value
    assert len(warnings) == 1
    assert "Ctrl+Z is not available" in warnings[0]
    assert "history database locked" in warnings[0]


def test_finalize_treats_missing_history_transaction_as_no_undo(tmp_path: Path, monkeypatch) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(
        journal_module.messagebox,
        "showwarning",
        lambda _title, message, **_kwargs: warnings.append(message),
    )
    _old, _new, completed, steps = _rename_inputs(tmp_path)
    harness = _Harness(_History(result=None))

    harness._finalize_completed_rename(label="Manual rename", completed=completed, steps=steps)

    assert harness._last_rename_undo_available is False
    assert "Undo journal unavailable" in harness.status_var.value
    assert len(warnings) == 1
    assert "No Undo transaction was created" in warnings[0]
