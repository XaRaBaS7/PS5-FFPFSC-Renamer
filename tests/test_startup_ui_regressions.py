from __future__ import annotations

import inspect

from ps5_ffpfsc_renamer.ui.startup_preferences_mixin import StartupPreferencesMixin


def test_startup_preferences_does_not_override_branded_window_icon() -> None:
    source = inspect.getsource(StartupPreferencesMixin.__init__)
    assert "apply_window_icon" not in source


def test_scan_controls_prefers_sidebar_options_and_ignores_stale_tk_widget() -> None:
    source = inspect.getsource(StartupPreferencesMixin._set_scan_controls)
    assert '_sidebar_options_button' in source
    assert 'getattr(self, "options_button", None)' in source
    assert 'except tk.TclError' in source
