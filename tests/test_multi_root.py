from pathlib import Path
from types import SimpleNamespace

import ps5_ffpfsc_renamer.ui.multi_root_library_mixin as multi_root_module
from ps5_ffpfsc_renamer.metadata import GameMetadata
from ps5_ffpfsc_renamer.naming import FOLDER_SMART, NamingOptions
from ps5_ffpfsc_renamer.rename_plan import PlanStatus, build_rename_plan
from ps5_ffpfsc_renamer.root_health import RootStatus, root_key
from ps5_ffpfsc_renamer.ui.multi_root_library_mixin import MultiRootLibraryMixin


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


def _display_harness(roots: list[Path]) -> MultiRootLibraryMixin:
    harness = object.__new__(MultiRootLibraryMixin)
    harness.library_roots = roots
    return harness


def test_display_matching_prefers_deepest_root_without_resolve(monkeypatch, tmp_path: Path) -> None:
    outer = tmp_path / "Library"
    inner = outer / "Archive"
    source = inner / "Game" / "game.ffpfsc"
    harness = _display_harness([outer, inner])

    def fail_resolve(*_args, **_kwargs):
        raise AssertionError("display matching must not resolve filesystem paths")

    monkeypatch.setattr(Path, "resolve", fail_resolve)

    assert harness._matching_root(source) == inner
    assert harness._display_source(source) == str(Path("Archive") / "Game" / "game.ffpfsc")


def test_display_matching_does_not_confuse_similar_root_prefixes(tmp_path: Path) -> None:
    root = tmp_path / "PS5"
    source = tmp_path / "PS5-backup" / "game.ffpfsc"
    harness = _display_harness([root])

    assert harness._matching_root(source) is None
    assert harness._display_source(source) == "game.ffpfsc"


def test_single_root_display_returns_relative_path(tmp_path: Path) -> None:
    root = tmp_path / "Library"
    source = root / "Returnal" / "game.ffpfsc"
    harness = _display_harness([root])

    assert harness._display_source(source) == str(Path("Returnal") / "game.ffpfsc")


def test_root_normalization_does_not_resolve_filesystem(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "offline" / ".." / "Library"
    harness = _display_harness([root, root])

    def fail_resolve(*_args, **_kwargs):
        raise AssertionError("root summary normalization must not resolve filesystem paths")

    monkeypatch.setattr(Path, "resolve", fail_resolve)
    harness._normalize_roots()

    assert len(harness.library_roots) == 1
    assert harness.library_roots[0].name == "Library"


class _ProbeHarness(MultiRootLibraryMixin):
    def __init__(self, roots: list[Path]) -> None:
        self.library_roots = roots
        self._root_statuses = {}
        self.pending_callbacks = []
        self.summary_updates = 0

    def after(self, _delay: int, callback) -> None:
        self.pending_callbacks.append(callback)

    def _update_root_summary(self) -> None:
        self.summary_updates += 1


def _run_thread_inline(monkeypatch) -> None:
    monkeypatch.setattr(
        multi_root_module.threading,
        "Thread",
        lambda **kwargs: SimpleNamespace(start=kwargs["target"]),
    )


def test_async_probe_applies_status_when_root_selection_is_unchanged(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "Library"
    harness = _ProbeHarness([root])
    callbacks = []
    _run_thread_inline(monkeypatch)
    monkeypatch.setattr(
        multi_root_module,
        "probe_roots",
        lambda _roots: {root_key(root): RootStatus(root, "ONLINE", "available")},
    )

    harness._probe_library_roots_async(callback=lambda: callbacks.append("done"))
    assert len(harness.pending_callbacks) == 1
    harness.pending_callbacks.pop()()

    assert harness._root_statuses[root_key(root)].state == "ONLINE"
    assert harness.summary_updates == 1
    assert callbacks == ["done"]


def test_async_probe_discards_status_when_root_selection_changes(monkeypatch, tmp_path: Path) -> None:
    old_root = tmp_path / "Old"
    new_root = tmp_path / "New"
    harness = _ProbeHarness([old_root])
    callbacks = []
    _run_thread_inline(monkeypatch)
    monkeypatch.setattr(
        multi_root_module,
        "probe_roots",
        lambda _roots: {root_key(old_root): RootStatus(old_root, "ONLINE", "available")},
    )

    harness._probe_library_roots_async(callback=lambda: callbacks.append("done"))
    harness.library_roots = [new_root]
    harness.pending_callbacks.pop()()

    assert root_key(old_root) not in harness._root_statuses
    assert harness.summary_updates == 1
    assert callbacks == ["done"]
