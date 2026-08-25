# PS5 FFPFSC Renamer

Windows utility for scanning PS5 `.ffpfsc` libraries, reading game metadata, previewing safe output names and renaming files/folders without rewriting the FFPFSC payload.

> **Current stable release: v0.3.1**  
> **Current development line: v0.4 Smart Library**

## Preview

<p align="center">
  <img src="docs/screenshots/app-preview.svg" alt="PS5 FFPFSC Renamer interface preview" width="100%">
</p>

> The preview is versioned with the source code. Any visible GUI change must update this image before it can be merged. See [`docs/SCREENSHOT_POLICY.md`](docs/SCREENSHOT_POLICY.md).

## Highlights

- Scan one or more folders as one logical FFPFSC library.
- Restore saved folders and optionally scan them automatically at startup.
- Always-visible **Scan now / F5** action.
- Automatic scan after **Browse** and **Add folder**, configurable in Options.
- Central **Options** window for startup, scan/performance, naming, cache and MkPFS settings.
- Read internal `sce_sys/param.json` through MkPFS when supported.
- Persistent SQLite metadata cache for very fast repeat scans.
- Cache unchanged MkPFS failures so persistent `PARTIAL` / `ERROR` files are not re-read unnecessarily.
- Reorder filename components freely: **PPSA / Title ID**, **Game title**, **Version**.
- Search, filter and sort large libraries.
- File-size display without reading the whole image.
- Multi-selection with Ctrl/Shift and useful right-click actions.
- Collision detection before rename.
- Transactional batch rename with rollback if a later operation fails.
- Persistent rename history and **Undo / Ctrl+Z**.
- Duplicate Title ID comparison using path, version, size and a lightweight sampled fingerprint.
- CSV/JSON export and Library Health report.
- Read-only diagnostics for images that fail the fast metadata path.
- Recycle Bin integration instead of permanent deletion.
- Branded application icons.
- **Silent MkPFS execution on Windows**: no console popups during scan, diagnostics or engine tests.
- **Dual progress display**: real overall library progress plus animated current-activity progress.
- **Integrated Activity Log** with timestamped cache, MkPFS, warning and error events.

## Windows quick start

Download the latest Windows ZIP from GitHub **Releases**, extract the complete folder and run:

```text
PS5-FFPFSC-Renamer.exe
```

Keep this helper next to the application:

```text
mkpfs-helper.exe
```

The packaged Windows release does not require a separate Python installation.

Development-only files such as `.venv`, `src`, `tests`, `.github`, `pyproject.toml` and development launchers are not required by end users.

## Library workflow

1. Press **Browse** and choose a folder.
2. Press **+ Add folder** to include additional roots.
3. Use **Folders (N)...** to review or remove roots.
4. Saved roots can be restored and scanned automatically on later launches.
5. Use **Scan now / F5** whenever you want a manual refresh.
6. Review detected metadata and proposed output.
7. Change filename order, preset or folder handling without rescanning.
8. Apply the rename plan only after reviewing it.

Selected library roots are protected: Smart mode never renames the root itself.

## Progress and Activity Log

The Analysis area contains two progress indicators:

- **Overall scan** — real determinate progress across the entire library.
- **Current activity** — animated while discovery, cache checks or MkPFS work is active.

MkPFS does not expose a trustworthy per-file percentage for selective metadata extraction, so PS5 FFPFSC Renamer deliberately does not invent one.

Typical log output:

```text
[17:24:08] [INFO] Scan requested: 1 root(s)
[17:24:08] [CACHE] Discovery complete: 126 file(s), 117 cache hit(s), 9 MkPFS read(s)
[17:24:10] [MKPFS] Processed PPSA01285.ffpfsc (118/126)
[17:24:22] [OK] Scan complete: 126 file(s), cache 117, MkPFS 9, PARTIAL 0, ERROR 0
```

