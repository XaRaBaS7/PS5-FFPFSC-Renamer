from pathlib import Path

from ps5_ffpfsc_renamer.metadata import GameMetadata
from ps5_ffpfsc_renamer.naming import (
    FOLDER_KEEP_STRUCTURE,
    FOLDER_ONE_PER_GAME,
    FOLDER_ROOT_FLAT,
    NamingOptions,
)
from ps5_ffpfsc_renamer.rename_plan import PlanStatus, build_rename_plan
from ps5_ffpfsc_renamer.renamer import apply_rename_plan


def _metadata(
    title_id: str = "PPSA01285",
    title: str = "Returnal",
    version: str = "01.000.000",
) -> GameMetadata:
    return GameMetadata(
        title_id,
        title_name=title,
        content_version=version,
    )


def _full_options(folder_handling: str = FOLDER_KEEP_STRUCTURE) -> NamingOptions:
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


def test_keep_structure_renames_file_without_moving_it(tmp_path: Path) -> None:
    folder = tmp_path / "Existing folder"
    folder.mkdir()
    source = folder / "wrong.ffpfsc"
    source.write_bytes(b"data")

    plan = build_rename_plan(
        [(source, _metadata())],
        _full_options(FOLDER_KEEP_STRUCTURE),
        library_root=tmp_path,
    )
    item = plan[0]

    assert item.status is PlanStatus.READY
    assert item.target_directory is None
    assert item.source_directory is None
    assert item.destination.parent == folder.resolve()
    assert item.destination.name == "PPSA01285 - Returnal - v1.0.ffpfsc"

    apply_rename_plan(plan)
    assert item.destination.read_bytes() == b"data"
    assert folder.exists()


def test_flat_root_moves_nested_file_directly_to_library_root(tmp_path: Path) -> None:
    nested = tmp_path / "Old folder" / "Nested"
    nested.mkdir(parents=True)
    source = nested / "wrong.ffpfsc"
    source.write_bytes(b"game")

    plan = build_rename_plan(
        [(source, _metadata())],
        _full_options(FOLDER_ROOT_FLAT),
        library_root=tmp_path,
    )
    item = plan[0]

    assert item.status is PlanStatus.READY
    assert item.target_directory is None
    assert item.source_directory is None
    assert item.destination == tmp_path.resolve() / "PPSA01285 - Returnal - v1.0.ffpfsc"

    completed = apply_rename_plan(plan)
    assert completed == [(source.resolve(), item.destination)]
    assert item.destination.read_bytes() == b"game"
    assert nested.exists(), "source folders are intentionally retained for safety"


def test_flat_root_existing_destination_is_collision(tmp_path: Path) -> None:
    folder = tmp_path / "Old"
    folder.mkdir()
    source = folder / "wrong.ffpfsc"
    source.write_bytes(b"source")
    target = tmp_path / "PPSA01285 - Returnal - v1.0.ffpfsc"
    target.write_bytes(b"existing")

    plan = build_rename_plan(
        [(source, _metadata())],
        _full_options(FOLDER_ROOT_FLAT),
        library_root=tmp_path,
    )
    assert plan[0].status is PlanStatus.COLLISION
    assert plan[0].reason == "target file already exists"


def test_one_folder_per_game_loose_file_creates_top_level_folder(tmp_path: Path) -> None:
    source = tmp_path / "Returnal.ffpfsc"
    source.write_bytes(b"data")
    options = _full_options(FOLDER_ONE_PER_GAME)

    plan = build_rename_plan([(source, _metadata())], options, library_root=tmp_path)
    item = plan[0]
    expected_folder = tmp_path.resolve() / "PPSA01285 - Returnal - v1.0"

    assert item.status is PlanStatus.READY
    assert item.source_directory is None
    assert item.target_directory == expected_folder
    assert item.destination == expected_folder / "PPSA01285 - Returnal - v1.0.ffpfsc"

    completed = apply_rename_plan(plan)
    assert completed == [(source.resolve(), item.destination)]
    assert item.destination.read_bytes() == b"data"
    assert not source.exists()


