from pathlib import Path
from types import SimpleNamespace

from ps5_ffpfsc_renamer.details_prefetch import prefetch_game_details


def test_prefetch_deduplicates_paths_and_counts_cache_hits(tmp_path: Path) -> None:
    first = tmp_path / "a.ffpfsc"
    second = tmp_path / "b.ffpfsc"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    calls: list[Path] = []

    def loader(path, **_kwargs):
        calls.append(path)
        return SimpleNamespace(cache_hit=path.name == "a.ffpfsc")

    result = prefetch_game_details(
        [first, first, second],
        workers=1,
        loader=loader,
    )

    assert result.total == 2
    assert result.cached == 1
    assert result.loaded == 1
    assert result.failed == 0
    assert len(calls) == 2


def test_prefetch_collects_errors_without_aborting_other_items(tmp_path: Path) -> None:
    good = tmp_path / "good.ffpfsc"
    bad = tmp_path / "bad.ffpfsc"
    good.write_bytes(b"good")
    bad.write_bytes(b"bad")

    def loader(path, **_kwargs):
        if path.name == "bad.ffpfsc":
            raise RuntimeError("test failure")
        return SimpleNamespace(cache_hit=False)

    result = prefetch_game_details(
        [bad, good],
        workers=2,
        loader=loader,
    )

    assert result.total == 2
    assert result.loaded == 1
    assert result.failed == 1
    assert result.cancelled is False
    assert result.errors and result.errors[0][0].endswith("bad.ffpfsc")


def test_prefetch_reports_progress(tmp_path: Path) -> None:
    files = [tmp_path / f"{index}.ffpfsc" for index in range(3)]
    for path in files:
        path.write_bytes(b"x")
    progress = []

    def loader(_path, **_kwargs):
        return SimpleNamespace(cache_hit=True)

    result = prefetch_game_details(
        files,
        workers=8,
        loader=loader,
        progress=lambda done, total, path, state: progress.append(
            (done, total, path.name, state)
        ),
    )

    assert result.cached == 3
    assert result.loaded == 0
    assert len(progress) == 3
    assert progress[-1][0:2] == (3, 3)
