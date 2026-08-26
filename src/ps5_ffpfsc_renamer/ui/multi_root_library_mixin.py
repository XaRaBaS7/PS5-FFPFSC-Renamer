from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Iterable

from ..naming import NamingOptions
from ..root_health import RootStatus, probe_roots, root_key


def _lexical_absolute(path: Path) -> str:
    """Normalize a display/matching path without touching the filesystem."""

    return os.path.normpath(os.path.abspath(os.path.expanduser(str(path))))


def _lexical_key(path: Path) -> str:
    return os.path.normcase(_lexical_absolute(path)).casefold()


def _is_lexically_under(path: Path, root: Path) -> bool:
    candidate = _lexical_key(path)
    parent = _lexical_key(root)
    try:
        return os.path.commonpath((candidate, parent)) == parent
    except ValueError:
        return False


def _relative_display_path(path: Path, root: Path) -> Path | None:
    if not _is_lexically_under(path, root):
        return None
    try:
        return Path(os.path.relpath(_lexical_absolute(path), _lexical_absolute(root)))
    except ValueError:
        return None


def _root_selection_token(roots: Iterable[Path]) -> tuple[str, ...]:
    """Return an order-independent identity for one configured root selection."""

    return tuple(sorted(root_key(Path(root)) for root in roots))


