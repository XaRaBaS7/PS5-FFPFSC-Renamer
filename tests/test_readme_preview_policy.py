from tools.check_readme_preview import is_visible_ui_path


def test_preview_policy_covers_current_ui_mixins() -> None:
    assert is_visible_ui_path("src/ps5_ffpfsc_renamer/ui/workspace_layout_mixin.py")
    assert is_visible_ui_path("src/ps5_ffpfsc_renamer/ui/filename_builder_mixin.py")
    assert is_visible_ui_path("src/ps5_ffpfsc_renamer/ui/options_dialog_mixin.py")


def test_preview_policy_covers_shell_theme_and_branding() -> None:
    assert is_visible_ui_path("src/ps5_ffpfsc_renamer/desktop_core.py")
    assert is_visible_ui_path("src/ps5_ffpfsc_renamer/theme.py")
    assert is_visible_ui_path("src/ps5_ffpfsc_renamer/ui_icons.py")
    assert is_visible_ui_path("assets/brand/app-symbol.png")


def test_preview_policy_ignores_backend_only_changes() -> None:
    assert not is_visible_ui_path("src/ps5_ffpfsc_renamer/rename_plan.py")
    assert not is_visible_ui_path("tests/test_rename_plan.py")
