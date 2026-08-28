from __future__ import annotations

from pathlib import Path

import pytest

from ps5_ffpfsc_renamer.metadata import GameMetadata
from ps5_ffpfsc_renamer.rename_plan import PlanStatus, RenamePlanItem
from ps5_ffpfsc_renamer.renamer import apply_rename_plan, build_forward_steps


def _item(source: Path, destination: Path, title_id: str) -> RenamePlanItem:
    return RenamePlanItem(
        source=source,
        destination=destination,
        metadata=GameMetadata(title_id=title_id),
        status=PlanStatus.READY,
    )


def test_batch_failure_rolls_back_earlier_completed_rename(tmp_path: Path) -> None:
    first = tmp_path / "first.ffpfsc"
    second = tmp_path / "second.ffpfsc"
    occupied = tmp_path / "occupied.ffpfsc"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    occupied.write_bytes(b"do-not-overwrite")

    plan = [
        _item(first, tmp_path / "renamed-first.ffpfsc", "PPSA00001"),
        _item(second, occupied, "PPSA00002"),
    ]

    with pytest.raises(FileExistsError):
        apply_rename_plan(plan)

    assert first.read_bytes() == b"first"
    assert second.read_bytes() == b"second"
    assert occupied.read_bytes() == b"do-not-overwrite"
    assert not (tmp_path / "renamed-first.ffpfsc").exists()


def test_batch_failure_recreates_flat_cleanup_folder_before_rollback(tmp_path: Path) -> None:
    old_folder = tmp_path / "Old"
    old_folder.mkdir()
    first = old_folder / "first.ffpfsc"
    second = tmp_path / "second.ffpfsc"
    occupied = tmp_path / "occupied.ffpfsc"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    occupied.write_bytes(b"do-not-overwrite")

    first_destination = tmp_path / "renamed-first.ffpfsc"
    plan = [
        RenamePlanItem(
            source=first,
            destination=first_destination,
            metadata=GameMetadata(title_id="PPSA00001"),
            status=PlanStatus.READY,
            cleanup_directories=(old_folder,),
        ),
        _item(second, occupied, "PPSA00002"),
    ]

    with pytest.raises(FileExistsError):
        apply_rename_plan(plan)

    assert old_folder.exists()
    assert first.read_bytes() == b"first"
    assert not first_destination.exists()
    assert second.read_bytes() == b"second"
    assert occupied.read_bytes() == b"do-not-overwrite"


def test_forward_steps_capture_smart_folder_rename(tmp_path: Path) -> None:
    old_folder = tmp_path / "Old"
    old_folder.mkdir()
    source = old_folder / "game.ffpfsc"
    source.write_bytes(b"image")
    target_folder = tmp_path / "PPSA00003 - Game"
    destination = target_folder / "PPSA00003 - Game.ffpfsc"

    item = RenamePlanItem(
        source=source,
        destination=destination,
        metadata=GameMetadata(title_id="PPSA00003", title_name="Game"),
        status=PlanStatus.READY,
        source_directory=old_folder,
        target_directory=target_folder,
    )

    steps = build_forward_steps([item])

    assert [step.kind for step in steps] == ["rename_dir", "rename_file"]
    assert steps[0].source == old_folder
    assert steps[0].destination == target_folder
    assert steps[1].source == target_folder / "game.ffpfsc"
    assert steps[1].destination == destination


def test_forward_steps_capture_flat_root_cleanup_after_file_move(tmp_path: Path) -> None:
    old_folder = tmp_path / "Old"
    source = old_folder / "game.ffpfsc"
    destination = tmp_path / "PPSA00004.ffpfsc"
    item = RenamePlanItem(
        source=source,
        destination=destination,
        metadata=GameMetadata(title_id="PPSA00004"),
        status=PlanStatus.READY,
        cleanup_directories=(old_folder,),
    )

    steps = build_forward_steps([item])
    assert [step.kind for step in steps] == ["rename_file", "cleanup_dir"]
    assert steps[0].source == source
    assert steps[0].destination == destination
    assert steps[1].destination == old_folder
