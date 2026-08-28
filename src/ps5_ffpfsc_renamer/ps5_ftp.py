from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import ftplib
import ipaddress
import os
import posixpath
import re
import socket
import subprocess
import threading
from typing import Iterable


DEFAULT_FTP_PORT = 1337
DEFAULT_FTP_USER = "anonymous"
MAX_DISCOVERY_HOSTS = 1022
MAX_REMOTE_SCAN_DIRECTORIES = 4096
RFC1918_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
SHADOWMOUNT_PFSC_MOUNT_BASE = "/mnt/shadowmnt/pfsc"
SHADOWMOUNT_REFERENCE_FILES = (
    "/data/shadowmount/config.ini",
    "/data/shadowmount/autotune.ini",
    "/data/shadowmount/manual.lst",
    "/data/shadowmount/manual.status",
)


@dataclass(frozen=True, slots=True)
class RemoteEntry:
    name: str
    path: str
    is_dir: bool
    size: int | None = None


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    host: str
    port: int
    banner: str = ""

    @property
    def label(self) -> str:
        marker = "PS5 FTP candidate" if self.port == DEFAULT_FTP_PORT else "FTP candidate"
        return f"{self.host}:{self.port} — {marker}"


class ShadowMountReferenceError(RuntimeError):
    def __init__(self, references: Iterable[str]) -> None:
        self.references = tuple(references)
        joined = ", ".join(self.references)
        super().__init__(
            "Remote rename blocked because the current filename/path is referenced by "
            f"ShadowMount configuration: {joined}"
        )


class ShadowMountMountedError(RuntimeError):
    def __init__(self, source_path: str, mount_point: str) -> None:
        self.source_path = source_path
        self.mount_point = mount_point
        super().__init__(
            "Remote rename blocked because the .ffpfsc currently appears to be mounted by "
            f"ShadowMountPlus at {mount_point}. Unmount/stop the game image, then retry."
        )


def normalize_remote_path(path: str) -> str:
    text = (path or "/").strip().replace("\\", "/")
    if not text.startswith("/"):
        text = "/" + text
    normalized = posixpath.normpath(text)
    return "/" if normalized in {"", "."} else normalized


def validate_remote_ffpfsc_rename(source_path: str, new_name: str) -> tuple[str, str]:
    source = normalize_remote_path(source_path)
    original_name = posixpath.basename(source)
    proposed = new_name.strip()

    if not original_name.lower().endswith(".ffpfsc"):
        raise ValueError("Only .ffpfsc files can be renamed in PS5 FTP mode.")
    if not proposed or proposed in {".", ".."}:
        raise ValueError("The new filename is empty or invalid.")
    if "/" in proposed or "\\" in proposed or posixpath.basename(proposed) != proposed:
        raise ValueError("The new filename must not contain a folder path.")
    if not proposed.lower().endswith(".ffpfsc"):
        raise ValueError("The .ffpfsc extension must be preserved.")
    if any(ord(char) < 32 for char in proposed):
        raise ValueError("The filename contains control characters.")

    destination = normalize_remote_path(posixpath.join(posixpath.dirname(source), proposed))
    if destination == source:
        raise ValueError("The new filename is identical to the current filename.")
    return source, destination


def _fnv1a32(text: str) -> int:
    value = 2166136261
    for byte in text.encode("utf-8"):
        value ^= byte
        value = (value * 16777619) & 0xFFFFFFFF
    return value


def shadowmount_pfsc_mount_point(source_path: str) -> str:
    """Return the mount point ShadowMountPlus derives for an outer .ffpfsc path."""
    source = normalize_remote_path(source_path)
    name = posixpath.basename(source)
    base = name.rsplit(".", 1)[0] if "." in name else name
    return f"{SHADOWMOUNT_PFSC_MOUNT_BASE}/{base}_{_fnv1a32(source):08x}"


