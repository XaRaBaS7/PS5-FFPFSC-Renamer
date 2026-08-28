from __future__ import annotations

import inspect

from ps5_ffpfsc_renamer import desktop
from ps5_ffpfsc_renamer.ui import ps5_ftp_workspace


def test_desktop_installs_ps5_ftp_workspace_after_canonical_ui() -> None:
    source = inspect.getsource(desktop.RenamerApp.__init__)
    assert "install_ps5_ftp_workspace(self)" in source
    assert "after_idle" in source


def test_remote_workspace_exposes_local_and_ftp_sidebar_modes() -> None:
    source = inspect.getsource(ps5_ftp_workspace._RemoteWorkspaceController)
    assert '"▣  Local Library"' in source
    assert '"⇄  PS5 FTP"' in source
    assert '"Discover PS5"' in source
    assert '"PS5 Explorer"' in source
    assert '"Find .ffpfsc"' in source
    assert '"Rename selected .ffpfsc..."' in source


def test_remote_workspace_keeps_password_session_only_and_mentions_etaHEN_default() -> None:
    source = inspect.getsource(ps5_ftp_workspace._RemoteWorkspaceController._build_remote_workspace)
    assert 'show="•"' in source
    assert "credentials remain in memory only" in source
    assert "1337" in source
