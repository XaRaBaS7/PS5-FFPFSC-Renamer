from pathlib import Path

from ps5_ffpfsc_renamer.metadata import GameMetadata
from ps5_ffpfsc_renamer.naming import (
    FOLDER_ALWAYS_NEW,
    FOLDER_FILE_ONLY,
    FOLDER_SMART,
    NamingOptions,
)
from ps5_ffpfsc_renamer.rename_plan import PlanStatus, build_rename_plan
from ps5_ffpfsc_renamer.renamer import apply_rename_plan


def _metadata() -> GameMetadata:
    return GameMetadata(
        "PPSA01285",
        title_name="Returnal",
        content_version="01.000.000",
    )


def _full_options(folder_handling: str = FOLDER_FILE_ONLY) -> NamingOptions:
    return NamingOptions(
        include_title_id=True,
        include_title=True,
        include_version=True,
        folder_handling=folder_handling,
    )


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


def test_always_new_folder_destination(tmp_path: Path) -> None:
    source = tmp_path / "Returnal.ffpfsc"
    source.write_bytes(b"data")
    options = _full_options(FOLDER_ALWAYS_NEW)

    plan = build_rename_plan([(source, _metadata())], options, library_root=tmp_path)
    item = plan[0]
    expected_folder = tmp_path / "PPSA01285 - Returnal - v1.0"

    assert item.status is PlanStatus.READY
    assert item.source_directory is None
    assert item.target_directory == expected_folder
    assert item.destination == expected_folder / "PPSA01285 - Returnal - v1.0.ffpfsc"

    completed = apply_rename_plan(plan)
    assert completed == [(source.resolve(), item.destination)]
    assert item.destination.read_bytes() == b"data"
    assert not source.exists()


def test_existing_output_folder_is_collision(tmp_path: Path) -> None:
    source = tmp_path / "game.ffpfsc"
    source.write_bytes(b"data")
    (tmp_path / "PPSA01285").mkdir()

    plan = build_rename_plan(
        [(source, GameMetadata("PPSA01285"))],
        NamingOptions(folder_handling=FOLDER_ALWAYS_NEW),
        library_root=tmp_path,
    )
    assert plan[0].status is PlanStatus.COLLISION


def test_smart_loose_file_creates_folder_without_renaming_root(tmp_path: Path) -> None:
    source = tmp_path / "Returnal.ffpfsc"
    source.write_bytes(b"data")

    plan = build_rename_plan(
        [(source, _metadata())],
        _full_options(FOLDER_SMART),
        library_root=tmp_path,
    )
    item = plan[0]

    assert item.status is PlanStatus.READY
    assert item.source_directory is None
    assert item.target_directory == tmp_path / "PPSA01285 - Returnal - v1.0"
    assert item.target_directory != tmp_path


def test_smart_existing_dedicated_folder_renames_folder_and_file(tmp_path: Path) -> None:
    old_folder = tmp_path / "Returnal old"
    old_folder.mkdir()
    source = old_folder / "anything.ffpfsc"
    source.write_bytes(b"game")
    (old_folder / "notes.txt").write_text("keep me", encoding="utf-8")

    options = _full_options(FOLDER_SMART)
    plan = build_rename_plan([(source, _metadata())], options, library_root=tmp_path)
    item = plan[0]
    new_folder = tmp_path / "PPSA01285 - Returnal - v1.0"

    assert item.status is PlanStatus.READY
    assert item.source_directory == old_folder.resolve()
    assert item.target_directory == new_folder
    assert item.destination == new_folder / "PPSA01285 - Returnal - v1.0.ffpfsc"

    completed = apply_rename_plan(plan)
    assert completed == [(source.resolve(), item.destination)]
    assert not old_folder.exists()
    assert item.destination.read_bytes() == b"game"
    assert (new_folder / "notes.txt").read_text(encoding="utf-8") == "keep me"


def test_smart_folder_with_multiple_ffpfsc_is_blocked(tmp_path: Path) -> None:
    folder = tmp_path / "mixed"
    folder.mkdir()
    source = folder / "a.ffpfsc"
    source.write_bytes(b"a")
    (folder / "b.ffpfsc").write_bytes(b"b")

    plan = build_rename_plan(
        [(source, _metadata())],
        _full_options(FOLDER_SMART),
        library_root=tmp_path,
    )
    assert plan[0].status is PlanStatus.INVALID
    assert "exactly one .ffpfsc" in plan[0].reason


def test_smart_already_named_folder_only_renames_file(tmp_path: Path) -> None:
    folder = tmp_path / "PPSA01285 - Returnal - v1.0"
    folder.mkdir()
    source = folder / "old.ffpfsc"
    source.write_bytes(b"data")

    plan = build_rename_plan(
        [(source, _metadata())],
        _full_options(FOLDER_SMART),
        library_root=tmp_path,
    )
    item = plan[0]

    assert item.status is PlanStatus.READY
    assert item.source_directory is None
    assert item.target_directory is None
    assert item.destination == folder / "PPSA01285 - Returnal - v1.0.ffpfsc"


def test_smart_target_folder_collision_blocks(tmp_path: Path) -> None:
    old_folder = tmp_path / "Old"
    old_folder.mkdir()
    source = old_folder / "game.ffpfsc"
    source.write_bytes(b"data")
    (tmp_path / "PPSA01285 - Returnal - v1.0").mkdir()

    plan = build_rename_plan(
        [(source, _metadata())],
        _full_options(FOLDER_SMART),
        library_root=tmp_path,
    )
    assert plan[0].status is PlanStatus.COLLISION
    assert plan[0].reason == "target folder already exists"
