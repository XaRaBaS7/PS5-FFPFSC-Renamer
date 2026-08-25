# PS5 FFPFSC Renamer

Windows utility for scanning PS5 `.ffpfsc` libraries, reading game metadata, previewing safe output names and renaming files/folders without rewriting the FFPFSC payload.

> **Current release target: v0.2.0**

## Highlights

- Scan one or more folders as a single FFPFSC library.
- **Browse** starts scanning immediately; **Add folder** extends the same library.
- Restore your previous folders and UI preferences when the app reopens.
- Read internal `sce_sys/param.json` through MkPFS when supported.
- Persist verified metadata in a local SQLite cache so unchanged files are skipped on later scans.
- Build filenames in any order using **PPSA / Title ID**, **Game title** and **Version**.
- Search and filter large libraries by status or duplicate Title ID.
- Display file size without reading the whole image.
- Select multiple rows with Ctrl/Shift and use right-click operations on the selection.
- Detect collisions before any rename.
- Compare duplicate Title IDs using path, version, size and a lightweight sampled fingerprint.
- Diagnose FFPFSC images that MkPFS cannot parse through the fast metadata path.
- Move files to the Windows Recycle Bin instead of permanently deleting them.

## Windows quick start

### Packaged release — recommended

Download the Windows ZIP from the GitHub **Releases** page, extract the **complete folder**, then run:

```text
PS5-FFPFSC-Renamer.exe
```

The packaged release is designed to run without a separate Python installation. Keep `mkpfs-helper.exe` next to the main application executable; it is the isolated MkPFS helper used for metadata inspection.

### Development checkout

Clone/download the repository and run:

```text
RUN.bat
```

The launcher creates `.venv`, installs the project plus the tested `MkPFS 0.0.9`, and starts the GUI.

## Library workflow

1. Press **Browse** and choose a folder. The scan begins automatically.
2. Press **+ Add folder** to include more roots.
3. Use **Folders (N)...** to review/remove roots.
4. Review detected metadata and the proposed output.
5. Change filename order/preset/folder handling without rescanning.
6. Apply only after the plan is correct.

Selected roots are protected: Smart mode never renames the library root itself.

### Persistent configuration

The app stores preferences here:

```text
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\settings.json
```

Persisted settings include:

- library folders;
- recursive scanning;
- worker count;
- filename preset and enabled components;
- component order;
- compact/original version format;
- `v` prefix;
- folder handling mode;
- result filter;
- window geometry.

`Clear cache` does **not** delete these preferences.

## Metadata cache

Verified metadata is cached here:

```text
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\metadata-cache.sqlite3
```

The fastest cache path checks:

```text
normalized path + file size + modification timestamp
```

If a known file was moved or renamed, the cache can use a lightweight quick fingerprint based on:

```text
file size + small samples from beginning + middle + end
```

This reads only a tiny portion of a huge image. It is an identity hint for cache/duplicate handling, **not** a full checksum or cryptographic integrity proof.

## Filename Builder

Presets are shortcuts; the component order is fully user-controlled.

Examples:

```text
PPSA01285.ffpfsc
PPSA01285 - Returnal.ffpfsc
Returnal - PPSA01285.ffpfsc
PPSA01285 - Returnal - v1.0.ffpfsc
Returnal - PPSA01285 - v1.0.ffpfsc
v1.0 - Returnal - PPSA01285.ffpfsc
```

Version formatting supports:

```text
Compact:
01.000.000 -> 1.0
02.500.000 -> 2.5
01.005.000 -> 1.005

Original:
01.000.000
```

Changing output settings after a scan rebuilds the rename plan instantly from metadata already in memory; the `.ffpfsc` files are not scanned again.

## Folder handling

### Smart (recommended)

Loose file in a selected root:

```text
Before:
G:\PS5\FFPFSC\Returnal.ffpfsc

After:
G:\PS5\FFPFSC\PPSA01285 - Returnal\
└── PPSA01285 - Returnal.ffpfsc
```

Already inside a dedicated folder:

```text
Before:
G:\PS5\FFPFSC\Returnal old\
├── game.ffpfsc
└── notes.txt

After:
G:\PS5\FFPFSC\PPSA01285 - Returnal\
├── PPSA01285 - Returnal.ffpfsc
└── notes.txt
```

If a folder contains multiple `.ffpfsc` files, Smart mode blocks the folder rename instead of guessing.

### File only

Renames only the `.ffpfsc`; folder names stay unchanged.

### Always create new folder

Always creates a generated per-game folder and moves the renamed FFPFSC inside it.

## Result table

The main table includes:

```text
Current file | Title ID | Title | Version | Size | Proposed output | Status
```

Use the Search box for free-text filtering and the Filter selector for:

```text
ALL
READY
UNCHANGED
PARTIAL
COLLISION
INVALID
ERROR
DUPLICATES
```

### Status meanings