The Activity Log can be hidden/shown, copied or cleared. A rolling persistent log is stored in:

```text
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\activity.log
```

MkPFS stdout/stderr are captured by the application; normal use does not open Windows console windows.

## Options

The **Options** window groups advanced configuration without crowding the main library view.

### General

- automatically scan saved folders at startup;
- automatically scan after Browse;
- automatically scan after Add folder;
- remember window size and position;
- show compact relative paths or full paths.

### Scan & Performance

- include subfolders;
- worker count (`1`, `2`, `4`, `Auto`);
- optional pruning of cache records for missing files.

Recommended workers:

- **1 (HDD / safest)** — mechanical drives;
- **2** — moderate parallelism;
- **4 (SSD / NVMe)** — faster solid-state storage;
- **Auto** — conservative automatic choice.

GPU acceleration and CPU affinity are intentionally not used for metadata scanning because this workflow is primarily storage-bound and only extracts very small metadata files.

### Naming

- filename preset;
- PPSA / title / version components;
- compact/original version formatting;
- optional `v` prefix;
- Smart / File only / Always create new folder handling.

### Cache & Engine

- Cache Manager;
- App Data folder;
- current MkPFS source;
- MkPFS Engine Manager / custom compatible executable.

Settings are stored in:

```text
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\settings.json
```

## Metadata cache

Verified metadata and cached analysis failures are stored in:

```text
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\metadata-cache.sqlite3
```

Fast cache matching uses:

```text
normalized path + file size + modification timestamp
```

For moved/renamed files or duplicate hints, the application can use a lightweight quick fingerprint based on:

```text
file size + small samples from beginning + middle + end
```

This is an identity hint, **not** a full checksum or cryptographic integrity proof.

`Analyze again` bypasses the failure cache when you explicitly want to retry a problematic image.

## Filename Builder

Examples:

```text
PPSA01285.ffpfsc
PPSA01285 - Returnal.ffpfsc
Returnal - PPSA01285.ffpfsc
PPSA01285 - Returnal - v1.0.ffpfsc
Returnal - PPSA01285 - v1.0.ffpfsc
v1.0 - Returnal - PPSA01285.ffpfsc
```

Compact version examples:

```text
01.000.000 -> 1.0
02.500.000 -> 2.5
01.005.000 -> 1.005
```

Changing output settings rebuilds the plan from metadata already in memory; `.ffpfsc` files are not rescanned.

## Folder handling

### Smart — recommended

Loose file in a library root:

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

Renames only the `.ffpfsc`; folder names remain unchanged.

### Always create new folder

Creates a generated per-game folder and moves the renamed FFPFSC into it.

## Transaction safety and Undo

Batch rename is transactional. If a later operation fails, previously completed items are rolled back automatically.

Successful rename transactions are written to persistent history. **Edit → Undo last rename** or `Ctrl+Z` restores the previous layout only when it is still safe.

Undo never overwrites paths created after the original operation, and app-created folders are removed only when empty.

## Result table

```text
Current file | Title ID | Title | Version | Size | Proposed output | Status
```

Available filters:

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
- **COLLISION** — the target conflicts with another item or existing filesystem object.
- **INVALID** — a safety rule blocks the operation.
- **PARTIAL** — metadata could not be verified internally, but PPSA/title was inferred from the path; automatic rename stays disabled.
- **ERROR** — metadata could not be read and no safe fallback was available.

Hover the Status cell for a concise explanation.

## Right-click actions

Single-row actions include:

- Rename using current plan
- Rename file manually
- Show in Explorer
- Open folder
- Run diagnostics
- Copy full path
- Copy Title ID / PPSA
- Show details
- Analyze again
- Compare duplicates
- Why blocked?
- Delete → move to Recycle Bin

Multiple selected rows support selected rename, re-analysis, path copy and Recycle Bin operations.

Filesystem-changing actions require confirmation.

## Desktop menus and shortcuts

