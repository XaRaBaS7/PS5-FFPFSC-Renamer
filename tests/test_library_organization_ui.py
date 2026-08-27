from __future__ import annotations

import inspect

from ps5_ffpfsc_renamer.ui.filename_builder_mixin import FilenameBuilderMixin
from ps5_ffpfsc_renamer.ui.rename_safety_mixin import RenameSafetyMixin


def test_filename_builder_exposes_outcome_based_organization_choices() -> None:
    source = inspect.getsource(FilenameBuilderMixin._build_output_controls)
    assert "Library organization" in source
    assert "One folder per game" not in source  # labels come from class constants
    assert "folder_mode_combo" not in source
    assert "_create_organization_card" in source
    assert FilenameBuilderMixin.FOLDER_ONE_PER_GAME_LABEL == "One folder per game"
    assert FilenameBuilderMixin.FOLDER_ROOT_FLAT_LABEL == "All files in library root"
    assert FilenameBuilderMixin.FOLDER_KEEP_STRUCTURE_LABEL == "Keep current structure"


def test_folder_help_explains_the_result_not_internal_smart_logic() -> None:
    source = inspect.getsource(FilenameBuilderMixin._update_folder_help)
    assert "directly under its library root" in source
    assert "moved directly into its selected library root" in source
    assert "stays in its current folder" in source
    assert "multiple FFPFSC" not in source


def test_rename_confirmation_uses_custom_dark_review_dialog() -> None:
    rename_source = inspect.getsource(RenameSafetyMixin._rename)
    dialog_source = inspect.getsource(RenameSafetyMixin._confirm_rename_dialog)
    assert "_confirm_rename_dialog" in rename_source
    assert "askyesno" not in rename_source
    assert "Review changes" in dialog_source
    assert "FFPFSC contents are never rewritten or recompressed" in dialog_source
    assert "Apply {report.ready_count} changes" in dialog_source


def test_footer_credit_is_inset_and_presented_as_project_credit() -> None:
    source = inspect.getsource(FilenameBuilderMixin._build_footer)
    assert 'text="PROJECT BY"' in source
    assert 'text="XaRaBaS  ↗"' in source
    assert 'padx=(12, 12)' in source
