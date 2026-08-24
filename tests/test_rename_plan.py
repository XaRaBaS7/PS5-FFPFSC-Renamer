from pathlib import Path

from ps5_ffpfsc_renamer.metadata import GameMetadata
from ps5_ffpfsc_renamer.rename_plan import PlanStatus, build_rename_plan


def test_ready_plan(tmp_path: Path) -> None:
    source = tmp_path / "wrong-name.ffpfsc"
    source.write_bytes(b"data")
    plan = build_rename_plan([(source, GameMetadata("PPSA01285"))])
    assert plan[0].status is PlanStatus.READY
    assert plan[0].destination.name == "PPSA01285.ffpfsc"


def test_existing_target_blocks(tmp_path: Path) -> None:
    source = tmp_path / "wrong-name.ffpfsc"
    target = tmp_path / "PPSA01285.ffpfsc"
    source.write_bytes(b"source")
    target.write_bytes(b"target")
    plan = build_rename_plan([(source, GameMetadata("PPSA01285"))])
    assert plan[0].status is PlanStatus.COLLISION


def test_duplicate_target_blocks_both(tmp_path: Path) -> None:
    a = tmp_path / "a.ffpfsc"
    b = tmp_path / "b.ffpfsc"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    metadata = GameMetadata("PPSA01285")
    plan = build_rename_plan([(a, metadata), (b, metadata)])
    assert all(item.status is PlanStatus.COLLISION for item in plan)