def test_one_folder_per_game_renames_existing_dedicated_folder_and_file(tmp_path: Path) -> None:
    old_folder = tmp_path / "Returnal old"
    old_folder.mkdir()
    source = old_folder / "anything.ffpfsc"
    source.write_bytes(b"game")
    (old_folder / "notes.txt").write_text("keep me", encoding="utf-8")

    options = _full_options(FOLDER_ONE_PER_GAME)
    plan = build_rename_plan([(source, _metadata())], options, library_root=tmp_path)
    item = plan[0]
    new_folder = tmp_path.resolve() / "PPSA01285 - Returnal - v1.0"

    assert item.status is PlanStatus.READY
    assert item.source_directory == old_folder.resolve()
    assert item.target_directory == new_folder
    assert item.destination == new_folder / "PPSA01285 - Returnal - v1.0.ffpfsc"

    completed = apply_rename_plan(plan)
    assert completed == [(source.resolve(), item.destination)]
    assert not old_folder.exists()
    assert item.destination.read_bytes() == b"game"
    assert (new_folder / "notes.txt").read_text(encoding="utf-8") == "keep me"


def test_one_folder_per_game_shared_folder_splits_games_into_root_folders(tmp_path: Path) -> None:
    shared = tmp_path / "Mixed"
    shared.mkdir()
    first = shared / "a.ffpfsc"
    second = shared / "b.ffpfsc"
    first.write_bytes(b"a")
    second.write_bytes(b"b")

    items = [
        (first, _metadata("PPSA01285", "Returnal")),
        (second, _metadata("PPSA05366", "A Plague Tale Requiem", "01.005.000")),
    ]
    plan = build_rename_plan(
        items,
        _full_options(FOLDER_ONE_PER_GAME),
        library_root=tmp_path,
    )

    assert all(item.status is PlanStatus.READY for item in plan)
    assert all(item.source_directory is None for item in plan)
    assert plan[0].target_directory == tmp_path.resolve() / "PPSA01285 - Returnal - v1.0"
    assert plan[1].target_directory == (
        tmp_path.resolve() / "PPSA05366 - A Plague Tale Requiem - v1.005"
    )

    apply_rename_plan(plan)
    assert plan[0].destination.read_bytes() == b"a"
    assert plan[1].destination.read_bytes() == b"b"
    assert shared.exists()


def test_one_folder_per_game_nested_source_moves_to_top_level_game_folder(tmp_path: Path) -> None:
    nested = tmp_path / "Archive" / "Old" / "Returnal"
    nested.mkdir(parents=True)
    source = nested / "game.ffpfsc"
    source.write_bytes(b"data")

    plan = build_rename_plan(
        [(source, _metadata())],
        _full_options(FOLDER_ONE_PER_GAME),
        library_root=tmp_path,
    )
    item = plan[0]

    assert item.status is PlanStatus.READY
    assert item.source_directory is None
    assert item.target_directory == tmp_path.resolve() / "PPSA01285 - Returnal - v1.0"


def test_one_folder_per_game_already_named_folder_only_renames_file(tmp_path: Path) -> None:
    folder = tmp_path / "PPSA01285 - Returnal - v1.0"
    folder.mkdir()
    source = folder / "old.ffpfsc"
    source.write_bytes(b"data")

    plan = build_rename_plan(
        [(source, _metadata())],
        _full_options(FOLDER_ONE_PER_GAME),
        library_root=tmp_path,
    )
    item = plan[0]

    assert item.status is PlanStatus.READY
    assert item.source_directory is None
    assert item.target_directory is None
    assert item.destination == folder.resolve() / "PPSA01285 - Returnal - v1.0.ffpfsc"


def test_one_folder_per_game_target_folder_collision_blocks(tmp_path: Path) -> None:
    old_folder = tmp_path / "Old"
    old_folder.mkdir()
    source = old_folder / "game.ffpfsc"
    source.write_bytes(b"data")
    (tmp_path / "PPSA01285 - Returnal - v1.0").mkdir()

    plan = build_rename_plan(
        [(source, _metadata())],
        _full_options(FOLDER_ONE_PER_GAME),
        library_root=tmp_path,
    )
    assert plan[0].status is PlanStatus.COLLISION
    assert plan[0].reason == "target folder already exists"
