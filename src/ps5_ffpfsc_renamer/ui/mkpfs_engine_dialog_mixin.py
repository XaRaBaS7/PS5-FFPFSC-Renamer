from __future__ import annotations

import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..ffpfsc_reader import _mkpfs_command, mkpfs_source_description, set_mkpfs_executable
from ..process_utils import run_hidden


class MkPFSEngineDialogMixin:
    """MkPFS source selection and silent engine self-test dialog."""

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
            text=(
                "The packaged app normally uses its sibling mkpfs-helper.exe. "
                "You can optionally point the renamer at another compatible MkPFS executable "
                "for testing/upgrades."
            ),
            style="CardMuted.TLabel",
            wraplength=710,
        ).pack(anchor="w", pady=(2, 10))

        source_var = tk.StringVar()
        ttk.Label(frame, text="Current source", style="CardMuted.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            textvariable=source_var,
            style="Card.TLabel",
            wraplength=710,
        ).pack(anchor="w", pady=(2, 12))

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
                    part
                    for part in (completed.stdout.strip(), completed.stderr.strip())
                    if part
                )
                if completed.returncode == 0:
                    self._log("OK", "MkPFS engine test succeeded")
                    messagebox.showinfo(
                        "MkPFS test",
                        "MkPFS launched successfully.\n\n" + (output[:1200] or "No output."),
                        parent=window,
                    )
                else:
                    self._log(
                        "WARN",
                        f"MkPFS engine test returned code {completed.returncode}",
                    )
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
        ttk.Button(
            buttons,
            text="Use automatic / bundled",
            command=automatic,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Test engine", command=test_engine).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")
        refresh()
