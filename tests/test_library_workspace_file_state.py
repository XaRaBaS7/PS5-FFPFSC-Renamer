from pathlib import Path

from ps5_ffpfsc_renamer.cache_batch import FileState
from ps5_ffpfsc_renamer.ui.library_workspace_mixin import LibraryWorkspaceMixin


class _WorkspaceHarness:
    _known_file_size = LibraryWorkspaceMixin._known_file_size


def test_workspace_reuses_scan_file_state_for_size(tmp_path: Path) -> None:
    image = tmp_path / "game.ffpfsc"
    harness = _WorkspaceHarness()
    harness._last_scan_file_states = {image: FileState(size=123456789, mtime_ns=1)}

    assert harness._known_file_size(image) == 123456789


def test_workspace_falls_back_to_filesystem_when_state_is_missing(tmp_path: Path) -> None:
    image = tmp_path / "game.ffpfsc"
    image.write_bytes(b"12345")
    harness = _WorkspaceHarness()
    harness._last_scan_file_states = {}

    assert harness._known_file_size(image) == 5