def _parse_unix_list_line(line: str, root: str) -> RemoteEntry | None:
    """Parse the LIST format used by PS5 ftpsrv variants that lack MLSD/NLST."""
    parts = line.rstrip("\r\n").split(maxsplit=8)
    if len(parts) < 9:
        return None
    mode = parts[0]
    name = parts[8]
    if name in {"", ".", ".."}:
        return None
    if mode.startswith("l") and " -> " in name:
        name = name.split(" -> ", 1)[0]
    is_dir = mode.startswith("d")
    size: int | None = None
    if not is_dir:
        try:
            size = int(parts[4])
        except ValueError:
            size = None
    return RemoteEntry(
        name=name,
        path=normalize_remote_path(posixpath.join(root, name)),
        is_dir=is_dir,
        size=size,
    )


def _private_ipv4(value: str) -> str | None:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    if address.version != 4 or address.is_loopback or address.is_link_local:
        return None
    if not any(address in network for network in RFC1918_NETWORKS):
        return None
    return str(address)


def local_private_ipv4_addresses() -> tuple[str, ...]:
    """Return local RFC1918 IPv4 addresses without sending network payloads."""
    found: set[str] = set()

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            candidate = _private_ipv4(info[4][0])
            if candidate:
                found.add(candidate)
    except OSError:
        pass

    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))
            candidate = _private_ipv4(probe.getsockname()[0])
            if candidate:
                found.add(candidate)
        finally:
            probe.close()
    except OSError:
        pass

    if os.name == "nt":
        try:
            output = subprocess.check_output(
                ["ipconfig"],
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=3,
            )
        except (OSError, subprocess.SubprocessError):
            output = ""
        for value in re.findall(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)", output):
            candidate = _private_ipv4(value)
            if candidate:
                found.add(candidate)

    return tuple(sorted(found, key=ipaddress.ip_address))


def discovery_hosts(
    local_addresses: Iterable[str] | None = None,
    *,
    max_hosts: int = MAX_DISCOVERY_HOSTS,
) -> tuple[str, ...]:
    """Build a bounded set of /24 LAN/Wi-Fi targets from local RFC1918 IPs."""
    addresses = tuple(local_addresses or local_private_ipv4_addresses())
    local_set = {value for value in addresses if _private_ipv4(value)}
    targets: list[str] = []
    seen: set[str] = set()

    for value in addresses:
        candidate = _private_ipv4(value)
        if not candidate:
            continue
        network = ipaddress.ip_network(f"{candidate}/24", strict=False)
        for host in network.hosts():
            text = str(host)
            if text in local_set or text in seen:
                continue
            seen.add(text)
            targets.append(text)
            if len(targets) >= max_hosts:
                return tuple(targets)
    return tuple(targets)


def _probe_ftp(host: str, port: int, timeout: float) -> DiscoveryCandidate | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        if sock.connect_ex((host, port)) != 0:
            return None
        banner = ""
        try:
            payload = sock.recv(512)
            banner = payload.decode("utf-8", errors="replace").strip()
        except OSError:
            pass
        return DiscoveryCandidate(host=host, port=port, banner=banner)
    except OSError:
        return None
    finally:
        sock.close()


def discover_ps5_ftp(
    *,
    port: int = DEFAULT_FTP_PORT,
    timeout: float = 0.35,
    workers: int = 64,
    local_addresses: Iterable[str] | None = None,
    stop_event: threading.Event | None = None,
) -> list[DiscoveryCandidate]:
    """Scan only bounded RFC1918 /24 LAN/Wi-Fi ranges for the selected FTP port."""
    if not 1 <= int(port) <= 65535:
        raise ValueError("FTP port must be between 1 and 65535.")

    targets = discovery_hosts(local_addresses)
    results: list[DiscoveryCandidate] = []
    stop = stop_event or threading.Event()

    with ThreadPoolExecutor(max_workers=max(1, min(int(workers), 96))) as pool:
        futures = {
            pool.submit(_probe_ftp, host, int(port), float(timeout)): host
            for host in targets
            if not stop.is_set()
        }
        for future in as_completed(futures):
            if stop.is_set():
                break
            try:
                candidate = future.result()
            except OSError:
                candidate = None
            if candidate is not None:
                results.append(candidate)

    return sorted(results, key=lambda item: ipaddress.ip_address(item.host))


