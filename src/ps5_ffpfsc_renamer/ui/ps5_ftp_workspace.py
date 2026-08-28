from __future__ import annotations

import posixpath
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from ..ps5_ftp import (
    DEFAULT_FTP_PORT,
    DEFAULT_FTP_USER,
    DiscoveryCandidate,
    PS5FtpClient,
    RemoteEntry,
    ShadowMountReferenceError,
    discover_ps5_ftp,
    normalize_remote_path,
)
from ..theme import COLORS


def _widget_text(widget: tk.Misc) -> str:
    try:
        return str(widget.cget("text"))
    except (AttributeError, tk.TclError):
        return ""


def _format_size(value: int | None) -> str:
    if value is None:
        return ""
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024.0 or unit == "TB":
            return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024.0
    return ""


class _RemoteWorkspaceController:
    def __init__(self, app: tk.Tk, shell: ttk.Frame, sidebar: tk.Frame, local_content: ttk.Frame) -> None:
        self.app = app
        self.shell = shell
        self.sidebar = sidebar
        self.local_content = local_content
        self.remote_content: ttk.Frame | None = None
        self.client: PS5FtpClient | None = None
        self.entries: dict[str, RemoteEntry] = {}
        self.busy = False
        self.mode = "local"

        self.host_var = tk.StringVar(master=app)
        self.port_var = tk.StringVar(master=app, value=str(DEFAULT_FTP_PORT))
        self.user_var = tk.StringVar(master=app, value=DEFAULT_FTP_USER)
        self.password_var = tk.StringVar(master=app)
        self.path_var = tk.StringVar(master=app, value="/")
        self.remote_status_var = tk.StringVar(master=app, value="● Disconnected")
        self.remote_note_var = tk.StringVar(
            master=app,
            value="Connect to the PS5 FTP service, browse the remote filesystem, then choose the .ffpfsc library folder.",
        )
        self.library_root_var = tk.StringVar(master=app, value="No remote library selected")

        self._local_button_parts: tuple[tk.Widget, ...] = ()
        self._ftp_button_parts: tuple[tk.Widget, ...] = ()
        self.tree: ttk.Treeview | None = None
        self.connect_button: ttk.Button | None = None
        self.disconnect_button: ttk.Button | None = None
        self.refresh_button: ttk.Button | None = None
        self.find_button: ttk.Button | None = None
        self.rename_button: ttk.Button | None = None

        self._install_sidebar_switcher()
        self._build_remote_workspace()
        self._update_sidebar_state()

    def _install_sidebar_switcher(self) -> None:
        engine_heading: tk.Widget | None = None
        old_library: tk.Widget | None = None
        for child in self.sidebar.winfo_children():
            if _widget_text(child) == "ENGINE":
                engine_heading = child
                break
        for child in self.sidebar.winfo_children():
            if not isinstance(child, tk.Frame):
                continue
            texts = {_widget_text(grandchild).strip() for grandchild in child.winfo_children()}
            if any("Library" in value for value in texts):
                old_library = child
                break
        if old_library is not None:
            try:
                old_library.destroy()
            except tk.TclError:
                pass

        nav = tk.Frame(self.sidebar, bg=COLORS["sidebar"], bd=0, highlightthickness=0)
        pack_options: dict[str, object] = {"fill": "x"}
        if engine_heading is not None:
            pack_options["before"] = engine_heading
        nav.pack(**pack_options)
        self._local_button_parts = self._workspace_button(nav, "▣  Local Library", lambda: self.show("local"))
        self._ftp_button_parts = self._workspace_button(nav, "⇄  PS5 FTP", lambda: self.show("ftp"))

    def _workspace_button(self, parent: tk.Frame, text: str, command: Callable[[], None]) -> tuple[tk.Widget, ...]:
        row = tk.Frame(parent, bg=COLORS["sidebar"], height=42, cursor="hand2")
        row.pack(fill="x")
        row.pack_propagate(False)
        marker = tk.Frame(row, bg=COLORS["sidebar"], width=3, cursor="hand2")
        marker.pack(side="left", fill="y")
        label = tk.Label(
            row,
            text=f"  {text}",
            bg=COLORS["sidebar"],
            fg=COLORS["text_soft"],
            font=("Segoe UI", 10, "bold"),
            anchor="w",
            cursor="hand2",
        )
        label.pack(side="left", fill="both", expand=True, padx=(10, 0))
        for widget in (row, marker, label):
            widget.bind("<Button-1>", lambda _event, action=command: action())
        return row, marker, label

    def _style_workspace_button(self, parts: tuple[tk.Widget, ...], active: bool) -> None:
        if len(parts) != 3:
            return
        row, marker, label = parts
        background = COLORS["accent_soft"] if active else COLORS["sidebar"]
        foreground = COLORS["accent_hover"] if active else COLORS["text_soft"]
        try:
            row.configure(bg=background)
            marker.configure(bg=COLORS["accent"] if active else COLORS["sidebar"])
            label.configure(bg=background, fg=foreground)
        except tk.TclError:
            pass

    def _update_sidebar_state(self) -> None:
        self._style_workspace_button(self._local_button_parts, self.mode == "local")
        self._style_workspace_button(self._ftp_button_parts, self.mode == "ftp")

    def show(self, mode: str) -> None:
        if mode not in {"local", "ftp"} or self.remote_content is None:
            return
        try:
            if mode == "ftp":
                self.local_content.pack_forget()
                if not self.remote_content.winfo_manager():
                    self.remote_content.pack(side="left", fill="both", expand=True)
            else:
                self.remote_content.pack_forget()
                if not self.local_content.winfo_manager():
                    self.local_content.pack(side="left", fill="both", expand=True)
        except tk.TclError:
            return
        self.mode = mode
        self._update_sidebar_state()

    def _build_remote_workspace(self) -> None:
        content = ttk.Frame(self.shell, padding=(24, 20, 24, 18))
        self.remote_content = content

        header = ttk.Frame(content)
        header.pack(fill="x")
        ttk.Label(header, text="PS5 FTP Library", style="Title.TLabel").pack(side="left")
        status = tk.Label(
            header,
            textvariable=self.remote_status_var,
            bg=COLORS["bg"],
            fg=COLORS["danger"],
            font=("Segoe UI", 9, "bold"),
            anchor="e",
        )
        status.pack(side="right")
        self._status_label = status
        ttk.Label(
            content,
            text="Browse and organize .ffpfsc files directly on the PS5 FTP filesystem.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 14))

        connection = ttk.Frame(content, style="Card.TFrame", padding=14)
        connection.pack(fill="x")
        connection.columnconfigure(1, weight=1)
        connection.columnconfigure(5, weight=1)
        labels = (("PS5 IP / host", 0), ("Port", 2), ("Username", 4), ("Password", 6))
        for text, column in labels:
            ttk.Label(connection, text=text, style="CardMuted.TLabel").grid(row=0, column=column, sticky="w", padx=(0, 6))
        ttk.Entry(connection, textvariable=self.host_var).grid(row=0, column=1, sticky="ew", padx=(0, 10))
        ttk.Entry(connection, textvariable=self.port_var, width=7).grid(row=0, column=3, sticky="w", padx=(0, 14))
        ttk.Entry(connection, textvariable=self.user_var, width=18).grid(row=0, column=5, sticky="ew", padx=(0, 10))
        ttk.Entry(connection, textvariable=self.password_var, show="•", width=16).grid(row=0, column=7, sticky="ew")

        actions = ttk.Frame(connection, style="Card.TFrame")
        actions.grid(row=1, column=0, columnspan=8, sticky="ew", pady=(12, 0))
        ttk.Button(actions, text="Discover PS5", style="Secondary.TButton", command=self.discover).pack(side="left")
        self.connect_button = ttk.Button(actions, text="Connect", style="Primary.TButton", command=self.connect)
        self.connect_button.pack(side="left", padx=(7, 0))
        self.disconnect_button = ttk.Button(
            actions, text="Disconnect", style="Secondary.TButton", command=self.disconnect, state="disabled"
        )
        self.disconnect_button.pack(side="left", padx=(7, 0))
        ttk.Label(
            actions,
            text="etaHEN default FTP port: 1337 • credentials remain in memory only",
            style="CardMuted.TLabel",
        ).pack(side="right")

        browser = ttk.Frame(content, style="Card.TFrame", padding=14)
        browser.pack(fill="both", expand=True, pady=(12, 0))
        path_row = ttk.Frame(browser, style="Card.TFrame")
        path_row.pack(fill="x")
        ttk.Label(path_row, text="Remote path", style="CardMuted.TLabel").pack(side="left")
        ttk.Entry(path_row, textvariable=self.path_var).pack(side="left", fill="x", expand=True, padx=(8, 7))
        ttk.Button(path_row, text="Up", style="Secondary.TButton", command=self.up).pack(side="left")
        self.refresh_button = ttk.Button(
            path_row, text="Refresh", style="Secondary.TButton", command=self.refresh, state="disabled"
        )
        self.refresh_button.pack(side="left", padx=(7, 0))

        remote_header = ttk.Frame(browser, style="Card.TFrame")
        remote_header.pack(fill="x", pady=(10, 6))
        ttk.Label(remote_header, text="PS5 Explorer", style="CardTitle.TLabel").pack(side="left")
        ttk.Label(remote_header, textvariable=self.library_root_var, style="CardMuted.TLabel").pack(side="right")

        table_wrap = ttk.Frame(browser, style="Card.TFrame")
        table_wrap.pack(fill="both", expand=True)
        tree = ttk.Treeview(table_wrap, columns=("type", "size", "path"), show="tree headings", selectmode="browse", height=18)
        tree.heading("#0", text="Name")
        tree.heading("type", text="Type")
        tree.heading("size", text="Size")
        tree.heading("path", text="Remote path")
        tree.column("#0", width=300, minwidth=180, stretch=True)
        tree.column("type", width=100, minwidth=80, stretch=False, anchor="center")
        tree.column("size", width=110, minwidth=90, stretch=False, anchor="e")
        tree.column("path", width=460, minwidth=220, stretch=True)
        yscroll = ttk.Scrollbar(table_wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)
        tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")
        tree.bind("<Double-1>", self._double_click)
        tree.bind("<<TreeviewSelect>>", lambda _event: self._refresh_rename_state(), add="+")
        self.tree = tree

        commands = ttk.Frame(browser, style="Card.TFrame")
        commands.pack(fill="x", pady=(9, 0))
        ttk.Button(
            commands,
            text="Use this folder as PS5 library",
            style="Secondary.TButton",
            command=self.use_current_folder,
        ).pack(side="left")
        self.find_button = ttk.Button(
            commands, text="Find .ffpfsc", style="Secondary.TButton", command=self.find_ffpfsc, state="disabled"
        )
        self.find_button.pack(side="left", padx=(7, 0))
        self.rename_button = ttk.Button(
            commands,
            text="Rename selected .ffpfsc...",
            style="RenamePrimary.TButton",
            command=self.rename_selected,
            state="disabled",
        )
        self.rename_button.pack(side="right")

        tk.Label(
            content,
            textvariable=self.remote_note_var,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 8),
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(8, 0))

    def _set_connected(self, connected: bool) -> None:
        try:
            if connected and self.client is not None:
                self.remote_status_var.set(f"● Connected • {self.client.host}:{self.client.port}")
                self._status_label.configure(fg=COLORS["success"])
            else:
                self.remote_status_var.set("● Disconnected")
                self._status_label.configure(fg=COLORS["danger"])
        except tk.TclError:
            return
        for button in (self.refresh_button, self.find_button):
            if button is not None:
                button.state(["!disabled"] if connected and not self.busy else ["disabled"])
        if self.disconnect_button is not None:
            self.disconnect_button.state(["!disabled"] if connected and not self.busy else ["disabled"])
        if self.connect_button is not None:
            self.connect_button.state(["disabled"] if connected or self.busy else ["!disabled"])
        self._refresh_rename_state()

    def _refresh_rename_state(self) -> None:
        if self.rename_button is None or self.tree is None:
            return
        enabled = False
        if self.client is not None and self.client.connected and not self.busy:
            selected = self.tree.selection()
            if selected:
                entry = self.entries.get(selected[0])
                enabled = bool(entry and not entry.is_dir and entry.name.lower().endswith(".ffpfsc"))
        self.rename_button.state(["!disabled"] if enabled else ["disabled"])

    def _run(self, label: str, action: Callable[[], Any], success: Callable[[Any], None]) -> None:
        if self.busy:
            return
        self.busy = True
        self.remote_note_var.set(label)
        self._set_connected(bool(self.client and self.client.connected))

        def worker() -> None:
            try:
                result = action()
            except Exception as exc:
                self.app.after(0, lambda error=exc: self._task_failed(error))
            else:
                self.app.after(0, lambda value=result: self._task_succeeded(success, value))

        threading.Thread(target=worker, daemon=True, name="ps5-ftp-task").start()

    def _task_succeeded(self, success: Callable[[Any], None], value: Any) -> None:
        self.busy = False
        success(value)
        self._set_connected(bool(self.client and self.client.connected))

    def _task_failed(self, error: BaseException) -> None:
        self.busy = False
        self.remote_note_var.set(f"{type(error).__name__}: {error}")
        if isinstance(error, ShadowMountReferenceError):
            messagebox.showwarning(
                "Remote rename blocked",
                f"{error}\n\nThe file was not renamed. This protection prevents stale exact-path references.",
                parent=self.app,
            )
        else:
            messagebox.showerror("PS5 FTP", f"{type(error).__name__}: {error}", parent=self.app)
        self._set_connected(bool(self.client and self.client.connected))

    def _render_entries(self, entries: list[RemoteEntry]) -> None:
        if self.tree is None:
            return
        self.tree.delete(*self.tree.get_children())
        self.entries.clear()
        for index, entry in enumerate(entries):
            iid = f"remote-{index}"
            self.entries[iid] = entry
            self.tree.insert(
                "",
                "end",
                iid=iid,
                text=("📁 " if entry.is_dir else "📄 ") + entry.name,
                values=(
                    "Folder" if entry.is_dir else "FFPFSC" if entry.name.lower().endswith(".ffpfsc") else "File",
                    _format_size(entry.size),
                    entry.path,
                ),
            )
        self._refresh_rename_state()

    def connect(self) -> None:
        host = self.host_var.get().strip()
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("PS5 FTP", "FTP port must be a number.", parent=self.app)
            return
        username = self.user_var.get().strip() or DEFAULT_FTP_USER
        password = self.password_var.get()

        def action() -> tuple[PS5FtpClient, str]:
            client = PS5FtpClient()
            welcome = client.connect(host, port=port, username=username, password=password)
            return client, welcome

        def success(result: tuple[PS5FtpClient, str]) -> None:
            old = self.client
            self.client, welcome = result
            if old is not None:
                old.close()
            self.remote_note_var.set(f"Connected. {welcome.strip()}" if welcome.strip() else "Connected to PS5 FTP.")
            self.path_var.set("/")
            self.refresh()

        self._run("Connecting to PS5 FTP...", action, success)

    def disconnect(self) -> None:
        client = self.client
        self.client = None
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        self.remote_note_var.set("Disconnected from PS5 FTP.")
        self.entries.clear()
        if self.tree is not None:
            self.tree.delete(*self.tree.get_children())
        self._set_connected(False)

    def refresh(self) -> None:
        client = self.client
        if client is None or not client.connected:
            return
        path = normalize_remote_path(self.path_var.get())

        def success(entries: list[RemoteEntry]) -> None:
            self.path_var.set(path)
            self._render_entries(entries)
            self.remote_note_var.set(f"{len(entries)} item(s) in {path}")

        self._run(f"Reading {path}...", lambda: client.list_dir(path), success)

    def up(self) -> None:
        current = normalize_remote_path(self.path_var.get())
        self.path_var.set(posixpath.dirname(current.rstrip("/")) or "/")
        if self.client is not None and self.client.connected:
            self.refresh()

    def _double_click(self, _event=None) -> None:
        if self.tree is None:
            return
        selected = self.tree.selection()
        if not selected:
            return
        entry = self.entries.get(selected[0])
        if entry is None or not entry.is_dir:
            return
        self.path_var.set(entry.path)
        self.refresh()

    def use_current_folder(self) -> None:
        path = normalize_remote_path(self.path_var.get())
        self.library_root_var.set(f"Remote library: {path}")
        self.remote_note_var.set(f"{path} selected as the PS5 .ffpfsc library root. Use Find .ffpfsc to enumerate it.")

    def find_ffpfsc(self) -> None:
        client = self.client
        if client is None or not client.connected:
            return
        root = normalize_remote_path(self.path_var.get())

        def success(entries: list[RemoteEntry]) -> None:
            self._render_entries(entries)
            self.library_root_var.set(f"Remote library: {root}")
            self.remote_note_var.set(
                f"Found {len(entries)} .ffpfsc file(s) below {root}. Remote metadata extraction will be added on top of this bounded FTP workspace."
            )

        self._run(
            f"Scanning {root} recursively for .ffpfsc files...",
            lambda: client.find_ffpfsc(root, recursive=True),
            success,
        )

    def rename_selected(self) -> None:
        client = self.client
        if client is None or not client.connected or self.tree is None:
            return
        selected = self.tree.selection()
        if not selected:
            return
        entry = self.entries.get(selected[0])
        if entry is None or entry.is_dir or not entry.name.lower().endswith(".ffpfsc"):
            return
        new_name = simpledialog.askstring(
            "Rename remote .ffpfsc",
            "New filename (the .ffpfsc extension is required):",
            initialvalue=entry.name,
            parent=self.app,
        )
        if new_name is None:
            return
        new_name = new_name.strip()
        if not messagebox.askyesno(
            "Confirm remote rename",
            f"PS5: {client.host}:{client.port}\n\nFrom:\n{entry.path}\n\n"
            f"To:\n{posixpath.join(posixpath.dirname(entry.path), new_name)}\n\n"
            "The utility will refuse collisions and will block the rename if known ShadowMount exact-path references are detected.",
            parent=self.app,
        ):
            return

        def success(destination: str) -> None:
            self.remote_note_var.set(f"Remote rename verified: {destination}")
            self.refresh()

        self._run(
            f"Preflighting and renaming {entry.name}...",
            lambda: client.rename_ffpfsc(entry.path, new_name),
            success,
        )

    def discover(self) -> None:
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Discover PS5", "FTP port must be a number.", parent=self.app)
            return

        def success(candidates: list[DiscoveryCandidate]) -> None:
            self.remote_note_var.set(f"Discovery complete: {len(candidates)} FTP candidate(s) found on port {port}.")
            self._show_discovery_results(candidates)

        self._run(
            "Scanning private LAN / Wi-Fi /24 networks for the selected FTP port...",
            lambda: discover_ps5_ftp(port=port),
            success,
        )

    def _show_discovery_results(self, candidates: list[DiscoveryCandidate]) -> None:
        dialog = tk.Toplevel(self.app)
        dialog.title("Discover PS5")
        dialog.geometry("640x360")
        dialog.minsize(540, 300)
        dialog.transient(self.app)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="PS5 FTP discovery", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Only private local /24 networks were scanned. Select a candidate to copy its IP.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 10))
        tree = ttk.Treeview(frame, columns=("port", "banner"), show="headings", height=10)
        tree.heading("port", text="Address / port")
        tree.heading("banner", text="FTP banner")
        tree.column("port", width=180, anchor="w")
        tree.column("banner", width=390, anchor="w")
        tree.pack(fill="both", expand=True)
        for index, candidate in enumerate(candidates):
            tree.insert("", "end", iid=str(index), values=(f"{candidate.host}:{candidate.port}", candidate.banner or "(no banner)"))
        if not candidates:
            tree.insert("", "end", values=("No candidates found", "Check that FTP is enabled on the PS5."))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(10, 0))

        def use_selected() -> None:
            selected = tree.selection()
            if not selected:
                return
            try:
                candidate = candidates[int(selected[0])]
            except (IndexError, ValueError):
                return
            self.host_var.set(candidate.host)
            self.port_var.set(str(candidate.port))
            dialog.destroy()
            self.remote_note_var.set(f"Selected {candidate.host}:{candidate.port}. Enter credentials if required, then Connect.")

        ttk.Button(buttons, text="Close", style="Secondary.TButton", command=dialog.destroy).pack(side="right")
        ttk.Button(
            buttons,
            text="Use selected",
            style="Primary.TButton",
            command=use_selected,
            state="normal" if candidates else "disabled",
        ).pack(side="right", padx=(0, 7))

    def close(self) -> None:
        client = self.client
        self.client = None
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def install_ps5_ftp_workspace(app: tk.Tk) -> _RemoteWorkspaceController | None:
    """Install Local Library / PS5 FTP workspace switching on the built desktop."""
    existing = getattr(app, "_ps5_ftp_workspace_controller", None)
    if existing is not None:
        return existing
    shell = next((child for child in app.winfo_children() if isinstance(child, ttk.Frame)), None)
    if shell is None:
        return None
    children = shell.winfo_children()
    sidebar = next((child for child in children if isinstance(child, tk.Frame)), None)
    local_content = next((child for child in children if isinstance(child, ttk.Frame)), None)
    if sidebar is None or local_content is None:
        return None
    controller = _RemoteWorkspaceController(app, shell, sidebar, local_content)
    setattr(app, "_ps5_ftp_workspace_controller", controller)

    def cleanup(event: tk.Event) -> None:
        if event.widget is app:
            controller.close()

    app.bind("<Destroy>", cleanup, add="+")
    return controller
