from __future__ import annotations

import subprocess
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .activity_log import ActivityLog
from .ffpfsc_reader import (
    _mkpfs_command,
    mkpfs_source_description,
    set_mkpfs_executable,
)
from .gui_v11 import RenamerApp as RenamerAppV11
from .metadata import GameMetadata
from .process_utils import run_hidden
from .renamer import RenameStep
from .theme import COLORS


class RenamerApp(RenamerAppV11):
    """v0.3.1 desktop shell with silent MkPFS and an integrated activity log."""

    def __init__(self) -> None:
        self._activity_log = ActivityLog()
        self._log_text: tk.Text | None = None
        self._log_body: ttk.Frame | None = None
        self._log_toggle_button: ttk.Button | None = None
        self._log_visible = True
        super().__init__()
        self._log("INFO", f"PS5 FFPFSC Renamer v{__version__} started")
        self._log("ENGINE", mkpfs_source_description())

    # ---------------------------------------------------------- log panel
    def _build_footer(self, parent: ttk.Frame) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(10, 6))
        card.pack(fill="x", pady=(6, 5))

        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Activity log", style="CardTitle.TLabel").pack(side="left")
        ttk.Label(
            header,
            text="MkPFS runs silently — activity and errors appear here",
            style="CardMuted.TLabel",
        ).pack(side="left", padx=(10, 0))

        ttk.Button(header, text="Clear", command=self._clear_activity_log).pack(side="right")
        ttk.Button(header, text="Copy", command=self._copy_activity_log).pack(
            side="right", padx=(0, 5)
        )
        self._log_toggle_button = ttk.Button(
            header,
            text="Hide",
            command=self._toggle_activity_log,
        )
        self._log_toggle_button.pack(side="right", padx=(0, 5))

        self._log_body = ttk.Frame(card, style="Card.TFrame")
        self._log_body.pack(fill="x", pady=(5, 0))

        log_frame = tk.Frame(
            self._log_body,
            bg=COLORS["panel_alt"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        log_frame.pack(fill="x")

        self._log_text = tk.Text(
            log_frame,
            height=5,
            wrap="none",
            bg=COLORS["panel_alt"],
            fg=COLORS["text_soft"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["accent"],
            selectforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            font=("Consolas", 8),
            padx=7,
            pady=5,
        )
        self._log_text.pack(side="left", fill="x", expand=True)
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self._log_text.yview)
        scroll.pack(side="right", fill="y")
        self._log_text.configure(yscrollcommand=scroll.set)

        for tag, color in (
            ("INFO", COLORS["text_soft"]),
            ("ENGINE", COLORS["muted"]),
            ("CACHE", COLORS["warning"]),
            ("MKPFS", COLORS["accent_hover"]),
            ("OK", COLORS["success"]),
            ("WARN", COLORS["warning"]),
            ("ERROR", COLORS["danger"]),
        ):
            self._log_text.tag_configure(tag, foreground=color)

        for line in self._activity_log.tail(80):
            self._insert_log_line(line, self._level_from_line(line))

        super()._build_footer(parent)

    @staticmethod
    def _level_from_line(line: str) -> str:
        for level in ("ERROR", "WARN", "OK", "MKPFS", "CACHE", "ENGINE", "INFO"):
            if f"[{level}]" in line:
                return level
        return "INFO"

    def _insert_log_line(self, line: str, level: str) -> None:
        if self._log_text is None:
            return
        self._log_text.configure(state="normal")
        self._log_text.insert("end", line + "\n", level if level in self._log_text.tag_names() else "INFO")
        # Keep the UI bounded even after very long sessions. The persistent log
        # on disk keeps a larger rolling history.
        try:
            line_count = int(self._log_text.index("end-1c").split(".")[0])
            if line_count > 800:
                self._log_text.delete("1.0", "101.0")
        except (tk.TclError, ValueError):
            pass
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _log(self, level: str, message: str) -> None:
        line = self._activity_log.write(level, message)
        if threading.current_thread() is threading.main_thread():
            self._insert_log_line(line, level.upper())
        else:
            try:
                self.after(0, lambda: self._insert_log_line(line, level.upper()))
            except tk.TclError:
                pass

    def _toggle_activity_log(self) -> None:
        if self._log_body is None or self._log_toggle_button is None:
            return
        if self._log_visible:
            self._log_body.pack_forget()
            self._log_visible = False
            self._log_toggle_button.configure(text="Show")
        else:
            self._log_body.pack(fill="x", pady=(5, 0))
            self._log_visible = True
            self._log_toggle_button.configure(text="Hide")

    def _clear_activity_log(self) -> None:
        self._activity_log.clear()
        if self._log_text is not None:
            self._log_text.configure(state="normal")
            self._log_text.delete("1.0", "end")
            self._log_text.configure(state="disabled")

    def _copy_activity_log(self) -> None:
        if self._log_text is None:
            return
        text = self._log_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set("Activity log copied to clipboard")

    # -------------------------------------------------------- scan logging
    def _scan(self) -> None:
        roots = self.library_roots or ([Path(self.folder_var.get().strip())] if self.folder_var.get().strip() else [])
        if roots:
            self._log(
                "INFO",
                f"Scan requested: {len(roots)} root(s), recursive={bool(self.recursive_var.get())}, workers={self.worker_var.get()}",
            )
        super()._scan()

    def _analysis_started(self, total: int, cache_hits: int, misses: int, workers: int) -> None:
        super()._analysis_started(total, cache_hits, misses, workers)
        self._log(
            "CACHE",
            f"Discovery complete: {total} file(s), {cache_hits} cache hit(s), {misses} MkPFS read(s), {workers} worker(s)",
        )

    def _progress_update(
        self,
        completed: int,
        total: int,
        started_at: float,
        last_name: str,
        workers: int,
        cache_hits: int,
        mkpfs_reads: int,
    ) -> None:
        super()._progress_update(
            completed,
            total,
            started_at,
            last_name,
            workers,
            cache_hits,
            mkpfs_reads,
        )
        self._log("MKPFS", f"Processed {last_name} ({completed}/{total})")

    def _scan_complete(
        self,
        parsed: list[tuple[Path, GameMetadata]],
        errors: list[tuple[Path, str]],
        total: int,
        started_at: float,
        workers: int,
        cache_hits: int,
        mkpfs_reads: int,
    ) -> None:
        super()._scan_complete(
            parsed,
            errors,
            total,
            started_at,
            workers,
            cache_hits,
            mkpfs_reads,
        )
        partial_count = len(getattr(self, "partial_items", []))
        hard_errors = len(getattr(self, "scan_errors", []))
        level = "WARN" if partial_count or hard_errors else "OK"
        self._log(
            level,
            f"Scan complete: {total} file(s), cache {cache_hits}, MkPFS {mkpfs_reads}, PARTIAL {partial_count}, ERROR {hard_errors}",
        )

    def _scan_failed(self, detail: str) -> None:
        self._log("ERROR", f"Scan failed: {detail}")
        super()._scan_failed(detail)

    def _scan_cancelled(self, completed: int, total: int) -> None:
        self._log("WARN", f"Scan cancelled after {completed}/{total} file(s)")
        super()._scan_cancelled(completed, total)

    # ------------------------------------------------------ action logging
    def _run_diagnostics(self, path: Path) -> None:
        self._log("INFO", f"Diagnostics requested: {path}")
        super()._run_diagnostics(path)

    def _analyze_paths(self, paths: list[Path]) -> None:
        self._log("INFO", f"Forced re-analysis requested for {len(paths)} file(s)")
        super()._analyze_paths(paths)

    def _finalize_completed_rename(
        self,
        *,
        label: str,
        completed: list[tuple[Path, Path]],
        steps: list[RenameStep],
    ) -> None:
        super()._finalize_completed_rename(label=label, completed=completed, steps=steps)
        if completed:
            self._log("OK", f"{label}: {len(completed)} file(s) renamed")
            for old_path, new_path in completed[:20]:
                self._log("INFO", f"Rename: {old_path} -> {new_path}")
            if len(completed) > 20:
                self._log("INFO", f"Rename log abbreviated: {len(completed) - 20} additional item(s)")

    # -------------------------------------------------- silent engine test
    def _show_mkpfs_settings(self) -> None:
        window = tk.Toplevel(self)
        window.title("MkPFS engine")
        window.transient(self)
        window.geometry("760x350")
        window.minsize(620, 320)

        frame = ttk.Frame(window, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="MkPFS engine", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="The packaged app normally uses its sibling mkpfs-helper.exe. You can optionally point the renamer at another compatible MkPFS executable for testing/upgrades.",
            style="CardMuted.TLabel",
            wraplength=710,
        ).pack(anchor="w", pady=(2, 10))

        source_var = tk.StringVar()
        ttk.Label(frame, text="Current source", style="CardMuted.TLabel").pack(anchor="w")
        ttk.Label(frame, textvariable=source_var, style="Card.TLabel", wraplength=710).pack(anchor="w", pady=(2, 12))

        def refresh() -> None:
            source_var.set(mkpfs_source_description())

        def choose() -> None:
            selected = filedialog.askopenfilename(
                title="Select MkPFS executable",
                parent=window,
                filetypes=(("Executable files", "*.exe"), ("All files", "*.*")),
            )
            if not selected:
                return
            selected_path = Path(selected).resolve()
            if not selected_path.is_file():
                return
            self._mkpfs_path = str(selected_path)
            set_mkpfs_executable(selected_path)
            self._queue_save_preferences()
            self._log("ENGINE", f"Custom MkPFS selected: {selected_path}")
            refresh()

        def automatic() -> None:
            self._mkpfs_path = None
            set_mkpfs_executable(None)
            self._queue_save_preferences()
            self._log("ENGINE", f"MkPFS source reset: {mkpfs_source_description()}")
            refresh()

        def test_engine() -> None:
            self._log("ENGINE", "Testing MkPFS engine")
            try:
                command = [*_mkpfs_command(), "--help"]
                completed = run_hidden(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=15,
                    check=False,
                )
                output = "\n".join(
                    part for part in (completed.stdout.strip(), completed.stderr.strip()) if part
                )
                if completed.returncode == 0:
                    self._log("OK", "MkPFS engine test succeeded")
                    messagebox.showinfo(
                        "MkPFS test",
                        "MkPFS launched successfully.\n\n" + (output[:1200] or "No output."),
                        parent=window,
                    )
                else:
                    self._log("WARN", f"MkPFS engine test returned code {completed.returncode}")
                    messagebox.showwarning(
                        "MkPFS test",
                        f"MkPFS returned code {completed.returncode}.\n\n{output[:1600]}",
                        parent=window,
                    )
            except Exception as exc:
                self._log("ERROR", f"MkPFS engine test failed: {exc}")
                messagebox.showerror("MkPFS test", str(exc), parent=window)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Choose executable...", command=choose).pack(side="left")
        ttk.Button(buttons, text="Use automatic / bundled", command=automatic).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Test engine", command=test_engine).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")
        refresh()


def main() -> None:
    RenamerApp().mainloop()


if __name__ == "__main__":
    main()
