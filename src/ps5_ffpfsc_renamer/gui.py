from __future__ import annotations

import time
import threading
import tkinter as tk
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .ffpfsc_reader import (
    MetadataReadCancelled,
    MetadataReadError,
    mkpfs_available,
    read_metadata,
)
from .rename_plan import PlanStatus, RenamePlanItem, build_rename_plan
from .renamer import apply_rename_plan
from .scanner import scan_ffpfsc
from .theme import COLORS, apply_theme


class RenamerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PS5 FFPFSC Renamer")
        self.geometry("1280x840")
        self.minsize(1060, 700)
        apply_theme(self)

        self.folder_var = tk.StringVar()
        self.recursive_var = tk.BooleanVar(value=True)
        self.worker_var = tk.StringVar(value="1 (HDD / safest)")
        self.status_var = tk.StringVar(value="Ready — select a folder to begin")
        self.files_var = tk.StringVar(value="0")
        self.ready_var = tk.StringVar(value="0")
        self.blocked_var = tk.StringVar(value="0")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_detail_var = tk.StringVar(value="Idle")
        self.progress_note_var = tk.StringVar(
            value="Large FFPFSC libraries can take time to inspect. Only metadata is extracted; game contents are not unpacked."
        )
        self.plan: list[RenamePlanItem] = []
        self.cancel_event = threading.Event()
        self._scan_active = False

        self._build_ui()

    def _build_ui(self) -> None:
        root_shell = ttk.Frame(self)
        root_shell.pack(fill="both", expand=True)

        self._build_sidebar(root_shell)

        content = ttk.Frame(root_shell, padding=(26, 22, 26, 20))
        content.pack(side="left", fill="both", expand=True)

        header = ttk.Frame(content)
        header.pack(fill="x")
        ttk.Label(header, text="Library Renamer", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Read FFPFSC metadata, preview the detected Title ID, and rename only after validation.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 0))

        self._build_stats(content)
        self._build_controls(content)
        self._build_progress(content)
        self._build_table(content)
        self._build_footer(content)

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        sidebar = tk.Frame(parent, bg=COLORS["sidebar"], width=218, highlightthickness=0, bd=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand = tk.Frame(sidebar, bg=COLORS["sidebar"])
        brand.pack(fill="x", padx=20, pady=(23, 24))
        tk.Label(
            brand,
            text="FFPFSC",
            bg=COLORS["sidebar"],
            fg=COLORS["accent"],
            font=("Segoe UI", 16, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            brand,
            text="RENAMER",
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            brand,
            text=f"v{__version__}",
            bg=COLORS["sidebar"],
            fg=COLORS["muted_dark"],
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

        self._sidebar_group(sidebar, "WORKSPACE")
        active = tk.Frame(sidebar, bg=COLORS["accent_soft"], height=42)
        active.pack(fill="x")
        active.pack_propagate(False)
        tk.Frame(active, bg=COLORS["accent"], width=3).pack(side="left", fill="y")
        tk.Label(
            active,
            text="  ▦  Library",
            bg=COLORS["accent_soft"],
            fg=COLORS["accent_hover"],
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(side="left", fill="both", expand=True, padx=(10, 0))

        self._sidebar_group(sidebar, "ENGINE", top=24)
        status_box = tk.Frame(
            sidebar,
            bg=COLORS["surface"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        status_box.pack(fill="x", padx=16, pady=(5, 0))
        tk.Label(
            status_box,
            text="MkPFS",
            bg=COLORS["surface"],
            fg=COLORS["text_soft"],
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 2))
        engine_ok = mkpfs_available()
        tk.Label(
            status_box,
            text="●  Detected" if engine_ok else "●  Not installed",
            bg=COLORS["surface"],
            fg=COLORS["success"] if engine_ok else COLORS["danger"],
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 10))

        legal = tk.Frame(sidebar, bg=COLORS["sidebar"])
        legal.pack(side="bottom", fill="x", padx=18, pady=18)
        tk.Frame(legal, bg=COLORS["border"], height=1).pack(fill="x", pady=(0, 12))
        tk.Label(
            legal,
            text="Homebrew & personal backup tool",
            bg=COLORS["sidebar"],
            fg=COLORS["muted"],
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            legal,
            text="Not affiliated with Sony Interactive Entertainment",
            bg=COLORS["sidebar"],
            fg=COLORS["muted_dark"],
            font=("Segoe UI", 7),
            anchor="w",
            wraplength=175,
            justify="left",
        ).pack(fill="x", pady=(4, 0))

    @staticmethod
    def _sidebar_group(parent: tk.Widget, text: str, top: int = 0) -> None:
        tk.Label(
            parent,
            text=text,
            bg=COLORS["sidebar"],
            fg=COLORS["muted_dark"],
            font=("Segoe UI", 8, "bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(top, 7))

    def _build_stats(self, parent: ttk.Frame) -> None:
        stats = ttk.Frame(parent)
        stats.pack(fill="x", pady=(20, 14))
        for column in range(3):
            stats.columnconfigure(column, weight=1, uniform="stats")

        cards = (
            ("FILES FOUND", self.files_var, COLORS["accent"]),
            ("READY TO RENAME", self.ready_var, COLORS["success"]),
            ("BLOCKED / ERRORS", self.blocked_var, COLORS["danger"]),
        )
        for column, (label, variable, accent) in enumerate(cards):
            card = tk.Frame(
                stats,
                bg=COLORS["panel"],
                highlightthickness=1,
                highlightbackground=COLORS["border"],
                bd=0,
            )
            card.grid(
                row=0,
                column=column,
                sticky="ew",
                padx=(0 if column == 0 else 6, 0 if column == 2 else 6),
            )
            tk.Frame(card, bg=accent, height=2).pack(fill="x")
            tk.Label(
                card,
                textvariable=variable,
                bg=COLORS["panel"],
                fg=COLORS["text"],
                font=("Segoe UI", 21, "bold"),
                anchor="w",
            ).pack(fill="x", padx=15, pady=(12, 0))
            tk.Label(
                card,
                text=label,
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                font=("Segoe UI", 8, "bold"),
                anchor="w",
            ).pack(fill="x", padx=15, pady=(0, 12))

    def _build_controls(self, parent: ttk.Frame) -> None:
        controls = ttk.Frame(parent, style="Card.TFrame", padding=16)
        controls.pack(fill="x")
        controls.columnconfigure(0, weight=1)

        top = ttk.Frame(controls, style="Card.TFrame")
        top.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 9))
        ttk.Label(top, text="FFPFSC library", style="CardTitle.TLabel").pack(side="left")
        ttk.Label(
            top,
            text="Select a folder containing compressed images",
            style="CardMuted.TLabel",
        ).pack(side="left", padx=(10, 0))

        self.folder_entry = tk.Entry(
            controls,
            textvariable=self.folder_var,
            bg=COLORS["panel_alt"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["accent"],
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
            relief="flat",
            font=("Segoe UI", 10),
        )
        self.folder_entry.grid(row=1, column=0, sticky="ew", ipady=8, padx=(0, 10))
        self.browse_button = ttk.Button(
            controls,
            text="Browse",
            style="Secondary.TButton",
            command=self._browse,
        )
        self.browse_button.grid(row=1, column=1, padx=(0, 8))
        self.scan_button = ttk.Button(
            controls,
            text="Scan library",
            style="Primary.TButton",
            command=self._scan,
        )
        self.scan_button.grid(row=1, column=2)

        self.recursive_check = ttk.Checkbutton(
            controls,
            text="Include subfolders",
            variable=self.recursive_var,
        )
        self.recursive_check.grid(row=2, column=0, sticky="w", pady=(10, 0))

        performance = ttk.Frame(controls, style="Card.TFrame")
        performance.grid(row=2, column=1, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Label(performance, text="Analysis workers", style="CardMuted.TLabel").pack(side="left", padx=(0, 8))
        self.worker_combo = ttk.Combobox(
            performance,
            textvariable=self.worker_var,
            values=("1 (HDD / safest)", "2", "4 (SSD / NVMe)", "Auto"),
            state="readonly",
            width=17,
            style="Performance.TCombobox",
        )
        self.worker_combo.pack(side="left")

    def _build_progress(self, parent: ttk.Frame) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(16, 12))
        card.pack(fill="x", pady=(10, 0))

        top = ttk.Frame(card, style="Card.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="Analysis progress", style="CardTitle.TLabel").pack(side="left")
        self.cancel_button = ttk.Button(
            top,
            text="Cancel",
            style="Danger.TButton",
            command=self._cancel_scan,
            state="disabled",
        )
        self.cancel_button.pack(side="right")

        ttk.Label(
            card,
            textvariable=self.progress_note_var,
            style="CardMuted.TLabel",
            wraplength=850,
            justify="left",
        ).pack(fill="x", pady=(5, 9))

        self.progress = ttk.Progressbar(
            card,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
            style="Scan.Horizontal.TProgressbar",
        )
        self.progress.pack(fill="x")
        ttk.Label(
            card,
            textvariable=self.progress_detail_var,
            style="CardInfo.TLabel",
        ).pack(fill="x", pady=(7, 0))

    def _build_table(self, parent: ttk.Frame) -> None:
        table_card = tk.Frame(
            parent,
            bg=COLORS["surface"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            bd=0,
        )
        table_card.pack(fill="both", expand=True, pady=(14, 14))

        columns = ("file", "title_id", "title", "version", "new_name", "status")
        self.tree = ttk.Treeview(
            table_card,
            columns=columns,
            show="headings",
            style="Library.Treeview",
        )
        headings = {
            "file": "Current file",
            "title_id": "Title ID",
            "title": "Title",
            "version": "Version",
            "new_name": "Proposed name",
            "status": "Status",
        }
        widths = {
            "file": 240,
            "title_id": 105,
            "title": 245,
            "version": 105,
            "new_name": 180,
            "status": 105,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], minwidth=80, anchor="w")

        self.tree.tag_configure("ready", foreground=COLORS["success"])
        self.tree.tag_configure("unchanged", foreground=COLORS["muted"])
        self.tree.tag_configure("collision", foreground=COLORS["danger"])
        self.tree.tag_configure("invalid", foreground=COLORS["danger"])
        self.tree.tag_configure("error", foreground=COLORS["danger"])

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

    def _build_footer(self, parent: ttk.Frame) -> None:
        footer = ttk.Frame(parent)
        footer.pack(fill="x")
        ttk.Label(
            footer,
            textvariable=self.status_var,
            style="Subtitle.TLabel",
        ).pack(side="left")
        self.rename_button = ttk.Button(
            footer,
            text="Rename ready files",
            style="Primary.TButton",
            command=self._rename,
            state="disabled",
        )
        self.rename_button.pack(side="right")

    def _browse(self) -> None:
        selected = filedialog.askdirectory(title="Select FFPFSC folder")
        if selected:
            self.folder_var.set(selected)

    def _scan(self) -> None:
        folder_text = self.folder_var.get().strip()
        if not folder_text:
            messagebox.showwarning("PS5 FFPFSC Renamer", "Select a folder first.")
            return
        if not mkpfs_available():
            messagebox.showerror(
                "MkPFS required",
                "MkPFS is not installed.\n\nInstall it with:\npython -m pip install mkpfs==0.0.9",
            )
            return

        folder = Path(folder_text)
        recursive = bool(self.recursive_var.get())
        worker_setting = self.worker_var.get()

        self.cancel_event.clear()
        self.plan = []
        self._set_scan_controls(active=True)
        self.rename_button.configure(state="disabled")
        self.status_var.set("Scanning library...")
        self.files_var.set("0")
        self.ready_var.set("0")
        self.blocked_var.set("0")
        self.progress_var.set(0.0)
        self.progress_detail_var.set("Discovering .ffpfsc files...")
        self.progress_note_var.set(
            "Finding files first. Metadata analysis begins immediately afterwards and progress will update after each completed image."
        )
        for row in self.tree.get_children():
            self.tree.delete(row)

        threading.Thread(
            target=self._scan_worker,
            args=(folder, recursive, worker_setting),
            daemon=True,
        ).start()

    def _set_scan_controls(self, active: bool) -> None:
        self._scan_active = active
        if active:
            self.scan_button.configure(state="disabled")
            self.browse_button.configure(state="disabled")
            self.folder_entry.configure(state="disabled")
            self.worker_combo.configure(state="disabled")
            self.recursive_check.state(["disabled"])
            self.cancel_button.configure(state="normal")
        else:
            self.scan_button.configure(state="normal")
            self.browse_button.configure(state="normal")
            self.folder_entry.configure(state="normal")
            self.worker_combo.configure(state="readonly")
            self.recursive_check.state(["!disabled"])
            self.cancel_button.configure(state="disabled")

    def _cancel_scan(self) -> None:
        if not self._scan_active:
            return
        self.cancel_event.set()
        self.cancel_button.configure(state="disabled")
        self.status_var.set("Cancelling analysis...")
        self.progress_note_var.set(
            "Cancellation requested. Running MkPFS readers are being stopped; no files will be renamed."
        )

    @staticmethod
    def _resolve_worker_count(setting: str, total: int) -> int:
        if total <= 1:
            return 1
        if setting == "Auto":
            # Conservative default: two concurrent readers. The operation is
            # storage-bound, so using every CPU core can make HDDs slower.
            return min(2, total)
        if setting.startswith("4"):
            return min(4, total)
        if setting.startswith("2"):
            return min(2, total)
        return 1

    def _scan_worker(self, folder: Path, recursive: bool, worker_setting: str) -> None:
        try:
            images = scan_ffpfsc(folder, recursive=recursive)
        except Exception as exc:
            self.after(0, lambda detail=str(exc): self._scan_failed(detail))
            return

        total = len(images)
        workers = self._resolve_worker_count(worker_setting, total)
        started_at = time.monotonic()
        self.after(0, lambda: self._analysis_started(total, workers))

        if self.cancel_event.is_set():
            self.after(0, lambda: self._scan_cancelled(0, total))
            return

        if total == 0:
            self.after(0, lambda: self._show_results([], [], 0, started_at, workers))
            return

        parsed: list[tuple[Path, object]] = []
        errors: list[tuple[Path, str]] = []
        completed = 0

        if workers == 1:
            for image in images:
                if self.cancel_event.is_set():
                    break
                try:
                    metadata = read_metadata(image, cancel_event=self.cancel_event)
                    parsed.append((image, metadata))
                except MetadataReadCancelled:
                    break
                except MetadataReadError as exc:
                    errors.append((image, str(exc)))
                except Exception as exc:
                    errors.append((image, f"Unexpected error: {exc}"))

                completed += 1
                self.after(
                    0,
                    lambda done=completed, name=image.name: self._progress_update(
                        done,
                        total,
                        started_at,
                        name,
                        workers,
                    ),
                )
        else:
            executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ffpfsc-reader")
            future_to_image = {
                executor.submit(read_metadata, image, 120, self.cancel_event): image
                for image in images
            }
            pending = set(future_to_image)
            try:
                while pending and not self.cancel_event.is_set():
                    done, pending = wait(
                        pending,
                        timeout=0.2,
                        return_when=FIRST_COMPLETED,
                    )
                    for future in done:
                        image = future_to_image[future]
                        try:
                            metadata = future.result()
                            parsed.append((image, metadata))
                        except MetadataReadCancelled:
                            self.cancel_event.set()
                            break
                        except MetadataReadError as exc:
                            errors.append((image, str(exc)))
                        except Exception as exc:
                            errors.append((image, f"Unexpected error: {exc}"))

                        completed += 1
                        self.after(
                            0,
                            lambda done_count=completed, name=image.name: self._progress_update(
                                done_count,
                                total,
                                started_at,
                                name,
                                workers,
                            ),
                        )
            finally:
                if self.cancel_event.is_set():
                    for future in pending:
                        future.cancel()
                executor.shutdown(wait=True, cancel_futures=True)

        if self.cancel_event.is_set():
            self.after(0, lambda: self._scan_cancelled(completed, total))
            return

        # The plan is built only after all metadata has been collected so that
        # cross-file destination collisions can be detected correctly.
        plan = build_rename_plan(parsed)
        self.after(
            0,
            lambda: self._show_results(plan, errors, total, started_at, workers),
        )

    def _analysis_started(self, total: int, workers: int) -> None:
        self.files_var.set(str(total))
        if total == 0:
            self.progress_note_var.set("No .ffpfsc files were found in the selected location.")
            self.progress_detail_var.set("0 files found")
            return

        if total >= 20:
            self.progress_note_var.set(
                f"Large library detected: {total} FFPFSC files. Analysis may take several minutes on large images or slower drives. "
                f"Keep the window open; progress, elapsed time and ETA are updated continuously. Using {workers} worker(s)."
            )
        else:
            self.progress_note_var.set(
                f"{total} FFPFSC file(s) found. Reading only sce_sys/param.json metadata with {workers} worker(s)."
            )
        self.progress_detail_var.set(f"0/{total} • 0% • elapsed 00:00 • ETA calculating...")
        self.status_var.set(f"Analyzing 0/{total}...")

    def _progress_update(
        self,
        completed: int,
        total: int,
        started_at: float,
        last_name: str,
        workers: int,
    ) -> None:
        elapsed = max(0.0, time.monotonic() - started_at)
        percent = (completed / total * 100.0) if total else 0.0
        self.progress_var.set(percent)

        eta_text = "calculating..."
        if completed > 0 and elapsed > 0 and completed < total:
            rate = completed / elapsed
            if rate > 0:
                eta_text = self._format_duration((total - completed) / rate)
        elif completed >= total:
            eta_text = "00:00"

        self.progress_detail_var.set(
            f"{completed}/{total} • {percent:.0f}% • elapsed {self._format_duration(elapsed)} • "
            f"ETA {eta_text} • {workers} worker(s)"
        )
        self.status_var.set(f"Analyzing {completed}/{total} — {last_name}")

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds_int = max(0, int(seconds))
        hours, remainder = divmod(seconds_int, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _scan_failed(self, detail: str) -> None:
        self._set_scan_controls(active=False)
        self.status_var.set("Scan failed")
        self.blocked_var.set("1")
        self.progress_note_var.set("The scan stopped because an error occurred.")
        self.progress_detail_var.set(detail)
        messagebox.showerror("PS5 FFPFSC Renamer", detail)

    def _scan_cancelled(self, completed: int, total: int) -> None:
        self.plan = []
        self._set_scan_controls(active=False)
        percent = (completed / total * 100.0) if total else 0.0
        self.progress_var.set(percent)
        self.progress_note_var.set(
            "Analysis cancelled by the user. No filenames or FFPFSC contents were changed."
        )
        self.progress_detail_var.set(f"Stopped after {completed}/{total} file(s) • {percent:.0f}%")
        self.status_var.set(f"Cancelled — {completed}/{total} file(s) analyzed")
        self.rename_button.configure(state="disabled")

    def _show_results(
        self,
        plan: list[RenamePlanItem],
        errors: list[tuple[Path, str]],
        total: int,
        started_at: float,
        workers: int,
    ) -> None:
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
                tags=(item.status.value,),
            )
        for image, detail in errors:
            self.tree.insert(
                "",
                "end",
                values=(image.name, "-", detail, "-", "-", "ERROR"),
                tags=("error",),
            )

        ready = sum(item.status is PlanStatus.READY for item in plan)
        blocked = sum(
            item.status in {PlanStatus.COLLISION, PlanStatus.INVALID}
            for item in plan
        ) + len(errors)
        unchanged = sum(item.status is PlanStatus.UNCHANGED for item in plan)
        elapsed = max(0.0, time.monotonic() - started_at)

        self.files_var.set(str(total))
        self.ready_var.set(str(ready))
        self.blocked_var.set(str(blocked))
        self.progress_var.set(100.0 if total else 0.0)
        self.progress_note_var.set(
            "Analysis complete. Review the detected metadata and proposed filenames before applying any rename."
        )
        self.progress_detail_var.set(
            f"Completed {total} file(s) in {self._format_duration(elapsed)} • {workers} worker(s)"
        )
        self.status_var.set(
            f"Scan complete — {ready} ready, {unchanged} already named, {blocked} blocked/error(s)"
        )
        self._set_scan_controls(active=False)
        if ready and not blocked:
            self.rename_button.configure(state="normal")

    def _rename(self) -> None:
        ready = [item for item in self.plan if item.status is PlanStatus.READY]
        if not ready:
            return
        if not messagebox.askyesno(
            "Confirm rename",
            f"Rename {len(ready)} file(s)?\n\nOnly filenames will change. FFPFSC image contents are not modified.",
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
