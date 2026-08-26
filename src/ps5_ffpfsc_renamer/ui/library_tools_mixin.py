from __future__ import annotations

import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from ..cache import quick_fingerprint
from ..diagnostics import diagnose_image
from ..library_view import human_size
from ..workspace_models import LibraryRecord


class LibraryToolsMixin:
    """Diagnostics/reporting and duplicate inspection for library rows."""

    def _show_record_details(self, record: LibraryRecord) -> None:
        text = (
            f"File: {record.view.source.name}\n"
            f"Path: {record.view.source}\n"
            f"Size: {human_size(record.view.size)}\n\n"
            f"Title ID: {record.view.title_id}\n"
            f"Title: {record.view.title}\n"
            f"Version: {record.view.version}\n"
            f"Proposed output: {record.view.output}\n"
            f"Status: {record.view.status}"
        )
        if record.view.duplicate:
            text += "\nDuplicate Title ID: yes"
        if record.friendly:
            text += f"\n\nNote: {record.friendly}"
        messagebox.showinfo("FFPFSC details", text, parent=self)

    def _run_diagnostics(self, path: Path) -> None:
        if self._scan_active:
            messagebox.showinfo(
                "Diagnostics",
                "Wait for the current library scan to finish first.",
                parent=self,
            )
            return
        self.status_var.set(f"Running diagnostics: {path.name}...")

        def worker() -> None:
            try:
                report = diagnose_image(
                    path,
                    library_root=self._matching_root(path),
                    timeout=45,
                )
            except Exception as exc:
                report = f"Diagnostics failed:\n{exc}"
            self.after(0, lambda: self._show_report("FFPFSC diagnostics", report))

        threading.Thread(target=worker, daemon=True).start()

    def _show_report(self, title: str, text: str) -> None:
        self.status_var.set("Ready")
        window = tk.Toplevel(self)
        window.title(title)
        window.transient(self)
        window.geometry("900x620")
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        box = tk.Text(
            frame,
            wrap="word",
            bg="#181321",
            fg="#f4f0ff",
            insertbackground="#ffffff",
            relief="flat",
            font=("Consolas", 9),
        )
        box.pack(fill="both", expand=True)
        box.insert("1.0", text)
        box.configure(state="disabled")
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(
            buttons,
            text="Copy report",
            command=lambda: self._copy_text(text),
        ).pack(side="left")
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")

    def _compare_duplicates(self, title_id: str) -> None:
        group = list(self._duplicate_groups.get(title_id.upper(), []))
        if len(group) < 2:
            return
        self.status_var.set(f"Comparing duplicates: {title_id}...")

        def worker() -> None:
            lines = [f"DUPLICATE COMPARISON — {title_id}", ""]
            fingerprints: list[tuple[int | None, str | None]] = []
            for index, record in enumerate(group, start=1):
                path = record.view.source
                fingerprint = None
                try:
                    fingerprint = quick_fingerprint(path)
                except OSError:
                    pass
                fingerprints.append((record.view.size, fingerprint))
                lines.extend(
                    (
                        f"[{index}] {record.view.title}",
                        f"Path: {path}",
                        f"Version: {record.view.version}",
                        f"Size: {human_size(record.view.size)}",
                        f"Status: {record.view.status}",
                        f"Quick fingerprint: {fingerprint or 'unavailable'}",
                        "",
                    )
                )
            comparable = [value for value in fingerprints if value[1] is not None]
            same = (
                bool(comparable)
                and len(set(comparable)) == 1
                and len(comparable) == len(group)
            )
            lines.append(
                "Assessment: sampled size/fingerprint matches for every file."
                if same
                else "Assessment: files differ in size and/or sampled fingerprint, or a sample could not be read."
            )
            lines.append(
                "Note: the quick fingerprint reads only small samples and is an identity hint, not a full-file checksum."
            )
            report = "\n".join(lines)
            self.after(
                0,
                lambda: self._show_report(f"Duplicates — {title_id}", report),
            )

        threading.Thread(target=worker, daemon=True).start()
