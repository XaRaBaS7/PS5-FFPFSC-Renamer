from pathlib import Path

from ps5_ffpfsc_renamer.metadata import GameMetadata
from ps5_ffpfsc_renamer.naming import FOLDER_SMART, NamingOptions
from ps5_ffpfsc_renamer.rename_plan import PlanStatus, build_rename_plan


def test_smart_mode_uses_the_correct_root_for_each_file(tmp_path: Path) -> None:
    root_a = tmp_path / "DriveA"
    root_b = tmp_path / "DriveB"
    root_a.mkdir()
    root_b.mkdir()

    source_a = root_a / "returnal-old.ffpfsc"
    source_b = root_b / "astro-old.ffpfsc"
    source_a.write_bytes(b"a")
    source_b.write_bytes(b"b")

    items = [
        (
            source_a,
            GameMetadata(
                "PPSA01285",
                title_name="Returnal",
                content_version="01.000.000",
            ),
        ),
        (
            source_b,
            GameMetadata(
                "PPSA00001",
                title_name="Astro",
                content_version="02.500.000",
            ),
        ),
    ]
    options = NamingOptions(
        include_title_id=True,
        include_title=True,
        include_version=True,
        folder_handling=FOLDER_SMART,
        library_roots=(str(root_a), str(root_b)),
    )

    plan = build_rename_plan(items, options)

    assert [item.status for item in plan] == [PlanStatus.READY, PlanStatus.READY]
    assert plan[0].target_directory == root_a / "PPSA01285 - Returnal - v1.0"
    assert plan[1].target_directory == root_b / "PPSA00001 - Astro - v2.5"


def test_most_specific_selected_root_is_protected(tmp_path: Path) -> None:
    outer = tmp_path / "Library"
    inner = outer / "SecondRoot"
    inner.mkdir(parents=True)
    source = inner / "game.ffpfsc"
    source.write_bytes(b"data")

    options = NamingOptions(
        folder_handling=FOLDER_SMART,
        library_roots=(str(outer), str(inner)),
    )
    plan = build_rename_plan([(source, GameMetadata("PPSA01285"))], options)

    item = plan[0]
    assert item.status is PlanStatus.READY
    assert item.source_directory is None
    assert item.target_directory == inner / "PPSA01285"
    assert item.target_directory != inner


def test_source_outside_all_selected_roots_is_blocked(tmp_path: Path) -> None:
    root_a = tmp_path / "A"
    root_b = tmp_path / "B"
    outside = tmp_path / "Outside"
    root_a.mkdir()
    root_b.mkdir()
    outside.mkdir()
    source = outside / "game.ffpfsc"
    source.write_bytes(b"data")

    options = NamingOptions(
        folder_handling=FOLDER_SMART,
        library_roots=(str(root_a), str(root_b)),
    )
    plan = build_rename_plan([(source, GameMetadata("PPSA01285"))], options)

    assert plan[0].status is PlanStatus.INVALID
    assert "outside the selected library roots" in plan[0].reason
