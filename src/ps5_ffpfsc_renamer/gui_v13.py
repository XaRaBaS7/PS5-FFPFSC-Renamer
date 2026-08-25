from __future__ import annotations

import json
import math
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from .diagnostics import classify_reader_error
from .game_details import GameDetails, load_game_details
from .gui_v12 import RenamerApp as RenamerAppV12
from .gui_v9 import _Record
from .library_view import human_size
from .theme import COLORS


class RenamerApp(RenamerAppV12):
    """v0.4 game-details inspector with cached selective icon/JSON reads."""

    def __init__(self) -> None:
        self._details_body: ttk.Frame | None = None
        self._details_toggle_button: ttk.Button | None = None
        self._details_status_var: tk.StringVar | None = None
        self._details_vars: dict[str, tk.StringVar] = {}
        self._details_json: tk.Text | None = None
        self._details_icon_label: tk.Label | None = None
        self._details_photo: tk.PhotoImage | None = None
        self._details_record: _Record | None = None
        self._details_visible = False
        self._details_generation = 0
        super().__init__()
        self.tree.bind("<<TreeviewSelect>>", self._on_details_selection, add="+")

    # ------------------------------------------------------ details panel
    def _build_footer(self, parent: ttk.Frame) -> None:
        self._build_details_panel(parent)
        super()._build_footer(parent)

    def _build_details_panel(self, parent: ttk.Frame) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(10, 6))
        card.pack(fill="x", pady=(6, 0))

        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Game details", style="CardTitle.TLabel").pack(side="left")
        self._details_status_var = tk.StringVar(value="Select one game to inspect")
        ttk.Label(
            header,
            textvariable=self._details_status_var,
            style="CardMuted.TLabel",
        ).pack(side="left", padx=(10, 0))

        self._details_toggle_button = ttk.Button(
            header,
            text="Show",
            command=self._toggle_details_panel,
            state="disabled",
        )
        self._details_toggle_button.pack(side="right")
        ttk.Button(
            header,
            text="Refresh details",
            command=self._refresh_selected_details,
        ).pack(side="right", padx=(0, 5))

        self._details_body = ttk.Frame(card, style="Card.TFrame")

        notebook = ttk.Notebook(self._details_body)
        notebook.pack(fill="both", expand=True, pady=(6, 0))

        summary = ttk.Frame(notebook, padding=10)
        raw = ttk.Frame(notebook, padding=8)
        notebook.add(summary, text="Details")
        notebook.add(raw, text="param.json")

        icon_frame = tk.Frame(
            summary,
            width=178,
            height=178,
            bg=COLORS["panel_alt"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        icon_frame.pack(side="left", anchor="n", padx=(0, 14))
        icon_frame.pack_propagate(False)
        self._details_icon_label = tk.Label(
            icon_frame,
            text="ICON0\nnot loaded",
            bg=COLORS["panel_alt"],
            fg=COLORS["muted"],
            font=("Segoe UI", 10),
            justify="center",
        )
        self._details_icon_label.pack(fill="both", expand=True)

        info = ttk.Frame(summary)
        info.pack(side="left", fill="both", expand=True)
        self._details_vars = {
            "title": tk.StringVar(value="-"),
            "title_id": tk.StringVar(value="-"),
            "content_version": tk.StringVar(value="-"),
            "master_version": tk.StringVar(value="-"),
            "size": tk.StringVar(value="-"),
            "status": tk.StringVar(value="-"),
            "source": tk.StringVar(value="-"),
            "path": tk.StringVar(value="-"),
        }

        rows = (
            ("Title", "title"),
            ("Title ID / PPSA", "title_id"),
            ("Content version", "content_version"),
            ("Master version", "master_version"),
            ("FFPFSC size", "size"),
            ("Renamer status", "status"),
            ("Details source", "source"),
            ("Path", "path"),
        )
        for row_index, (label, key) in enumerate(rows):
            ttk.Label(info, text=label, style="CardMuted.TLabel").grid(
                row=row_index, column=0, sticky="nw", padx=(0, 12), pady=3
            )
            ttk.Label(
                info,
                textvariable=self._details_vars[key],
                style="CardInfo.TLabel",
                wraplength=780 if key == "path" else 560,
                justify="left",
            ).grid(row=row_index, column=1, sticky="nw", pady=3)
        info.columnconfigure(1, weight=1)

        actions = ttk.Frame(info)
        actions.grid(row=len(rows), column=1, sticky="w", pady=(9, 0))
        ttk.Button(actions, text="Show in Explorer", command=self._details_show_in_explorer).pack(
            side="left"
        )
        ttk.Button(actions, text="Open folder", command=self._details_open_folder).pack(
            side="left", padx=(5, 0)
        )
        ttk.Button(actions, text="Run diagnostics", command=self._details_run_diagnostics).pack(
            side="left", padx=(5, 0)
        )

        raw_toolbar = ttk.Frame(raw)
        raw_toolbar.pack(fill="x", pady=(0, 5))
        ttk.Label(
            raw_toolbar,
            text="Raw sce_sys/param.json extracted selectively from the FFPFSC image",
            style="CardMuted.TLabel",
        ).pack(side="left")
        ttk.Button(raw_toolbar, text="Copy JSON", command=self._copy_details_json).pack(side="right")

        text_frame = tk.Frame(
            raw,
            bg=COLORS["panel_alt"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        text_frame.pack(fill="both", expand=True)
        self._details_json = tk.Text(
            text_frame,
            height=11,
            wrap="none",
            bg=COLORS["panel_alt"],
            fg=COLORS["text_soft"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["accent"],
            selectforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            font=("Consolas", 9),
            padx=7,
            pady=5,
        )
        self._details_json.pack(side="left", fill="both", expand=True)
        scroll_y = ttk.Scrollbar(text_frame, orient="vertical", command=self._details_json.yview)
        scroll_y.pack(side="right", fill="y")
        scroll_x = ttk.Scrollbar(raw, orient="horizontal", command=self._details_json.xview)
        scroll_x.pack(fill="x")
        self._details_json.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self._set_details_json("Select a game to load sce_sys/param.json")

    def _toggle_details_panel(self) -> None:
        if self._details_body is None or self._details_toggle_button is None:
            return
        if self._details_visible:
            self._details_body.pack_forget()
            self._details_visible = False
            self._details_toggle_button.configure(text="Show")
        else:
            self._details_body.pack(fill="x")
            self._details_visible = True
            self._details_toggle_button.configure(text="Hide")

    def _ensure_details_visible(self) -> None:
        if self._details_body is None or self._details_visible:
            return
        self._details_body.pack(fill="x")
        self._details_visible = True
        if self._details_toggle_button is not None:
            self._details_toggle_button.configure(text="Hide", state="normal")

    def _set_details_json(self, text: str) -> None:
        if self._details_json is None:
            return
        self._details_json.configure(state="normal")
        self._details_json.delete("1.0", "end")
        self._details_json.insert("1.0", text)
        self._details_json.configure(state="disabled")

    def _reset_details_icon(self, text: str = "ICON0\nnot loaded") -> None:
        self._details_photo = None
        if self._details_icon_label is not None:
            self._details_icon_label.configure(image="", text=text)

    def _show_icon(self, path: Path | None) -> None:
        if self._details_icon_label is None:
            return
        if path is None or not path.is_file():
            self._reset_details_icon("ICON0\nnot available")
            return
        try:
            image = tk.PhotoImage(file=str(path))
            factor = max(1, math.ceil(max(image.width(), image.height()) / 164))
            if factor > 1:
                image = image.subsample(factor, factor)
            self._details_photo = image
            self._details_icon_label.configure(image=image, text="")
        except tk.TclError:
            self._reset_details_icon("ICON0\nunsupported image")

    # -------------------------------------------------------- selection
    def _on_details_selection(self, _event=None) -> None:
        rows = self.tree.selection()
        if len(rows) != 1:
            self._details_record = None
            self._details_generation += 1
            if self._details_status_var is not None:
                self._details_status_var.set(
                    "Select one game to inspect" if not rows else f"{len(rows)} games selected"
                )
            if self._details_toggle_button is not None:
                self._details_toggle_button.configure(state="disabled" if not rows else "normal")
            return
        record = self._row_records.get(rows[0])
        if record is not None:
            self._activate_details_record(record)

    def _activate_details_record(self, record: _Record, *, force: bool = False) -> None:
        self._details_record = record
        self._details_generation += 1
        generation = self._details_generation
        self._ensure_details_visible()
        if self._details_toggle_button is not None:
            self._details_toggle_button.configure(state="normal")

        view = record.view
        self._details_vars["title"].set(view.title or "-")
        self._details_vars["title_id"].set(view.title_id or "-")
        self._details_vars["content_version"].set(view.version or "-")
        self._details_vars["master_version"].set("Loading...")
        self._details_vars["size"].set(human_size(view.size))
        self._details_vars["status"].set(view.status)
        if view.status == "PARTIAL":
            source = f"Path fallback ({record.inference_source or 'filename/folder'})"
        elif view.status == "ERROR":
            source = "Unavailable in library scan"
        else:
            source = "Verified scan metadata / cache"
        self._details_vars["source"].set(source)
        self._details_vars["path"].set(str(view.source))
        self._set_details_json("Loading sce_sys/param.json...")
        self._reset_details_icon("Loading\nicon0.png...")
        if self._details_status_var is not None:
            self._details_status_var.set(f"Loading {view.source.name}...")

        thread = threading.Thread(
            target=self._details_worker,
            args=(view.source, generation, force),
            daemon=True,
            name="ffpfsc-details",
        )
        thread.start()

    def _details_worker(self, path: Path, generation: int, force: bool) -> None:
        try:
            details = load_game_details(path, force=force)
        except Exception as exc:
            detail = str(exc)
            try:
                self.after(0, lambda: self._details_failed(path, generation, detail))
            except tk.TclError:
                pass
            return
        try:
            self.after(0, lambda: self._details_loaded(path, generation, details))
        except tk.TclError:
            pass

    def _details_loaded(self, path: Path, generation: int, details: GameDetails) -> None:
        if generation != self._details_generation:
            return
        record = self._details_record
        if record is None or record.view.source.resolve(strict=False) != path.resolve(strict=False):
            return

        metadata = details.metadata
        self._details_vars["title"].set(metadata.title_name or record.view.title or "-")
        self._details_vars["title_id"].set(metadata.title_id)
        self._details_vars["content_version"].set(metadata.content_version or "-")
        self._details_vars["master_version"].set(metadata.master_version or "-")
        self._details_vars["source"].set(
            "Details cache" if details.cache_hit else "MkPFS selective extraction"
        )
        self._set_details_json(json.dumps(details.param_json, indent=2, ensure_ascii=False))
        self._show_icon(details.icon_path)
        if self._details_status_var is not None:
            suffix = "cache" if details.cache_hit else "MkPFS"
            icon = " • icon0.png" if details.icon_path is not None else " • no icon0.png"
            self._details_status_var.set(f"Loaded from {suffix}{icon}")
        self._log(
            "CACHE" if details.cache_hit else "MKPFS",
            f"Game details loaded: {path.name} ({'cache' if details.cache_hit else 'selective extraction'})",
        )

    def _details_failed(self, path: Path, generation: int, detail: str) -> None:
        if generation != self._details_generation:
            return
        code, friendly = classify_reader_error(detail)
        self._details_vars["master_version"].set("-")
        self._details_vars["source"].set(f"Details unavailable ({code})")
        self._set_details_json(f"Unable to read sce_sys/param.json\n\n{friendly}\n\nTechnical detail:\n{detail}")
        self._reset_details_icon("ICON0\nunavailable")
        if self._details_status_var is not None:
            self._details_status_var.set(friendly)
        self._log("WARN", f"Game details unavailable for {path.name}: {friendly}")

    # ----------------------------------------------------------- actions
    def _show_record_details(self, record: _Record) -> None:
        self._activate_details_record(record)

    def _refresh_selected_details(self) -> None:
        if self._details_record is None:
            return
        self._activate_details_record(self._details_record, force=True)

    def _current_details_path(self) -> Path | None:
        return self._details_record.view.source if self._details_record is not None else None

    def _details_show_in_explorer(self) -> None:
        path = self._current_details_path()
        if path is not None:
            self._show_in_explorer(path)

    def _details_open_folder(self) -> None:
        path = self._current_details_path()
        if path is not None:
            self._open_folder(path)

    def _details_run_diagnostics(self) -> None:
        path = self._current_details_path()
        if path is not None:
            self._run_diagnostics(path)

    def _copy_details_json(self) -> None:
        if self._details_json is None:
            return
        text = self._details_json.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set("param.json copied to clipboard")


def main() -> None:
    app = RenamerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
