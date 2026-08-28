from __future__ import annotations

from pathlib import Path

import pytest

from ps5_ffpfsc_renamer.metadata import GameMetadata
from ps5_ffpfsc_renamer.naming import FOLDER_ROOT_FLAT, NamingOptions
from ps5_ffpfsc_renamer.operation_history import HistoryError, OperationHistory
from ps5_ffpfsc_renamer.rename_plan import PlanStatus, RenamePlanItem, build_rename_plan
from ps5_ffpfsc_renamer.renamer import apply_rename_plan, build_forward_steps


def test_history_undo_restores_smart_folder_and_other_files(tmp_path: Path) -> None:
    old_folder = tmp_path / "Old Game"
    old_folder.mkdir()
    source = old_folder / "old-name.ffpfsc"
    source.write_bytes(b"image")
    note = old_folder / "notes.txt"
    note.write_text("keep me", encoding="utf-8")

    new_folder = tmp_path / "PPSA12345 - Example"
    destination = new_folder / "PPSA12345 - Example.ffpfsc"
    item = RenamePlanItem(
        source=source,
        destination=destination,
        metadata=GameMetadata(title_id="PPSA12345", title_name="Example"),
        status=PlanStatus.READY,
        source_directory=old_folder,
        target_directory=new_folder,
    )
    steps = build_forward_steps([item])
    completed = apply_rename_plan([item])

    history = OperationHistory(tmp_path / "history.sqlite3")
    transaction_id = history.record(label="Smart rename", pairs=completed, steps=steps)
    assert transaction_id is not None
    assert destination.exists()
    assert (new_folder / "notes.txt").exists()

    result = history.undo_last()

    assert result.transaction.is_undone
    assert source.exists()
    assert source.read_bytes() == b"image"
    assert note.read_text(encoding="utf-8") == "keep me"
    assert not new_folder.exists()


def test_history_undo_recreates_flat_root_source_folders_before_restoring_file(tmp_path: Path) -> None:
    nested = tmp_path / "Archive" / "Old Game"
    nested.mkdir(parents=True)
    source = nested / "old-name.ffpfsc"
    source.write_bytes(b"image")

    options = NamingOptions(
        include_title_id=True,
        include_title=True,
        folder_handling=FOLDER_ROOT_FLAT,
        library_roots=(str(tmp_path),),
    )
    plan = build_rename_plan(
        [(source, GameMetadata(title_id="PPSA12345", title_name="Example"))],
        options,
    )
    assert plan[0].status is PlanStatus.READY
    steps = build_forward_steps(plan)
    assert [step.kind for step in steps] == ["rename_file", "cleanup_dir", "cleanup_dir"]

    completed = apply_rename_plan(plan)
    destination = plan[0].destination
    assert destination.exists()
    assert not nested.exists()
    assert not (tmp_path / "Archive").exists()

    history = OperationHistory(tmp_path / "history.sqlite3")
    transaction_id = history.record(label="Flatten library", pairs=completed, steps=steps)
    assert transaction_id is not None

    result = history.undo_last()
    assert result.transaction.is_undone
    assert source.exists()
    assert source.read_bytes() == b"image"
    assert not destination.exists()
    assert nested.exists()


def test_history_only_allows_latest_non_undone_transaction(tmp_path: Path) -> None:
    history = OperationHistory(tmp_path / "history.sqlite3")

    first_old = tmp_path / "a.ffpfsc"
    first_new = tmp_path / "a2.ffpfsc"
    first_old.write_bytes(b"a")
    first_old.rename(first_new)
    first_id = history.record(
        label="First",
        pairs=[(first_old, first_new)],
        steps=[],
    )
    # Empty step lists are intentionally not journaled.
    assert first_id is None

    from ps5_ffpfsc_renamer.renamer import RenameStep

    first_old = tmp_path / "b.ffpfsc"
    first_new = tmp_path / "b2.ffpfsc"
    first_old.write_bytes(b"b")
    first_old.rename(first_new)
    first_id = history.record(
        label="First",
        pairs=[(first_old, first_new)],
        steps=[RenameStep("rename_file", first_old, first_new)],
    )

    second_old = tmp_path / "c.ffpfsc"
    second_new = tmp_path / "c2.ffpfsc"
    second_old.write_bytes(b"c")
    second_old.rename(second_new)
    second_id = history.record(
        label="Second",
        pairs=[(second_old, second_new)],
        steps=[RenameStep("rename_file", second_old, second_new)],
    )

    assert first_id and second_id
    with pytest.raises(HistoryError, match="most recent"):
        history.undo(first_id)

    history.undo(second_id)
    assert second_old.exists()
    assert not second_new.exists()

    history.undo(first_id)
    assert first_old.exists()
    assert not first_new.exists()


def test_undo_never_overwrites_recreated_original_path(tmp_path: Path) -> None:
    from ps5_ffpfsc_renamer.renamer import RenameStep

    history = OperationHistory(tmp_path / "history.sqlite3")
    old = tmp_path / "game.ffpfsc"
    new = tmp_path / "renamed.ffpfsc"
    old.write_bytes(b"original")
    old.rename(new)
    history.record(
        label="Rename",
        pairs=[(old, new)],
        steps=[RenameStep("rename_file", old, new)],
    )

    old.write_bytes(b"new unrelated file")
    with pytest.raises(HistoryError, match="cannot overwrite"):
        history.undo_last()

    assert old.read_bytes() == b"new unrelated file"
    assert new.read_bytes() == b"original"