class MultiRootLibraryMixin:
    """Multi-folder library controls and root mapping extracted from gui_v7."""

    def __init__(self) -> None:
        self.library_roots: list[Path] = []
        self._root_statuses: dict[str, RootStatus] = {}
        super().__init__()

    def _build_library_controls(self, card: ttk.Frame) -> None:
        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="FFPFSC library", style="CardTitle.TLabel").pack(side="left")
        self.folder_count_var = tk.StringVar(value="No folders selected")
        ttk.Label(
            header,
            textvariable=self.folder_count_var,
            style="CardMuted.TLabel",
        ).pack(side="right")

        ttk.Label(
            card,
            text="Browse starts scanning automatically. Add more folders to analyze them as one library.",
            style="CardMuted.TLabel",
        ).pack(anchor="w", pady=(2, 7))

        path_row = ttk.Frame(card, style="Card.TFrame")
        path_row.pack(fill="x")
        self.folder_entry = tk.Entry(
            path_row,
            textvariable=self.folder_var,
            bg="#211a2f",
            fg="#f4f0ff",
            insertbackground="#f4f0ff",
            selectbackground="#8b5cf6",
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground="#3a304d",
            highlightcolor="#8b5cf6",
            relief="flat",
            font=("Segoe UI", 9),
        )
        self.folder_entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 7))

        self.browse_button = ttk.Button(
            path_row,
            text="Browse",
            style="Secondary.TButton",
            command=self._browse,
        )
        self.browse_button.pack(side="left")
        self.add_folder_button = ttk.Button(
            path_row,
            text="+ Add folder",
            style="Secondary.TButton",
            command=self._add_folder,
        )
        self.add_folder_button.pack(side="left", padx=(6, 0))

        options = ttk.Frame(card, style="Card.TFrame")
        options.pack(fill="x", pady=(8, 0))
        self.recursive_check = ttk.Checkbutton(
            options,
            text="Include subfolders",
            variable=self.recursive_var,
        )
        self.recursive_check.pack(side="left")
        ttk.Label(options, text="Workers", style="CardMuted.TLabel").pack(
            side="left", padx=(14, 5)
        )
        self.worker_combo = ttk.Combobox(
            options,
            textvariable=self.worker_var,
            values=("1 (HDD / safest)", "2", "4 (SSD / NVMe)", "Auto"),
            state="readonly",
            width=17,
            style="Performance.TCombobox",
        )
        self.worker_combo.pack(side="left")

        self.manage_folders_button = ttk.Button(
            options,
            text="Folders (0)...",
            style="Secondary.TButton",
            command=self._manage_folders,
        )
        self.manage_folders_button.pack(side="left", padx=(8, 0))

        self.scan_button = ttk.Button(
            options,
            text="Scan library",
            style="Primary.TButton",
            command=self._scan,
        )
        self.scan_button.pack(side="right")

    @staticmethod
    def _root_key(path: Path) -> str:
        return root_key(path)

    def _root_status(self, path: Path) -> RootStatus | None:
        return self._root_statuses.get(self._root_key(path))

    def _normalize_roots(self) -> None:
        unique: list[Path] = []
        seen: set[str] = set()
        for root in self.library_roots:
            normalized = Path(_lexical_absolute(root))
            key = _lexical_key(normalized)
            if key in seen:
                continue
            seen.add(key)
            unique.append(normalized)
        self.library_roots = unique

    def _update_root_summary(self) -> None:
        self._normalize_roots()
        count = len(self.library_roots)
        if count:
            self.folder_var.set(str(self.library_roots[0]))
            known = [self._root_status(root) for root in self.library_roots]
            online = sum(1 for status in known if status is not None and status.state == "ONLINE")
            unavailable = sum(
                1 for status in known if status is not None and status.state in {"OFFLINE", "ERROR"}
            )
            unknown = count - online - unavailable
            summary = f"{count} folder{'s' if count != 1 else ''} selected"
            if online or unavailable:
                summary += f" • {online} online"
                if unavailable:
                    summary += f" • {unavailable} unavailable"
                if unknown:
                    summary += f" • {unknown} unchecked"
            self.folder_count_var.set(summary)
        else:
            self.folder_var.set("")
            self.folder_count_var.set("No folders selected")
        self.manage_folders_button.configure(text=f"Folders ({count})...")

    def _probe_library_roots_async(self, *, callback=None) -> None:
        roots = list(self.library_roots)
        if not roots:
            if callback is not None:
                callback()
            return
        selection_token = _root_selection_token(roots)

        def worker() -> None:
            statuses = probe_roots(roots)

            def done() -> None:
                # The user may change roots while a slow USB/NAS probe is in
                # flight. Never apply stale availability to a new selection.
                if _root_selection_token(self.library_roots) != selection_token:
                    self._update_root_summary()
                    if callback is not None:
                        callback()
                    return
                self._root_statuses.update(statuses)
                self._update_root_summary()
                if callback is not None:
                    callback()

            try:
                self.after(0, done)
            except tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True, name="ffpfsc-root-probe").start()

    def _manage_folders(self) -> None:
        window = tk.Toplevel(self)
        window.title("Scan folders")
        window.transient(self)
        window.grab_set()
        window.geometry("780x390")
        window.minsize(600, 320)

        container = ttk.Frame(window, padding=14)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text="Folders included in scan", style="CardTitle.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            container,
            text=(
                "Offline USB/NAS roots are kept in settings and skipped safely. "
                "Nested roots are scanned only once when subfolders are enabled."
            ),
            style="CardMuted.TLabel",
        ).pack(anchor="w", pady=(2, 5))

        availability_var = tk.StringVar(value="Availability from last check / scan")
        ttk.Label(
            container,
            textvariable=availability_var,
            style="CardInfo.TLabel",
        ).pack(anchor="w", pady=(0, 7))

        listbox = tk.Listbox(
            container,
            bg="#181321",
            fg="#f4f0ff",
            selectbackground="#6d4bc3",
            selectforeground="#ffffff",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#3a304d",
            font=("Consolas", 9),
        )
        listbox.pack(fill="both", expand=True)

        def refresh() -> None:
            if not window.winfo_exists():
                return
            listbox.delete(0, "end")
            online = offline = unknown = 0
            for root in self.library_roots:
                status = self._root_status(root)
                state = status.state if status is not None else "UNKNOWN"
                if state == "ONLINE":
                    online += 1
                elif state in {"OFFLINE", "ERROR"}:
                    offline += 1
                else:
                    unknown += 1
                listbox.insert("end", f"[{state:<7}]  {root}")
            parts = [f"{online} online", f"{offline} unavailable"]
            if unknown:
                parts.append(f"{unknown} unchecked")
            availability_var.set(" • ".join(parts) if self.library_roots else "No folders selected")
            self._update_root_summary()

        def add_here() -> None:
            selected = filedialog.askdirectory(title="Add folder", parent=window)
            if not selected:
                return
            candidate = Path(selected).resolve(strict=False)
            if self._root_key(candidate) not in {
                self._root_key(root) for root in self.library_roots
            }:
                self.library_roots.append(candidate)
            refresh()

        def remove_selected() -> None:
            indexes = list(listbox.curselection())
            if not indexes:
                return
            for index in reversed(indexes):
                if 0 <= index < len(self.library_roots):
                    del self.library_roots[index]
            refresh()

        buttons = ttk.Frame(container)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="+ Add", command=add_here).pack(side="left")
        ttk.Button(buttons, text="Remove", command=remove_selected).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(
            buttons,
            text="Clear all",
            command=lambda: (self.library_roots.clear(), refresh()),
        ).pack(side="left", padx=(6, 0))

        check_button = ttk.Button(buttons, text="Check availability")
        check_button.pack(side="left", padx=(12, 0))

        def check_now() -> None:
            check_button.configure(state="disabled", text="Checking...")
            availability_var.set("Checking roots in background...")

            def checked() -> None:
                if not window.winfo_exists():
                    return
                check_button.configure(state="normal", text="Check availability")
                refresh()

            self._probe_library_roots_async(callback=checked)

        check_button.configure(command=check_now)
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")

        def apply_and_scan() -> None:
            refresh()
            window.destroy()
            if self.library_roots:
                self.after(30, self._scan)

        ttk.Button(
            buttons,
            text="Scan selected folders",
            style="Primary.TButton",
            command=apply_and_scan,
        ).pack(side="right", padx=(0, 6))
        refresh()
        self._probe_library_roots_async(callback=refresh)

    def _set_scan_controls(self, active: bool) -> None:
        super()._set_scan_controls(active)
        state = "disabled" if active else "normal"
        self.add_folder_button.configure(state=state)
        self.manage_folders_button.configure(state=state)

    def _scan(self) -> None:
        if not self.library_roots:
            folder_text = self.folder_var.get().strip()
            if folder_text:
                candidate = Path(folder_text).expanduser()
                if candidate.is_dir():
                    self.library_roots = [candidate.resolve(strict=False)]
                    self._update_root_summary()
        super()._scan()

    def _matching_root(self, path: Path) -> Path | None:
        matches = [
            root
            for root in self.library_roots
            if _is_lexically_under(path, root)
        ]
        if not matches:
            return None
        return max(matches, key=lambda root: len(Path(_lexical_absolute(root)).parts))

    def _display_source(self, source: Path) -> str:
        root = self._matching_root(source)
        if root is None:
            return source.name
        relative = _relative_display_path(source, root)
        if relative is None:
            return source.name
        if len(self.library_roots) <= 1:
            return str(relative)
        return str(Path(root.name) / relative)

    def _current_naming_options(self) -> NamingOptions:
        options = super()._current_naming_options()
        return replace(
            options,
            library_root=str(self.library_roots[0]) if len(self.library_roots) == 1 else None,
            library_roots=tuple(str(root) for root in self.library_roots),
        )
