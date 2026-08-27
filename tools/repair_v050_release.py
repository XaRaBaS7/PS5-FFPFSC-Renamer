from __future__ import annotations

import hashlib
import marshal
from pathlib import Path
import struct
import sys
import zipfile
import zlib

MAGIC = b"MEI\x0c\x0b\x0a\x0b\x0e"
EXPECTED_BASE_SHA256 = "8224ef0d0b78f9ed46205c01787fa071c98ccee46c39f9a42efa56832ff409e0"
EXE_NAME = "PS5-FFPFSC-Renamer.exe"
STARTUP_MODULE = "ps5_ffpfsc_renamer.ui.startup_preferences_mixin"
FEEDBACK_MODULE = "ps5_ffpfsc_renamer.feedback_transport"
NEW_ENDPOINT = b"https://www.youstoreinformatica.com/ffpfsc/ps5-ffpfsc-feedback.php"
OLD_ENDPOINT = b"https://www.youstoreinformatica.com/ps5-ffpfsc-feedback.php"


def _patch_exe(exe: bytes) -> bytes:
    cookie_off = exe.rfind(MAGIC)
    if cookie_off < 0:
        raise RuntimeError("PyInstaller cookie not found")
    magic, pkglen, tocpos, toclen, pyver, pylib = struct.unpack(
        "!8sIIII64s", exe[cookie_off : cookie_off + 88]
    )
    if pyver != 311:
        raise RuntimeError(f"Unexpected bundled Python version: {pyver}")
    pkgstart = cookie_off + 88 - pkglen
    toc = bytearray(exe[pkgstart + tocpos : pkgstart + tocpos + toclen])

    entries = []
    offset = 0
    while offset < len(toc):
        entry_len = struct.unpack("!I", toc[offset : offset + 4])[0]
        pos, csize, usize, flag, typecode = struct.unpack(
            "!IIIBc", toc[offset + 4 : offset + 18]
        )
        name = bytes(toc[offset + 18 : offset + entry_len]).split(b"\0", 1)[0].decode()
        entries.append((name, pos, csize, usize, flag, typecode, offset))
        offset += entry_len
    if offset != len(toc):
        raise RuntimeError("Outer TOC parse mismatch")

    pyz_entry = next(entry for entry in entries if entry[0] == "PYZ.pyz")
    if entries[-1][0] != "PYZ.pyz":
        raise RuntimeError("PYZ is not the last CArchive entry")
    _, pyz_pos, pyz_size, _, _, _, pyz_toc_offset = pyz_entry
    pyz = exe[pkgstart + pyz_pos : pkgstart + pyz_pos + pyz_size]
    if pyz[:4] != b"PYZ\0":
        raise RuntimeError("Invalid PYZ header")

    old_toc_pos = struct.unpack("!I", pyz[8:12])[0]
    pyz_toc = marshal.loads(pyz[old_toc_pos:])
    if not isinstance(pyz_toc, list):
        raise RuntimeError("Unexpected PYZ TOC")

    new_toc = []
    new_blobs = []
    cursor = 12
    startup_seen = False
    for module_name, meta in pyz_toc:
        module_type, module_offset, module_len = meta
        blob = pyz[module_offset : module_offset + module_len]
        if module_name == STARTUP_MODULE:
            raw = bytearray(zlib.decompress(blob))

            # Stop the generated runtime icon from replacing the official
            # bundled brand icon. Marshal ref 0x15 is IconSet; 0x16 is
            # apply_window_icon in this certified v0.5.0 base build.
            if raw[1489:1494] != bytes.fromhex("7216000000"):
                raise RuntimeError("Unexpected startup icon marshal layout")
            raw[1489:1494] = bytes.fromhex("7215000000")

            # The modern shell destroys the former central Options button.
            # The old startup callback then tries to configure that dead Tk
            # command. Redirect that duplicate state update to scan_button,
            # which is always live and already controlled by the superclass.
            # Ref 0xd4 = options_button; ref 0xce = scan_button.
            for patch_at in (10517, 10581):
                if raw[patch_at : patch_at + 5] != bytes.fromhex("72d4000000"):
                    raise RuntimeError("Unexpected scan-control marshal layout")
                raw[patch_at : patch_at + 5] = bytes.fromhex("72ce000000")

            code = marshal.loads(bytes(raw))
            code_type = type(code)
            found = {}

            def walk(item):
                if item.co_name in {"__init__", "_set_scan_controls"}:
                    found[item.co_name] = item
                for child in item.co_consts:
                    if isinstance(child, code_type):
                        walk(child)

            walk(code)
            if found["__init__"].co_names[19] != "IconSet":
                raise RuntimeError("Icon patch semantic verification failed")
            scan_code = found["_set_scan_controls"]
            if "scan_button" not in scan_code.co_names or "options_button" in scan_code.co_names:
                raise RuntimeError("Startup scan patch semantic verification failed")
            if "scan_button" not in scan_code.co_consts:
                raise RuntimeError("Startup scan constant patch verification failed")

            blob = zlib.compress(bytes(raw), 9)
            startup_seen = True

        new_toc.append((module_name, (module_type, cursor, len(blob))))
        new_blobs.append(blob)
        cursor += len(blob)

    if not startup_seen:
        raise RuntimeError("Startup module not found")

    new_pyz_toc = marshal.dumps(new_toc, 4)
    new_pyz = pyz[:8] + struct.pack("!I", cursor) + b"".join(new_blobs) + new_pyz_toc

    # Full PYZ integrity check plus direct feedback endpoint gate.
    rebuilt_toc_pos = struct.unpack("!I", new_pyz[8:12])[0]
    rebuilt_toc = marshal.loads(new_pyz[rebuilt_toc_pos:])
    if len(rebuilt_toc) != 287:
        raise RuntimeError(f"Expected 287 PYZ modules, got {len(rebuilt_toc)}")
    rebuilt = dict(rebuilt_toc)
    for module_name, (_, module_offset, module_len) in rebuilt_toc:
        module_raw = zlib.decompress(new_pyz[module_offset : module_offset + module_len])
        marshal.loads(module_raw)
    _, feedback_offset, feedback_len = rebuilt[FEEDBACK_MODULE]
    feedback_raw = zlib.decompress(new_pyz[feedback_offset : feedback_offset + feedback_len])
    if NEW_ENDPOINT not in feedback_raw or OLD_ENDPOINT in feedback_raw:
        raise RuntimeError("Direct /ffpfsc/ feedback endpoint verification failed")

    # PYZ is the final outer entry, so prior entry offsets remain unchanged.
    struct.pack_into("!I", toc, pyz_toc_offset + 8, len(new_pyz))
    struct.pack_into("!I", toc, pyz_toc_offset + 12, len(new_pyz))
    new_outer_toc_pos = pyz_pos + len(new_pyz)
    new_pkglen = new_outer_toc_pos + len(toc) + 88
    new_cookie = struct.pack(
        "!8sIIII64s", magic, new_pkglen, new_outer_toc_pos, len(toc), pyver, pylib
    )
    patched = exe[: pkgstart + pyz_pos] + new_pyz + bytes(toc) + new_cookie

    # Re-parse the outer archive as a final structural gate.
    new_cookie_off = patched.rfind(MAGIC)
    _, check_pkglen, check_tocpos, check_toclen, check_pyver, _ = struct.unpack(
        "!8sIIII64s", patched[new_cookie_off : new_cookie_off + 88]
    )
    check_pkgstart = new_cookie_off + 88 - check_pkglen
    if check_pkgstart != pkgstart or check_pyver != 311:
        raise RuntimeError("Rebuilt CArchive verification failed")
    check_toc = patched[
        check_pkgstart + check_tocpos : check_pkgstart + check_tocpos + check_toclen
    ]
    if b"PYZ.pyz" not in check_toc:
        raise RuntimeError("Rebuilt outer TOC lost PYZ entry")
    return patched


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: repair_v050_release.py <release-zip>", file=sys.stderr)
        return 2
    archive = Path(sys.argv[1])
    original_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    if original_sha != EXPECTED_BASE_SHA256:
        raise RuntimeError(
            "Refusing to patch an unexpected release asset: "
            f"sha256={original_sha}, expected={EXPECTED_BASE_SHA256}"
        )

    temp = archive.with_suffix(".repaired.zip")
    with zipfile.ZipFile(archive, "r") as source:
        infos = source.infolist()
        names = [info.filename for info in infos]
        roots = {name.split("/", 1)[0] for name in names}
        if "assets" in roots or "app-icon.png" in roots:
            raise RuntimeError("Release contains redundant root branding assets")
        if EXE_NAME not in names or "mkpfs-helper.exe" not in names:
            raise RuntimeError("Release executables are missing")
        exe = _patch_exe(source.read(EXE_NAME))

        with zipfile.ZipFile(temp, "w") as target:
            for info in infos:
                payload = exe if info.filename == EXE_NAME else source.read(info.filename)
                target.writestr(info, payload, compress_type=info.compress_type, compresslevel=9)

    with zipfile.ZipFile(temp, "r") as check:
        failed = check.testzip()
        if failed:
            raise RuntimeError(f"ZIP integrity failure: {failed}")
        check_names = check.namelist()
        if "assets/" in check_names or "app-icon.png" in check_names:
            raise RuntimeError("Redundant root branding returned after repair")

    temp.replace(archive)
    final_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    print(f"FINAL_SHA256={final_sha}")
    print(f"FINAL_SIZE={archive.stat().st_size}")
    print("MODULES_OK=287")
    print("ENDPOINT_OK=https://www.youstoreinformatica.com/ffpfsc/ps5-ffpfsc-feedback.php")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