```text
File  → Scan / Export / Exit
Edit  → Undo / Select all / Clear selection
Tools → Options / History / Health / Re-analyze problems / Cache / MkPFS / App Data
Help  → About
```

```text
F5       Scan library
Ctrl+Z   Undo last rename
Ctrl+A   Select all visible results
Ctrl+E   Export library CSV
```

## Diagnostics

The fast metadata reader requests only:

```text
sce_sys/param.json
```

using MkPFS selective extraction:

```text
mkpfs unpack game.ffpfsc temp-dir --deep --only sce_sys/param.json --no-progress
```

For an image that fails this path, **Run diagnostics** performs read-only `inspect` and `tree --deep` checks.

This helps distinguish wrapped exFAT not detected, direct/raw layouts, truncated images and parser limitations. A `no inner exFAT` result does not by itself prove corruption.

## Performance

Repeat scans are accelerated through:

- verified metadata cache;
- cached unchanged MkPFS failures;
- batch SQLite lookups;
- iterative `os.scandir()` discovery;
- no traversal of directory symlinks/reparse points.

With multiple roots, an unavailable drive/folder can be skipped while other available roots continue scanning.

## Safety principles

- Rename operations never rewrite or recompress FFPFSC contents.
- Automatic rename plans use only internally verified metadata or cache records originally created from verified metadata.
- Path-derived `PARTIAL` metadata is display-only.
- Existing destination files/folders are not overwritten or merged automatically.
- Selected library roots are never renamed by Smart mode.
- Batch operations roll back completed items if a later rename fails.
- Undo refuses unsafe overwrites.
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

## Credits & Acknowledgements

PS5 FFPFSC Renamer is its own project, but it relies on and has benefited from the wider homebrew/open-source ecosystem. Many thanks to the authors and maintainers of the following projects.

### Runtime / bundled dependencies

- **[MkPFS — PSBrew/MkPFS](https://github.com/PSBrew/MkPFS)**  
  Used as the external read-only PFS/PFSC inspection and selective-extraction engine. The tested release dependency is `MkPFS 0.0.9`. MkPFS remains separately licensed under GPL-3.0.

- **[Send2Trash](https://github.com/arsenetar/send2trash)**  
  Used to move files to the operating-system Recycle Bin instead of permanently deleting them.

### Build / packaging tools

- **[PyInstaller](https://github.com/pyinstaller/pyinstaller)**  
  Used by the Windows CI/release workflow to create standalone executables.

### Related projects and inspiration

These projects are useful references in the PS5 FFPFS/PFSC tooling ecosystem. PS5 FFPFSC Renamer does **not** claim their code as its own and does not imply affiliation with their authors.

- **[PS5 exFAT Image Builder — kerrdec97/ps5-exfat-builder](https://github.com/kerrdec97/ps5-exfat-builder)**  
  A useful reference for PS5 image-library workflows and desktop utility UX.

- **[PS5 FFPFSC PRO — KINGDKAK/PS5-FFPFSC-PRO](https://github.com/KINGDKAK/PS5-FFPFSC-PRO)**  
  A related FFPFSC creation/compression utility and a useful reference for workflow and progress/log presentation.

- **[PS5 FFPFS CLI — bizkut/ps5-ffpfs-cli](https://github.com/bizkut/ps5-ffpfs-cli)**  
  A related command-line project whose Title ID auto-naming workflow helped validate the usefulness of metadata-driven naming.

For exact third-party licensing and redistribution notes, see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Development

For source development use:

```text
tools\dev\RUN_DEV.bat
```

Or manually:

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

The Windows CI compiles the source, runs tests, verifies README preview freshness and builds the standalone package.

## License

PS5 FFPFSC Renamer is licensed under the **MIT License**. See [`LICENSE`](LICENSE).

MkPFS remains separately licensed under GPL-3.0; see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and the source distribution bundled with Windows releases.
