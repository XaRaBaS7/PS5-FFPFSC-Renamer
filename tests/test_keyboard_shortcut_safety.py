from __future__ import annotations

import pytest

from ps5_ffpfsc_renamer.ui.keyboard_shortcuts_mixin import KeyboardShortcutsMixin


class _Widget:
    def __init__(self, widget_class: str) -> None:
        self.widget_class = widget_class

    def winfo_class(self) -> str:
        return self.widget_class


class _Event:
    def __init__(self, widget_class: str) -> None:
        self.widget = _Widget(widget_class)


class _Harness(KeyboardShortcutsMixin):
    def __init__(self) -> None:
        self._scan_active = False
        self.undo_calls = 0
        self.select_all_calls = 0

    def _undo_last_rename(self) -> None:
        self.undo_calls += 1

    def _select_all_rows(self) -> None:
        self.select_all_calls += 1


@pytest.mark.parametrize(
    "widget_class",
    ["Entry", "TEntry", "Text", "Spinbox", "TSpinbox", "TCombobox"],
)
def test_ctrl_z_never_triggers_filesystem_undo_in_text_editing_widget(
    widget_class: str,
) -> None:
    harness = _Harness()

    result = harness._shortcut_undo(_Event(widget_class))

    assert result is None
    assert harness.undo_calls == 0


@pytest.mark.parametrize(
    "widget_class",
    ["Entry", "TEntry", "Text", "Spinbox", "TSpinbox", "TCombobox"],
)
def test_ctrl_a_preserves_text_editing_context(widget_class: str) -> None:
    harness = _Harness()

    result = harness._shortcut_select_all(_Event(widget_class))

    assert result is None
    assert harness.select_all_calls == 0


def test_library_shortcuts_still_run_outside_text_editing_widgets() -> None:
    harness = _Harness()

    assert harness._shortcut_undo(_Event("Treeview")) == "break"
    assert harness._shortcut_select_all(_Event("Treeview")) == "break"
    assert harness.undo_calls == 1
    assert harness.select_all_calls == 1