class PS5FtpClient:
    """Small, conservative FTP client used by the PS5 remote workspace."""

    def __init__(self, ftp: ftplib.FTP | None = None) -> None:
        self.ftp = ftp or ftplib.FTP()
        self.host = ""
        self.port = DEFAULT_FTP_PORT
        self.connected = False

    def connect(
        self,
        host: str,
        *,
        port: int = DEFAULT_FTP_PORT,
        username: str = DEFAULT_FTP_USER,
        password: str = "",
        timeout: float = 6.0,
    ) -> str:
        host = host.strip()
        if not host:
            raise ValueError("PS5 IP / host is required.")
        port = int(port)
        if not 1 <= port <= 65535:
            raise ValueError("FTP port must be between 1 and 65535.")

        try:
            welcome = self.ftp.connect(host=host, port=port, timeout=timeout)
            self.ftp.login(user=username or DEFAULT_FTP_USER, passwd=password)
            self.ftp.set_pasv(True)
        except (OSError, EOFError, ftplib.Error):
            try:
                self.ftp.close()
            finally:
                self.connected = False
            raise
        self.host = host
        self.port = port
        self.connected = True
        return welcome or ""

    def close(self) -> None:
        try:
            if self.connected:
                try:
                    self.ftp.quit()
                except (OSError, EOFError, ftplib.Error):
                    self.ftp.close()
        finally:
            self.connected = False

    def _require_connection(self) -> None:
        if not self.connected:
            raise ConnectionError("PS5 FTP is not connected.")

    def _is_directory(self, path: str) -> bool:
        current = None
        try:
            current = self.ftp.pwd()
            self.ftp.cwd(path)
            return True
        except ftplib.Error:
            return False
        finally:
            if current is not None:
                try:
                    self.ftp.cwd(current)
                except ftplib.Error:
                    pass

    def exists(self, path: str) -> bool:
        self._require_connection()
        path = normalize_remote_path(path)
        try:
            self.ftp.voidcmd("TYPE I")
        except ftplib.Error:
            pass
        try:
            if self.ftp.size(path) is not None:
                return True
        except ftplib.Error:
            pass
        return self._is_directory(path)

    def _list_dir_via_list(self, root: str) -> list[RemoteEntry]:
        lines: list[str] = []
        self.ftp.retrlines(f"LIST {root}", lines.append)
        entries: list[RemoteEntry] = []
        for line in lines:
            parsed = _parse_unix_list_line(line, root)
            if parsed is not None:
                entries.append(parsed)
        return entries

    def list_dir(self, path: str = "/") -> list[RemoteEntry]:
        self._require_connection()
        root = normalize_remote_path(path)
        entries: list[RemoteEntry] = []

        try:
            for name, facts in self.ftp.mlsd(root):
                if name in {".", ".."}:
                    continue
                kind = facts.get("type", "")
                is_dir = kind in {"dir", "cdir", "pdir"}
                if kind in {"cdir", "pdir"}:
                    continue
                size = None
                if not is_dir:
                    try:
                        size = int(facts.get("size", ""))
                    except (TypeError, ValueError):
                        size = None
                entries.append(
                    RemoteEntry(
                        name=name,
                        path=normalize_remote_path(posixpath.join(root, name)),
                        is_dir=is_dir,
                        size=size,
                    )
                )
        except (AttributeError, ftplib.Error):
            # etaHEN's integrated FTP supports MLSD/NLST, but the standalone
            # ps5-payload-dev/etaHEN ftpsrv variants can expose LIST only.
            # LIST keeps the explorer usable on both implementations.
            entries = self._list_dir_via_list(root)

        entries.sort(key=lambda item: (not item.is_dir, item.name.casefold()))
        return entries

    def find_ffpfsc(
        self,
        root: str,
        *,
        recursive: bool = True,
        max_results: int = 10000,
        max_directories: int = MAX_REMOTE_SCAN_DIRECTORIES,
    ) -> list[RemoteEntry]:
        self._require_connection()
        start = normalize_remote_path(root)
        pending = [start]
        seen: set[str] = set()
        results: list[RemoteEntry] = []

        while pending:
            current = pending.pop()
            if current in seen:
                continue
            if len(seen) >= max_directories:
                raise RuntimeError(
                    f"Remote scan stopped after {max_directories} directories to avoid an unbounded traversal."
                )
            seen.add(current)
            try:
                current_entries = self.list_dir(current)
            except (OSError, ftplib.Error):
                if current == start:
                    raise
                continue
            for entry in current_entries:
                if entry.is_dir:
                    if recursive:
                        pending.append(entry.path)
                    continue
                if entry.name.lower().endswith(".ffpfsc"):
                    results.append(entry)
                    if len(results) >= max_results:
                        return sorted(results, key=lambda item: item.path.casefold())
        return sorted(results, key=lambda item: item.path.casefold())

    def read_text(self, path: str, *, max_bytes: int = 1024 * 1024) -> str:
        self._require_connection()
        remote_path = normalize_remote_path(path)
        try:
            remote_size = self.ftp.size(remote_path)
        except ftplib.Error:
            remote_size = None
        if remote_size is not None and remote_size > max_bytes:
            raise ValueError(f"Remote text file exceeds {max_bytes} bytes.")

        chunks: list[bytes] = []
        total = 0

        class _LimitReached(Exception):
            pass

        def collect(chunk: bytes) -> None:
            nonlocal total
            total += len(chunk)
            if total > max_bytes:
                raise _LimitReached
            chunks.append(chunk)

        try:
            self.ftp.retrbinary(f"RETR {remote_path}", collect, blocksize=16384)
        except _LimitReached as exc:
            raise ValueError(f"Remote text file exceeds {max_bytes} bytes.") from exc
        return b"".join(chunks).decode("utf-8", errors="replace")

    def shadowmount_references(self, source_path: str) -> tuple[str, ...]:
        self._require_connection()
        source = normalize_remote_path(source_path)
        basename = posixpath.basename(source)
        matches: list[str] = []
        for config_path in SHADOWMOUNT_REFERENCE_FILES:
            try:
                content = self.read_text(config_path)
            except (OSError, ValueError, ftplib.Error):
                continue
            if source in content or basename in content:
                matches.append(config_path)
        return tuple(matches)

    def shadowmount_mount_point(self, source_path: str) -> str:
        return shadowmount_pfsc_mount_point(source_path)

    def is_shadowmount_mounted(self, source_path: str) -> bool:
        self._require_connection()
        return self.exists(self.shadowmount_mount_point(source_path))

    def rename_ffpfsc(
        self,
        source_path: str,
        new_name: str,
        *,
        protect_shadowmount_references: bool = True,
    ) -> str:
        self._require_connection()
        source, destination = validate_remote_ffpfsc_rename(source_path, new_name)

        if not self.exists(source):
            raise FileNotFoundError(f"Remote source no longer exists: {source}")
        if self.exists(destination):
            raise FileExistsError(f"Remote destination already exists: {destination}")

        if protect_shadowmount_references:
            mount_point = self.shadowmount_mount_point(source)
            if self.exists(mount_point):
                raise ShadowMountMountedError(source, mount_point)
            references = self.shadowmount_references(source)
            if references:
                raise ShadowMountReferenceError(references)

        self.ftp.rename(source, destination)

        if self.exists(source):
            raise RuntimeError("FTP rename returned success but the old path still exists.")
        if not self.exists(destination):
            raise RuntimeError("FTP rename returned success but the new path cannot be verified.")
        return destination