- **READY** — the current plan can be applied.
- **UNCHANGED** — file/output already match.
- **COLLISION** — another file/folder would use the same target or the target already exists.
- **INVALID** — a safety rule prevents the operation.
- **PARTIAL** — MkPFS could not verify internal metadata, but a PPSA/title could be inferred from the filename/folder. Display-only; automatic rename is disabled.
- **ERROR** — metadata could not be read and no safe fallback was available.

Hover the **Status** cell for a concise explanation. Hover a duplicate **Title ID** for a duplicate hint.

## Right-click actions

Single row:

- Rename using current plan
- Rename file manually
- Show in Explorer
- Open folder
- Run diagnostics
- Copy full path
- Copy Title ID / PPSA
- Show details
- Analyze again
- Compare duplicates (when applicable)
- Why blocked? (when applicable)
- Delete → move to Recycle Bin

Multiple selected rows:

- Rename selected READY rows
- Analyze selected again
- Copy selected paths
- Delete selected → Recycle Bin

Filesystem-changing actions require confirmation.

## Duplicate comparison

When the same Title ID appears more than once, **Compare duplicates** reports for each file:

- full path;
- game title;
- version;
- size;
- status;
- quick fingerprint.

No duplicate is deleted automatically. The fingerprint reads only small samples and is explicitly not treated as a whole-file checksum.

## Diagnostics and problematic images

The fast metadata reader requests only:

```text
sce_sys/param.json
```

through:

```text
mkpfs unpack game.ffpfsc temp-dir --deep --only sce_sys/param.json --no-progress
```

For an image that fails this path, **Run diagnostics** performs read-only MkPFS checks using `inspect` and `tree --deep`.

This helps distinguish cases such as:

- wrapped exFAT not detected;
- direct/raw PFS layouts;
- truncated/unreadable image structure;
- current MkPFS parser limitations.

A `no inner exFAT` result does not by itself prove that a file is corrupt.

## Performance

The first scan of a large library may take time because every unknown image must be inspected. Later scans should be much faster because unchanged files use the SQLite cache.

Worker choices:

- **1 (HDD / safest)** — recommended for mechanical drives;
- **2** — moderate parallelism;
- **4 (SSD / NVMe)** — for faster solid-state storage;
- **Auto** — conservative automatic setting.

GPU acceleration and CPU affinity are intentionally not used for metadata scanning. The operation is primarily storage-bound and only extracts a very small metadata file.

## Safety principles

- Rename operations never rewrite or recompress FFPFSC contents.
- Automatic rename plans use only metadata verified from internal `sce_sys/param.json` or a cache entry originally created from that verified metadata.
- Path-derived `PARTIAL` metadata is display-only.
- Existing destination files/folders are not overwritten or merged automatically.
- Selected library roots are never renamed by Smart mode.
- Recycle Bin actions require confirmation.
- Cancellation stops metadata analysis without applying rename operations.

## ⚠️ Legal & Responsible Use

> **Homebrew & Personal Backup Tool**
>
> PS5 FFPFSC Renamer is intended for lawful homebrew use and for managing personal backup images created from games or content that you legally own and have dumped yourself.
>
> It does **not** download or distribute games, decrypt retail packages, provide encryption/license keys, bypass DRM or license checks, distribute copyrighted PlayStation files, or include firmware, exploits or payloads.
>
> Users are responsible for complying with the laws and license terms that apply in their jurisdiction. The project is not affiliated with, sponsored by, or endorsed by Sony Interactive Entertainment.

## MkPFS dependency

MkPFS is a separate project licensed under GPL-3.0. Development installs `mkpfs==0.0.9` from PyPI.

The packaged Windows release keeps MkPFS in a **separate helper executable** and includes the exact MkPFS 0.0.9 source distribution under:

```text
source\third-party\
```

See `THIRD_PARTY_NOTICES.md` for details.

## Development

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]" "mkpfs==0.0.9"
pytest -q
```

Run the GUI:

```powershell
ps5-ffpfsc-renamer-gui
```

The repository CI runs on Windows and includes source compilation, unit tests and a synthetic MkPFS end-to-end metadata round-trip.

## Build

`.github/workflows/build-windows.yml` creates a standalone Windows archive containing:

```text
PS5-FFPFSC-Renamer.exe
mkpfs-helper.exe
README.md
LICENSE
THIRD_PARTY_NOTICES.md
CHANGELOG.md
source\third-party\mkpfs-0.0.9...
```

A release commit on `main` beginning with `release:` triggers the tagged GitHub release workflow.

## License

PS5 FFPFSC Renamer is licensed under the **MIT License**. See `LICENSE`.

MkPFS remains separately licensed under GPL-3.0; see `THIRD_PARTY_NOTICES.md` and the source distribution bundled with Windows releases.

---

Created by **XaRaBaS** — https://github.com/XaRaBaS7/PS5-FFPFSC-Renamer
