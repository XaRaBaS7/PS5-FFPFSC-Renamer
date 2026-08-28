from __future__ import annotations

import ftplib

import pytest

from ps5_ffpfsc_renamer.ps5_ftp import (
    PS5FtpClient,
    ShadowMountReferenceError,
    discovery_hosts,
    normalize_remote_path,
    validate_remote_ffpfsc_rename,
)


class FakeFTP:
    def __init__(self) -> None:
        self.files = {
            "/games/PPSA00001.ffpfsc": b"game",
            "/data/shadowmount/config.ini": b"",
            "/data/shadowmount/manual.lst": b"",
        }
        self.dirs = {"/", "/games", "/data", "/data/shadowmount"}
        self.renames: list[tuple[str, str]] = []

    def voidcmd(self, _command: str):
        return "200 OK"

    def size(self, path: str):
        if path in self.files:
            return len(self.files[path])
        raise ftplib.error_perm("550 not a file")

    def pwd(self):
        return "/"

    def cwd(self, path: str):
        if path not in self.dirs:
            raise ftplib.error_perm("550 not a dir")
        return "250 OK"

    def retrbinary(self, command: str, callback, blocksize: int = 8192):
        assert command.startswith("RETR ")
        path = command[5:]
        if path not in self.files:
            raise ftplib.error_perm("550 missing")
        payload = self.files[path]
        for offset in range(0, len(payload), blocksize):
            callback(payload[offset : offset + blocksize])
        return "226 OK"

    def rename(self, source: str, destination: str):
        if source not in self.files:
            raise ftplib.error_perm("550 missing")
        if destination in self.files:
            raise ftplib.error_perm("550 exists")
        self.files[destination] = self.files.pop(source)
        self.renames.append((source, destination))
        return "250 OK"

    def mlsd(self, path: str):
        if path == "/games":
            yield "Folder", {"type": "dir"}
            yield "PPSA00001.ffpfsc", {"type": "file", "size": "4"}
            yield "notes.txt", {"type": "file", "size": "2"}
            return
        raise ftplib.error_perm("550 unsupported")


def _client(fake: FakeFTP | None = None) -> tuple[PS5FtpClient, FakeFTP]:
    ftp = fake or FakeFTP()
    client = PS5FtpClient(ftp)
    client.connected = True
    client.host = "192.168.1.20"
    client.port = 1337
    return client, ftp


def test_remote_path_normalization_is_posix_and_absolute() -> None:
    assert normalize_remote_path("games\\folder/../PPSA.ffpfsc") == "/games/PPSA.ffpfsc"
    assert normalize_remote_path("/") == "/"


def test_remote_rename_requires_same_folder_filename_and_ffpfsc_extension() -> None:
    source, destination = validate_remote_ffpfsc_rename(
        "/games/PPSA00001.ffpfsc",
        "PPSA00001 - Example - v1.0.ffpfsc",
    )
    assert source == "/games/PPSA00001.ffpfsc"
    assert destination == "/games/PPSA00001 - Example - v1.0.ffpfsc"

    with pytest.raises(ValueError):
        validate_remote_ffpfsc_rename(source, "../escape.ffpfsc")
    with pytest.raises(ValueError):
        validate_remote_ffpfsc_rename(source, "Example.iso")


def test_discovery_is_bounded_to_private_local_24_networks() -> None:
    hosts = discovery_hosts(["192.168.1.10", "10.4.5.20"])
    assert "192.168.1.10" not in hosts
    assert "10.4.5.20" not in hosts
    assert "192.168.1.1" in hosts
    assert "10.4.5.1" in hosts
    assert len(hosts) == 508


def test_remote_listing_sorts_folders_first_and_keeps_sizes() -> None:
    client, _ftp = _client()
    entries = client.list_dir("/games")
    assert [item.name for item in entries] == ["Folder", "notes.txt", "PPSA00001.ffpfsc"]
    assert entries[-1].size == 4


def test_remote_rename_preflights_collision_and_verifies_destination() -> None:
    client, ftp = _client()
    destination = client.rename_ffpfsc(
        "/games/PPSA00001.ffpfsc",
        "PPSA00001 - Game - v1.0.ffpfsc",
    )
    assert destination == "/games/PPSA00001 - Game - v1.0.ffpfsc"
    assert ftp.renames == [
        ("/games/PPSA00001.ffpfsc", "/games/PPSA00001 - Game - v1.0.ffpfsc")
    ]

    ftp.files["/games/Other.ffpfsc"] = b"existing"
    with pytest.raises(FileExistsError):
        client.rename_ffpfsc(destination, "Other.ffpfsc")


def test_shadowmount_exact_path_reference_blocks_remote_rename() -> None:
    client, ftp = _client()
    ftp.files["/data/shadowmount/manual.lst"] = b"/games/PPSA00001.ffpfsc\n"

    with pytest.raises(ShadowMountReferenceError) as captured:
        client.rename_ffpfsc(
            "/games/PPSA00001.ffpfsc",
            "PPSA00001 - Game.ffpfsc",
        )

    assert captured.value.references == ("/data/shadowmount/manual.lst",)
    assert ftp.renames == []
