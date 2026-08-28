from __future__ import annotations

import ftplib

import pytest

from ps5_ffpfsc_renamer.ps5_ftp import (
    PS5FtpClient,
    ShadowMountMountedError,
    ShadowMountReferenceError,
    discovery_hosts,
    normalize_remote_path,
    shadowmount_pfsc_mount_point,
    validate_remote_ffpfsc_rename,
)


class FakeFTP:
    def __init__(self) -> None:
        self.files = {
            "/games/PPSA00001.ffpfsc": b"game",
            "/data/shadowmount/config.ini": b"",
            "/data/shadowmount/autotune.ini": b"",
            "/data/shadowmount/manual.lst": b"",
            "/data/shadowmount/manual.status": b"",
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


class ListOnlyFTP(FakeFTP):
    """Model the standalone PS5 ftpsrv variant that exposes LIST but not MLSD/NLST."""

    def mlsd(self, path: str):
        raise ftplib.error_perm("502 MLSD unsupported")

    def retrlines(self, command: str, callback):
        assert command == "LIST /games"
        for line in (
            "drwxr-xr-x 2 0 0 0 Aug 28 10:00 Folder",
            "-rw-r--r-- 1 0 0 2 Aug 28 10:00 notes.txt",
            "-rw-r--r-- 1 0 0 4 Aug 28 10:00 PPSA00001.ffpfsc",
        ):
            callback(line)
        return "226 Transfer complete"


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
    assert len(hosts) == 506


def test_remote_listing_sorts_folders_first_and_keeps_sizes() -> None:
    client, _ftp = _client()
    entries = client.list_dir("/games")
    assert [item.name for item in entries] == ["Folder", "notes.txt", "PPSA00001.ffpfsc"]
    assert entries[-1].size == 4


def test_remote_listing_falls_back_to_list_for_standalone_ftpsrv() -> None:
    client, _ftp = _client(ListOnlyFTP())
    entries = client.list_dir("/games")
    assert [item.name for item in entries] == ["Folder", "notes.txt", "PPSA00001.ffpfsc"]
    assert entries[0].is_dir is True
    assert entries[-1].size == 4


def test_shadowmount_pfsc_mount_point_matches_current_algorithm() -> None:
    assert shadowmount_pfsc_mount_point("/games/PPSA00001.ffpfsc") == (
        "/mnt/shadowmnt/pfsc/PPSA00001_74598469"
    )


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


def test_shadowmount_filename_override_in_autotune_blocks_remote_rename() -> None:
    client, ftp = _client()
    ftp.files["/data/shadowmount/autotune.ini"] = b"image_sector=PPSA00001.ffpfsc:32768\n"

    with pytest.raises(ShadowMountReferenceError) as captured:
        client.rename_ffpfsc(
            "/games/PPSA00001.ffpfsc",
            "PPSA00001 - Game.ffpfsc",
        )

    assert captured.value.references == ("/data/shadowmount/autotune.ini",)
    assert ftp.renames == []


def test_currently_mounted_shadowmount_pfsc_is_never_renamed() -> None:
    client, ftp = _client()
    mount_point = shadowmount_pfsc_mount_point("/games/PPSA00001.ffpfsc")
    ftp.dirs.add(mount_point)

    with pytest.raises(ShadowMountMountedError) as captured:
        client.rename_ffpfsc(
            "/games/PPSA00001.ffpfsc",
            "PPSA00001 - Game.ffpfsc",
        )

    assert captured.value.mount_point == mount_point
    assert ftp.renames == []
