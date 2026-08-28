from __future__ import annotations

import inspect
from types import SimpleNamespace

from ps5_ffpfsc_renamer.ui.runtime_experience_mixin import RuntimeExperienceMixin
from ps5_ffpfsc_renamer.ui.shell_misc_mixin import ShellMiscMixin


class _FakeButton:
    def __init__(self, manager: str = "") -> None:
        self.manager = manager
        self.pack_options: dict[str, object] = {}
        self.states: list[tuple[str, ...]] = []

    def winfo_manager(self) -> str:
        return self.manager

    def pack(self, **kwargs) -> None:
        self.manager = "pack"
        self.pack_options = dict(kwargs)

    def pack_forget(self) -> None:
        self.manager = ""

    def state(self, states) -> None:
        self.states.append(tuple(states))


class _FakeResultLabel:
    def winfo_manager(self) -> str:
        return "pack"


class _History:
    def __init__(self, transaction) -> None:
        self.transaction = transaction

    def last_undoable(self):
        return self.transaction


def test_contextual_undo_stays_hidden_without_undoable_transaction() -> None:
    button = _FakeButton(manager="pack")
    app = SimpleNamespace(
        _undo_button=button,
        _results_count_label=None,
        history=_History(None),
        _scan_active=False,
    )

    ShellMiscMixin._refresh_undo_button(app)

    assert button.manager == ""


def test_contextual_undo_appears_next_to_apply_when_transaction_exists() -> None:
    button = _FakeButton()
    result_label = _FakeResultLabel()
    app = SimpleNamespace(
        _undo_button=button,
        _results_count_label=result_label,
        history=_History(object()),
        _scan_active=False,
    )

    ShellMiscMixin._refresh_undo_button(app)

    assert button.manager == "pack"
    assert button.pack_options["side"] == "right"
    assert button.pack_options["before"] is result_label
    assert button.states[-1] == ("!disabled",)


def test_contextual_undo_remains_visible_but_disabled_during_scan() -> None:
    button = _FakeButton()
    app = SimpleNamespace(
        _undo_button=button,
        _results_count_label=None,
        history=_History(object()),
        _scan_active=True,
    )

    ShellMiscMixin._refresh_undo_button(app)

    assert button.manager == "pack"
    assert button.states[-1] == ("disabled",)


def test_success_dialog_polish_reserves_close_button_space() -> None:
    calls: list[tuple[object, int, int]] = []

    class _Window:
        def winfo_exists(self) -> bool:
            return True

        def winfo_children(self):
            return []

    app = SimpleNamespace(
        _center_modal=lambda window, width, height: calls.append((window, width, height))
    )
    window = _Window()

    RuntimeExperienceMixin._polish_success_dialog(app, window)

    assert calls == [(window, 520, 330)]


def test_sidebar_creator_credit_is_right_aligned_and_unique_target() -> None:
    source = inspect.getsource(ShellMiscMixin._install_sidebar_creator_credit)
    assert 'text="Created by XaRaBaS"' in source
    assert 'anchor="e"' in source
    assert '"PROJECT BY" in texts' in source
