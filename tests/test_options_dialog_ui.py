from __future__ import annotations

import inspect

from ps5_ffpfsc_renamer.theme import apply_theme
from ps5_ffpfsc_renamer.ui.feedback_mixin import FeedbackMixin
from ps5_ffpfsc_renamer.ui.naming_profiles_mixin import NamingProfilesMixin
from ps5_ffpfsc_renamer.ui.options_dialog_mixin import OptionsDialogMixin
from ps5_ffpfsc_renamer.ui.settings_backup_mixin import SettingsBackupMixin


def test_options_uses_custom_sidebar_navigation_instead_of_native_tabs() -> None:
    source = inspect.getsource(OptionsDialogMixin._show_options)
    assert "ttk.Notebook(" not in source
    assert '"General", "Startup & display"' in source
    assert '"Scan & performance", "Workers & cache behavior"' in source
    assert '"Naming", "Filename & library layout"' in source
    assert '"Cache & engine", "Maintenance & MkPFS"' in source
    assert "_options_pages" in source
    assert 'text="Save changes"' in source


def test_options_naming_uses_outcome_based_organization_choices() -> None:
    source = inspect.getsource(OptionsDialogMixin._show_options)
    assert "FOLDER_ONE_PER_GAME" in source
    assert "FOLDER_ROOT_FLAT" in source
    assert "FOLDER_KEEP_STRUCTURE" in source
    assert "folder_mode_combo" not in source
    assert "Each .ffpfsc ends in its own named folder" in source
    assert "Every .ffpfsc ends directly in the library root" in source
    assert "Rename files where they are now" in source


def test_options_extensions_target_named_pages_not_notebook_tabs() -> None:
    naming_source = inspect.getsource(NamingProfilesMixin._show_options)
    backup_source = inspect.getsource(SettingsBackupMixin._show_options)
    assert "_options_pages" in naming_source
    assert 'pages.get("naming")' in naming_source
    assert "_find_notebook" not in naming_source
    assert "_options_pages" in backup_source
    assert 'pages.get("general")' in backup_source
    assert "Notebook(" not in backup_source


def test_theme_covers_standard_windows_form_controls() -> None:
    source = inspect.getsource(apply_theme)
    assert '"TEntry"' in source
    assert '"TCombobox"' in source
    assert '"TSpinbox"' in source
    assert '"*TCombobox*Listbox.background"' in source
    assert '"*TCombobox*Listbox.foreground"' in source
    assert '"*TCombobox*Listbox.selectBackground"' in source
    assert '"*TCombobox*Listbox.selectForeground"' in source
    assert '("readonly", COLORS["panel_alt"])' in source
    assert '("focus", COLORS["accent"])' in source


def test_feedback_category_uses_the_global_readonly_combobox_theme() -> None:
    source = inspect.getsource(FeedbackMixin._show_feedback_dialog)
    assert "category = ttk.Combobox(" in source
    assert 'state="readonly"' in source
