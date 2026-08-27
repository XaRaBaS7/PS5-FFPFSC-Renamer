from __future__ import annotations

from types import SimpleNamespace

from ps5_ffpfsc_renamer.rename_plan import PlanStatus
from ps5_ffpfsc_renamer.ui.shell_misc_mixin import ShellMiscMixin


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


def _shell_with_plan(*statuses: PlanStatus):
    shell = object.__new__(ShellMiscMixin)
    shell._rename_plan_button = _FakeButton()
    shell.plan = [SimpleNamespace(status=status) for status in statuses]
    shell._scan_active = False
    return shell


def test_rename_cta_reports_ready_count_and_remains_available_after_scan() -> None:
    shell = _shell_with_plan(PlanStatus.READY, PlanStatus.COLLISION, PlanStatus.READY)
    ShellMiscMixin._refresh_rename_plan_button(shell)

    assert shell._rename_plan_button.options["text"] == "Apply rename plan (2)"
    assert "disabled" not in shell._rename_plan_button.states


def test_rename_cta_is_disabled_while_scanning() -> None:
    shell = _shell_with_plan(PlanStatus.READY)
    shell._scan_active = True
    ShellMiscMixin._refresh_rename_plan_button(shell)

    assert shell._rename_plan_button.options["text"] == "Apply rename plan (1)"
    assert "disabled" in shell._rename_plan_button.states


def test_modern_shell_routes_rename_through_existing_safe_entrypoint() -> None:
    import inspect

    source = inspect.getsource(ShellMiscMixin._install_rename_plan_button)
    assert "command=self._rename" in source
    assert "apply_rename_plan" not in source


def test_modern_shell_keeps_options_in_sidebar_and_detaches_native_menubar() -> None:
    import inspect

    sidebar_source = inspect.getsource(ShellMiscMixin._install_sidebar_options_button)
    menu_source = inspect.getsource(ShellMiscMixin._install_modern_command_bar)
    assert 'text="Options"' in sidebar_source
    assert 'self.configure(menu="")' in menu_source


def test_modern_shell_failure_is_logged_and_does_not_abort_remaining_steps() -> None:
    shell = object.__new__(ShellMiscMixin)
    calls: list[str] = []
    warnings: list[str] = []

    def fail_sidebar() -> None:
        calls.append("sidebar")
        raise RuntimeError("synthetic layout failure")

    shell._install_sidebar_options_button = fail_sidebar
    shell._remove_legacy_central_options_button = lambda: calls.append("cleanup")
    shell._install_rename_plan_button = lambda: calls.append("rename")
    shell._install_modern_command_bar = lambda: calls.append("menu")
    shell._refresh_rename_plan_button = lambda: calls.append("refresh")
    shell._log = lambda _level, message: warnings.append(message)

    ShellMiscMixin._install_modern_shell(shell)

    assert calls == ["sidebar", "cleanup", "rename", "menu", "refresh"]
    assert len(warnings) == 1
    assert "Modern UI fallback (sidebar options)" in warnings[0]
    assert "synthetic layout failure" in warnings[0]
