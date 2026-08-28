from __future__ import annotations

import inspect

from ps5_ffpfsc_renamer import desktop
from ps5_ffpfsc_renamer.ui.workspace_layout_mixin import WorkspaceLayoutMixin


def test_configuration_uses_two_compact_outcome_tabs() -> None:
    source = inspect.getsource(WorkspaceLayoutMixin._build_configuration)
    assert '"Library setup", "Folders, scan and performance"' in source
    assert '"Rename builder", "Filename and library organization"' in source
    assert 'self._show_workspace_tab("library")' in source
    assert 'self._build_library_controls(library)' in source
    assert 'self._build_output_controls(rename)' in source


def test_workspace_tabs_show_only_one_panel_at_a_time() -> None:
    source = inspect.getsource(WorkspaceLayoutMixin._show_workspace_tab)
    assert 'page.pack(fill="x")' in source
    assert "page.pack_forget()" in source


def test_results_table_is_requested_taller_without_replacing_table_logic() -> None:
    source = inspect.getsource(WorkspaceLayoutMixin.__init__)
    assert "self.tree.configure(height=18)" in source
    assert desktop.RenamerApp._build_table.__qualname__.startswith("SortableResultsMixin.")


def test_effective_desktop_keeps_native_product_menu_attached() -> None:
    source = inspect.getsource(WorkspaceLayoutMixin._install_modern_command_bar)
    assert "self.configure(menu=menubar)" in source
    assert 'self.configure(menu="")' not in source
    assert desktop.RenamerApp._install_modern_command_bar is WorkspaceLayoutMixin._install_modern_command_bar


def test_creator_credit_is_footer_only_and_not_overlayed_on_results() -> None:
    footer = inspect.getsource(WorkspaceLayoutMixin._build_footer)
    suppress_overlay = inspect.getsource(WorkspaceLayoutMixin._install_creator_credit)
    assert 'text="PROJECT BY"' in footer
    assert 'text="XaRaBaS  ↗"' in footer
    assert "separator.pack(fill=\"x\")" in footer
    assert ".place(" not in footer
    assert ".place(" not in suppress_overlay


def test_product_menu_is_explicitly_built_when_missing() -> None:
    source = inspect.getsource(WorkspaceLayoutMixin.__init__)
    assert 'getattr(self, "_product_menu", None)' in source
    assert "self._build_product_menu()" in source
