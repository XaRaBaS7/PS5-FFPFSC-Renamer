from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .ffpfsc_reader import MetadataReadError, read_metadata
from .rename_plan import PlanStatus, RenamePlanItem, build_rename_plan
from .renamer import apply_rename_plan
from .scanner import scan_ffpfsc
from .theme import COLORS, apply_theme


class RenamerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PS5 FFPFSC Renamer")
        self.geometry("1220x760")
        self.minsize(980, 620)
        apply_theme(self)

        self.folder_var = tk.StringVar()
        self.recursive_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Ready")
        self.plan: list[RenamePlanItem] = []
        self._build_ui()

    def _build_ui(self) -> None:
        shell = ttk.Frame(self, padding=24)
        shell.pack(fill="both", expand=True)

        ttk.Label(shell, text="PS5 FFPFSC Renamer", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            shell,
            text="Inspect metadata, preview safe filenames, then rename only when you approve the plan.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 18))

        controls = ttk.Frame(shell, style="Card.TFrame", padding=18)
        controls.pack(fill="x")
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="FFPFSC library", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))
        entry = tk.Entry(
            controls,
            textvariable=self.folder_var,
            bg=COLORS["panel_alt"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            font=("Segoe UI", 10),
        )
        entry.grid(row=1, column=0, columnspan=2, sticky="ew", ipady=8, padx=(0, 10))
        ttk.Button(controls, text="Browse", style="Secondary.TButton", command=self._browse).grid(row=1, column=2, padx=(0, 8))
        self.scan_button = ttk.Button(controls, text="Scan library", style="Primary.TButton", command=self._scan)
        self.scan_button.grid(row=1, column=3)
        ttk.Checkbutton(controls, text="Include subfolders", variable=self.recursive_var).grid(row=2, column=0, sticky="w", pady=(12, 0))

        table_card = ttk.Frame(shell, style="Card.TFrame", padding=1)
        table_card.pack(fill="both", expand=True, pady=18)
        columns = ("file", "title_id", "title", "version", "new_name", "status")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", style="Library.Treeview")
        headings = {
            "file": "Current file",
            "title_id": "Title ID",
            "title": "Title",
            "version": "Version",
            "new_name": "Proposed name",
            "status": "Status",
        }
        widths = {"file": 250, "title_id": 100, "title": 260, "version": 100, "new_name": 180, "status": 100}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        footer = ttk.Frame(shell)
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_var, style="Subtitle.TLabel").pack(side="left")
        self.rename_button = ttk.Button(footer, text="Rename ready files", style="Primary.TButton", command=self._rename, state="disabled")
        self.rename_button.pack(side="right")

    def _browse(self) -> None:
        selected = filedialog.askdirectory(title="Select FFPFSC folder")
        if selected:
            self.folder_var.set(selected)

    def _scan(self) -> None:
        if not self.folder_var.get().strip():
            messagebox.showwarning("PS5 FFPFSC Renamer", "Select a folder first.")
            return
        self.scan_button.configure(state="disabled")
        self.rename_button.configure(state="disabled")
        self.status_var.set("Scanning...")
        for row in self.tree.get_children():
            self.tree.delete(row)
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self) -> None:
        try:
            images = scan_ffpfsc(Path(self.folder_var.get()), recursive=self.recursive_var.get())
        except Exception as exc:
            self.after(0, lambda: self._scan_failed(str(exc)))
            return

        parsed = []
        errors: list[tuple[Path, str]] = []
        for index, image in enumerate(images, start=1):
            self.after(0, lambda i=index, total=len(images): self.status_var.set(f"Analyzing {i}/{total}..."))
            try:
                parsed.append((image, read_metadata(image)))
            except MetadataReadError as exc:
                errors.append((image, str(exc)))

        plan = build_rename_plan(parsed)
        self.after(0, lambda: self._show_results(plan, errors, len(images)))

    def _scan_failed(self, detail: str) -> None:
        self.scan_button.configure(state="normal")
        self.status_var.set("Scan failed")
        messagebox.showerror("PS5 FFPFSC Renamer", detail)

    def _show_results(self, plan: list[RenamePlanItem], errors: list[tuple[Path, str]], total: int) -> None:
        self.plan = plan
        for item in plan:
            self.tree.insert(
                "",
                "end",
                values=(
                    item.source.name,
                    item.metadata.title_id,
                    item.metadata.title_name or "-",
                    item.metadata.content_version or "-",
                    item.destination.name,
                    item.status.value.upper(),
                ),
            )
        for image, detail in errors:
            self.tree.insert("", "end", values=(image.name, "-", detail, "-", "-", "ERROR"))

        ready = sum(item.status is PlanStatus.READY for item in plan)
        blocked = sum(item.status in {PlanStatus.COLLISION, PlanStatus.INVALID} for item in plan) + len(errors)
        self.status_var.set(f"{total} file(s) scanned • {ready} ready • {blocked} blocked")
        self.scan_button.configure(state="normal")
        if ready and not blocked:
            self.rename_button.configure(state="normal")

    def _rename(self) -> None:
        ready = [item for item in self.plan if item.status is PlanStatus.READY]
        if not ready:
            return
        if not messagebox.askyesno(
            "Confirm rename",
            f"Rename {len(ready)} file(s)?\n\nOnly filenames will change; image contents are not modified.",
        ):
            return
        try:
            completed = apply_rename_plan(self.plan)
        except Exception as exc:
            messagebox.showerror("PS5 FFPFSC Renamer", str(exc))
            return
        messagebox.showinfo("PS5 FFPFSC Renamer", f"Renamed {len(completed)} file(s).")
        self._scan()


def main() -> None:
    RenamerApp().mainloop()


if __name__ == "__main__":
    main()
