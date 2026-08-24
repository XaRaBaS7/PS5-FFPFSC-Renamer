from pathlib import Path

from ps5_ffpfsc_renamer.metadata import GameMetadata
from ps5_ffpfsc_renamer.naming import NamingOptions
from ps5_ffpfsc_renamer.rename_plan import PlanStatus, build_rename_plan
from ps5_ffpfsc_renamer.renamer import apply_rename_plan


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


def test_full_name_and_folder_destination(tmp_path: Path) -> None:
    source = tmp_path / "Returnal.ffpfsc"
    source.write_bytes(b"data")
    metadata = GameMetadata(
        "PPSA01285",
        title_name="Returnal",
        content_version="01.000.000",
    )
    options = NamingOptions(
        include_title_id=True,
        include_title=True,
        include_version=True,
        create_folder=True,
    )

    plan = build_rename_plan([(source, metadata)], options)
    item = plan[0]
    assert item.status is PlanStatus.READY
    assert item.target_directory == tmp_path / "PPSA01285 - Returnal - v1.0"
    assert item.destination == (
        tmp_path
        / "PPSA01285 - Returnal - v1.0"
        / "PPSA01285 - Returnal - v1.0.ffpfsc"
    )

    completed = apply_rename_plan(plan)
    assert completed == [(source.resolve(), item.destination)]
    assert item.destination.read_bytes() == b"data"
    assert not source.exists()


def test_existing_output_folder_can_be_used_when_target_is_free(tmp_path: Path) -> None:
    source = tmp_path / "game.ffpfsc"
    source.write_bytes(b"data")
    folder = tmp_path / "PPSA01285"
    folder.mkdir()

    plan = build_rename_plan(
        [(source, GameMetadata("PPSA01285"))],
        NamingOptions(create_folder=True),
    )
    assert plan[0].status is PlanStatus.READY


def test_file_occupying_output_folder_blocks(tmp_path: Path) -> None:
    source = tmp_path / "game.ffpfsc"
    source.write_bytes(b"data")
    (tmp_path / "PPSA01285").write_bytes(b"occupied")

    plan = build_rename_plan(
        [(source, GameMetadata("PPSA01285"))],
        NamingOptions(create_folder=True),
    )
    assert plan[0].status is PlanStatus.COLLISION
