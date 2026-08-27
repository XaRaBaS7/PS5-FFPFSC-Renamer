from __future__ import annotations

from types import SimpleNamespace

from ps5_ffpfsc_renamer.rename_plan import PlanStatus
from ps5_ffpfsc_renamer.ui.runtime_experience_mixin import RuntimeExperienceMixin


class _FakeButton:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}
        self.states: set[str] = set()

    def configure(self, **kwargs) -> None:
        self.options.update(kwargs)

    def state(self, states) -> None:
        for item in states:
            if item.startswith("!"):
                self.states.discard(item[1:])
            else:
                self.states.add(item)


def _runtime_with_plan(*statuses: PlanStatus):
    runtime = object.__new__(RuntimeExperienceMixin)
    runtime._rename_plan_button = _FakeButton()
    runtime.plan = [SimpleNamespace(status=status) for status in statuses]
    runtime._scan_active = False
    return runtime


def test_apply_changes_cta_reports_ready_count() -> None:
    runtime = _runtime_with_plan(PlanStatus.READY, PlanStatus.COLLISION, PlanStatus.READY)
    RuntimeExperienceMixin._refresh_rename_plan_button(runtime)

    assert runtime._rename_plan_button.options["text"] == "Apply changes (2)"
    assert "disabled" not in runtime._rename_plan_button.states


def test_apply_changes_cta_shows_scanning_state() -> None:
    runtime = _runtime_with_plan(PlanStatus.READY)
    runtime._scan_active = True
    RuntimeExperienceMixin._refresh_rename_plan_button(runtime)

    assert runtime._rename_plan_button.options["text"] == "Scanning..."
    assert "disabled" in runtime._rename_plan_button.states


def test_clock_duration_formats_minutes_and_hours() -> None:
    assert RuntimeExperienceMixin._clock_duration(0) == "00:00"
    assert RuntimeExperienceMixin._clock_duration(65) == "01:05"
    assert RuntimeExperienceMixin._clock_duration(3661) == "01:01:01"
