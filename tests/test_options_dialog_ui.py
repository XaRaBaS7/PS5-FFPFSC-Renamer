from __future__ import annotations

import inspect

from ps5_ffpfsc_renamer.ui.naming_profiles_mixin import NamingProfilesMixin
from ps5_ffpfsc_renamer.ui.options_dialog_mixin import OptionsDialogMixin
from ps5_ffpfsc_renamer.ui.settings_backup_mixin import SettingsBackupMixin


def test_options_uses_custom_sidebar_navigation_instead_of_native_tabs() -> None:
    source = inspect.getsource(OptionsDialogMixin._show_options)
    assert "ttk.Notebook" not in source
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
    assert "Notebook" not in backup_source
