from __future__ import annotations

import pytest

from ps5_ffpfsc_renamer.ui.library_health_mixin import LibraryHealthMixin


class _Var:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def set(self, value: str) -> None:
        self.value = value


class _HealthHarness:
    FILTERS = LibraryHealthMixin.FILTERS
    search_var = _Var("returnal")
    filter_var = _Var("ALL")
    status_var = _Var()
    render_count = 0

    def _render_records(self) -> None:
        self.render_count += 1


def test_focus_health_filter_clears_search_and_renders() -> None:
    harness = _HealthHarness()
    harness.search_var = _Var("returnal")
    harness.filter_var = _Var("ALL")
    harness.status_var = _Var()
    harness.render_count = 0

    LibraryHealthMixin._focus_health_filter(harness, "PROBLEMS")

    assert harness.search_var.value == ""
    assert harness.filter_var.value == "PROBLEMS"
    assert harness.status_var.value == "Library view: PROBLEMS"
    assert harness.render_count == 1


def test_focus_health_filter_rejects_unknown_filter() -> None:
    harness = _HealthHarness()

    with pytest.raises(ValueError, match="Unsupported health filter"):
        LibraryHealthMixin._focus_health_filter(harness, "BROKEN")
