from __future__ import annotations

import inspect
import tkinter as tk

import pytest

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
    assert 'pages.pack(fill="x")' in source


def test_configuration_auto_collapses_after_inactivity_and_can_reopen() -> None:
    init_source = inspect.getsource(WorkspaceLayoutMixin.__init__)
    schedule = inspect.getsource(WorkspaceLayoutMixin._schedule_workspace_collapse)
    collapse = inspect.getsource(WorkspaceLayoutMixin._collapse_workspace_configuration)
    show = inspect.getsource(WorkspaceLayoutMixin._show_workspace_tab)

    assert "WORKSPACE_AUTO_COLLAPSE_MS = 8000" in inspect.getsource(WorkspaceLayoutMixin)
    assert "self._workspace_collapse_job" in init_source
    assert "self.after(" in schedule
    assert "self.WORKSPACE_AUTO_COLLAPSE_MS" in schedule
    assert "pages.pack_forget()" in collapse
    assert "Configuration collapsed" in collapse
    assert 'pages.pack(fill="x")' in show


def test_results_table_is_requested_taller_without_replacing_table_logic() -> None:
    source = inspect.getsource(WorkspaceLayoutMixin.__init__)
    assert "self.tree.configure(height=24)" in source
    assert desktop.RenamerApp._build_table.__qualname__.startswith("SortableResultsMixin.")


def test_scan_action_is_kept_outside_auto_collapsing_configuration() -> None:
    source = inspect.getsource(WorkspaceLayoutMixin._build_progress)
    assert "old_scan.destroy()" in source
    assert 'text="Scan now  F5"' in source
    assert "command=self._scan" in source
    assert 'self.scan_button.pack(side="right")' in source
    assert 'cancel.pack(side="right", padx=(0, 6))' in source
    assert desktop.RenamerApp._build_progress is WorkspaceLayoutMixin._build_progress


def test_effective_desktop_restores_styled_product_command_bar() -> None:
    source = inspect.getsource(WorkspaceLayoutMixin._install_modern_command_bar)
    assert "tk.Menubutton(" in source
    assert "popup = self._clone_command_menu(submenu, button)" in source
    assert "button.configure(menu=popup)" in source
    assert 'self.configure(menu="")' in source
    assert desktop.RenamerApp._install_modern_command_bar is WorkspaceLayoutMixin._install_modern_command_bar


def test_styled_command_bar_uses_button_owned_menu_clones() -> None:
    source = inspect.getsource(WorkspaceLayoutMixin._clone_command_menu)
    assert "clone = tk.Menu(parent, tearoff=False)" in source
    assert "menu.invoke(item)" in source
    assert "child_clone = self._clone_command_menu(child, clone)" in source
    assert "clone.add_cascade" in source
    assert "clone.add_command" in source


def test_button_owned_menu_clone_invokes_canonical_callbacks() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable: {exc}")
    root.withdraw()

    class Harness:
        _menu_entry_option = staticmethod(WorkspaceLayoutMixin._menu_entry_option)
        _clone_command_menu = WorkspaceLayoutMixin._clone_command_menu

        def nametowidget(self, name: str):
            return root.nametowidget(name)

        @staticmethod
        def _style_popup_menu(_menu: tk.Menu) -> None:
            return

    calls: list[str] = []
    menubar = tk.Menu(root, tearoff=False)
    source = tk.Menu(menubar, tearoff=False)
    source.add_command(label="Scan library", command=lambda: calls.append("scan"))
    export = tk.Menu(source, tearoff=False)
    export.add_command(label="CSV", command=lambda: calls.append("csv"))
    source.add_cascade(label="Export", menu=export)
    menubar.add_cascade(label="File", menu=source)

    button = tk.Menubutton(root, text="File", indicatoron=False)
    harness = Harness()
    popup = harness._clone_command_menu(source, button)
    button.configure(menu=popup)

    try:
        assert popup.master is button
        assert str(button.cget("menu")) == str(popup)
        popup.invoke(0)
        nested = root.nametowidget(popup.entrycget(1, "menu"))
        assert isinstance(nested, tk.Menu)
        nested.invoke(0)
        assert calls == ["scan", "csv"]
    finally:
        root.destroy()


def test_native_menu_remains_fallback_until_styled_buttons_exist() -> None:
    source = inspect.getsource(WorkspaceLayoutMixin._install_modern_command_bar)
    assert "if not bar.winfo_children()" in source
    assert 'self.configure(menu="")' in source
    assert "self.configure(menu=menubar)" in source


def test_creator_credit_is_footer_only_and_not_overlayed_on_results() -> None:
    footer = inspect.getsource(WorkspaceLayoutMixin._build_footer)
    suppress_overlay = inspect.getsource(WorkspaceLayoutMixin._install_creator_credit)
    assert 'text="PROJECT BY"' in footer
    assert 'text="XaRaBaS  ↗"' in footer
    assert 'separator.pack(fill="x")' in footer
    assert ".place(" not in footer
    assert ".place(" not in suppress_overlay


def test_product_menu_is_explicitly_built_when_missing() -> None:
    source = inspect.getsource(WorkspaceLayoutMixin.__init__)
    assert 'getattr(self, "_product_menu", None)' in source
    assert "self._build_product_menu()" in source
