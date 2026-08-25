# PS5 FFPFSC Renamer

Windows utility for scanning PS5 `.ffpfsc` libraries, reading internal metadata, previewing safe output names and renaming files/folders **without rewriting or recompressing the FFPFSC payload**.

> **Current release: v0.4.1 — Version Sync Hotfix**

## Preview

<p align="center">
  <img src="docs/screenshots/app-preview.svg" alt="PS5 FFPFSC Renamer v0.4.0 interface preview" width="100%">
</p>

> The preview is versioned with the source. Visible GUI changes must refresh `docs/screenshots/app-preview.svg` before merge. See [`docs/SCREENSHOT_POLICY.md`](docs/SCREENSHOT_POLICY.md).

## Highlights

- Scan one or more folders as one logical FFPFSC library.
- Restore saved folders and optionally **auto-scan at startup**.
- Always-visible **Scan now / F5** action.
- Optional **Live Library Watch** for added, removed and modified `.ffpfsc` files.
- Persistent SQLite metadata cache, including unchanged `PARTIAL` / `ERROR` results.
- Read internal `sce_sys/param.json` through MkPFS when supported.
- On-demand **Game Details** with `icon0.png`, title, PPSA, versions and raw `param.json`.
- Dedicated details/artwork cache so repeated selections do not relaunch MkPFS.
- Reusable **Naming Profiles**, custom separators and freely reorderable PPSA / Title / Version components.
- Smart / File-only / Always-new-folder organization modes.
- Search, filters, sortable columns, file size and multi-selection.
- Transactional batch rename with automatic rollback.
- Persistent **Operation History + Ctrl+Z Undo**.
- Fresh **rename pre-flight** immediately before filesystem changes.
- Fast **post-rename identity verification** without reading the entire image.
- Built-in **Rename Safety Self-Test** using temporary dummy `.ffpfsc` files.
- Duplicate comparison, CSV/JSON export, Library Health and Library Statistics.
- Read-only diagnostics for problematic images.
- Recycle Bin integration instead of permanent deletion.
- Silent MkPFS helper execution on Windows, dual progress bars and integrated Activity Log.

## Windows quick start

Download the Windows ZIP from GitHub **Releases**, extract the complete archive and run:

```text
PS5-FFPFSC-Renamer.exe
```

Keep the helper next to the application:

```text
mkpfs-helper.exe
```

The packaged Windows build does **not** require Python, `.venv`, source files or development launchers.

## Typical workflow

1. Press **Browse** and choose a folder containing `.ffpfsc` files.
2. Use **+ Add folder** to add more library roots.
3. Wait for the automatic scan or press **Scan now / F5**.
4. Review Title ID, title, version, size, proposed output and status.
5. Choose a Naming Profile or build your own output format.
6. Review the rename pre-flight summary.
7. Apply only `READY` items.
8. The app verifies the completed paths and keeps the transaction available for **Ctrl+Z Undo**.

Selected library roots are protected: Smart mode never renames the root itself.

## Rename safety

Rename operations are deliberately conservative.

### Before Apply — pre-flight

Immediately before the filesystem is changed, the app checks the plan again. This catches situations such as a destination file appearing **after** the original preview but before confirmation.

The pre-flight summary includes:

```text
READY files
represented data size
file path changes
folders to create
folders to rename
blocked rows left untouched
```

Existing destinations are never silently overwritten or merged.

### During Apply — transactional rollback

Batch operations are transactional. If a later file/folder operation fails, already-completed steps are rolled back automatically whenever possible. Incomplete rollback is reported explicitly instead of being hidden behind a generic error.

### After Apply — identity verification

A rename should change a path, not the file contents. After generated rename operations, the app verifies the destination using:

```text
file size + filesystem device/file ID
```

On Windows/NTFS this normally verifies that the destination is the same filesystem object. If a usable file ID is unavailable, the app falls back to its lightweight sampled fingerprint.

This check does **not** read tens or hundreds of gigabytes just to validate a rename.

### Undo / Operation History

Successful transactions are written to a persistent SQLite journal. `Edit → Undo last rename` or `Ctrl+Z` restores the latest transaction only when safe.

Undo:

- never overwrites an existing original path;
- removes app-created folders only when empty;
- preserves folders containing user-added data;
- also keeps metadata/details caches aligned with restored paths.

### Rename Safety Self-Test

Use:

```text
Tools → Rename safety self-test...
```

The self-test never touches your library. It creates disposable dummy `.ffpfsc` files in a temporary folder and performs real filesystem operations covering:

- File-only rename + Undo;
- Smart loose-file folder creation + Undo;
- Smart existing-folder rename + Undo;
- collision protection;
- late batch collision + automatic rollback;
- SHA-256 comparison of the temporary payloads before/after.

The same suite runs in GitHub Actions CI.

## Game Details — v0.4

Select one result to open the **Game details** workspace. Existing scan metadata appears immediately; in the background the app selectively requests only:

```text
sce_sys/param.json
sce_sys/icon0.png
```

It does **not** extract the complete game image.

The Details workspace can show:

- `icon0.png`;
- game title;
- Title ID / PPSA;
- content version;
- master version;
- FFPFSC size;
- Renamer status;
- data source;
- full path.

The `param.json` tab displays formatted raw JSON with clipboard copy.

Loading is asynchronous, debounced and cancellable. Rapidly moving between rows does not leave obsolete detail reads running. With multiple selected rows, the panel switches to an in-memory summary and does not launch MkPFS.

### Details cache

Details/artwork are stored under:

```text
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\details-cache
```

Cache Manager reports valid/stale entries and disk usage, can prune stale entries, or clear the cache. Rename and Undo operations migrate valid cache entries to the new/restored path so artwork and JSON remain instant.

## Live Library Watch — v0.4

Live Watch is optional and disabled by default. Available intervals:

```text
15 / 30 / 60 / 120 seconds
```

The watcher checks only:

```text
path + size + modification timestamp
```

It does not continuously parse images. When a real change is detected, the normal cached scan runs. Activity Log distinguishes:

```text
Added / Removed / Modified
```

If a selected drive is temporarily unavailable, the watcher reports it and waits instead of clearing the current library.

For archival HDDs, leaving Live Watch off avoids unnecessarily waking/spinning the disk.

## Filename Builder & Naming Profiles

Components can be enabled and reordered freely:

```text
PPSA / Title ID
Game title
Version
```

Examples:

```text
PPSA01285.ffpfsc
PPSA01285 - Returnal.ffpfsc
Returnal - PPSA01285.ffpfsc
PPSA01285 - Returnal - v1.0.ffpfsc
Returnal - v1.0 - PPSA01285.ffpfsc
```

Built-in profiles include:

- **ShadowMount / PPSA only**;
- **PPSA + Title**;
- **Title + PPSA**;
- **Full archive**;
- **Title + Version + PPSA**.

Custom profiles remember enabled components, order, version formatting, optional `v` prefix, folder handling and separator. User profiles are stored in:

```text
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\naming-profiles.json
```

Separators can be customized, for example:

```text
" - "
"_"
" "
"."
" + "
```

Compact version examples:

```text
01.000.000 -> 1.0
02.500.000 -> 2.5
01.005.000 -> 1.005
```

Changing output settings rebuilds the plan from metadata already in memory; FFPFSC files are not rescanned.

## Folder handling

### Smart — recommended

Loose file:

```text
Before:
G:\PS5\FFPFSC\Returnal.ffpfsc

After:
G:\PS5\FFPFSC\PPSA01285 - Returnal\
└── PPSA01285 - Returnal.ffpfsc
```

Already in a dedicated folder:

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

If a candidate folder contains multiple `.ffpfsc` files, Smart mode blocks the folder rename instead of guessing.

### File only

Only the `.ffpfsc` filename changes.

### Always create new folder

Creates a generated per-game folder and moves the renamed FFPFSC into it.

## Results and statuses

Main table:

```text
Current file | Title ID | Title | Version | Size | Proposed output | Status
```

Filters:

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

Status meanings:

- **READY** — current verified plan can be applied.
- **UNCHANGED** — current path already matches the planned output.
- **COLLISION** — destination conflicts with another item or filesystem object.
- **INVALID** — a safety rule blocks the operation.
- **PARTIAL** — some metadata could be inferred from path/name but was not internally verified; automatic rename stays disabled.
- **ERROR** — metadata could not be read and no safe fallback was available.

Hovering `COLLISION` / blocked rows and the context menu explain why the operation is blocked.

## Progress & Activity Log

The Analysis area uses two progress indicators:

- **Overall scan** — real determinate progress across the library.
- **Current activity** — animated during discovery, cache checks and MkPFS work.

MkPFS selective extraction does not expose a trustworthy percentage for one image, so the app does not invent a per-file percentage.

Typical log messages:

```text
[21:30:02] [CACHE] 124 unchanged file(s) reused
[21:30:03] [MKPFS] Reading metadata: PPSA01285.ffpfsc
[21:30:04] [INFO] Rename pre-flight OK • 3 file(s)
[21:30:04] [OK] Post-rename verification passed • 3/3
```

A rolling log is stored in:

```text
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\activity.log
```

MkPFS stdout/stderr are captured internally; normal Windows use does not open console windows.

## Performance

Repeat scans are accelerated through:

- exact path + size + mtime cache hits;
- remembered unchanged MkPFS failures;
- batch SQLite lookups;
- iterative `os.scandir()` discovery;
- no directory symlink/reparse traversal;
- configurable workers;
- on-demand artwork extraction;
- details-cache migration after Rename and Undo.

Recommended metadata workers:

- **1 (HDD / safest)** — mechanical/archive drives;
- **2** — moderate parallelism;
- **4 (SSD / NVMe)** — fast solid-state storage;
- **Auto** — conservative automatic selection.

GPU acceleration and CPU affinity are intentionally not used for metadata scanning: this workload is primarily storage-bound and selectively reads small metadata assets.

## Tools

Desktop menus expose:

```text
File  → Scan / Export / Exit
Edit  → Undo / Select all / Clear selection
Tools → Options / History / Health / Statistics / Re-analyze / Cache / MkPFS / App Data / Rename safety self-test
Help  → About
```

Useful shortcuts:

```text
F5       Scan library
Ctrl+Z   Undo last rename
Ctrl+A   Select all visible results
Ctrl+E   Export library CSV
```

Library Statistics is generated entirely from in-memory scan results and performs no additional MkPFS reads.

Read-only diagnostics use MkPFS `inspect` / `tree --deep` to help distinguish unsupported/wrapped layouts, truncated images and parser limitations.

## Local application data

```text
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\settings.json
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\metadata-cache.sqlite3
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\operation-history.sqlite3
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\naming-profiles.json
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\details-cache\
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\activity.log
```

`Clear cache` does not erase saved library folders/settings unless the corresponding settings action explicitly requests it.

## ⚠️ Legal & Responsible Use

> **Homebrew & Personal Backup Tool**
>
> PS5 FFPFSC Renamer is intended only for lawful homebrew use and for games/content **you legally own and have dumped yourself**.
>
> It **does not** download games, decrypt retail packages, provide encryption/license keys, bypass DRM or license checks, distribute copyrighted PlayStation files, or include firmware, exploits or payloads.
>
> Users are responsible for complying with applicable laws and license terms. This project is not affiliated with, sponsored by, or endorsed by Sony Interactive Entertainment.

## Credits & Acknowledgements

PS5 FFPFSC Renamer is an independent project. Many thanks to the authors and maintainers of the tools and projects below.

### Runtime / bundled dependencies

- **[MkPFS — PSBrew/MkPFS](https://github.com/PSBrew/MkPFS)** — read-only PFS/PFSC inspection and selective extraction engine used by the Renamer. Tested dependency: `MkPFS 0.0.9`. MkPFS remains separately licensed under GPL-3.0.
- **[Send2Trash](https://github.com/arsenetar/send2trash)** — used for operating-system Recycle Bin integration instead of permanent deletion.

### Build / packaging

- **[PyInstaller](https://github.com/pyinstaller/pyinstaller)** — used by Windows CI/release packaging to build standalone executables.

### Related projects and inspiration

These are useful references in the PS5 FFPFS/PFSC tooling ecosystem. Their inclusion here does **not** imply code ownership, affiliation or endorsement.

- **[PS5 exFAT Image Builder — kerrdec97/ps5-exfat-builder](https://github.com/kerrdec97/ps5-exfat-builder)** — library workflow and desktop utility UX reference.
- **[PS5 FFPFSC PRO — KINGDKAK/PS5-FFPFSC-PRO](https://github.com/KINGDKAK/PS5-FFPFSC-PRO)** — related compression utility and progress/log workflow reference.
- **[PS5 FFPFS CLI — bizkut/ps5-ffpfs-cli](https://github.com/bizkut/ps5-ffpfs-cli)** — related CLI whose Title ID auto-naming workflow helped validate metadata-driven naming.

For exact third-party licensing and redistribution notes, see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Development

Source-development launcher:

```text
tools\dev\RUN_DEV.bat
```

Manual setup:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]" "mkpfs==0.0.9"
pytest -q
ps5-ffpfsc-renamer-gui
```

GitHub Actions compiles the source, checks README preview freshness, executes automated tests including the temporary-filesystem Rename Safety Self-Test, and builds the standalone Windows package.

## License

PS5 FFPFSC Renamer is licensed under the **MIT License**. See [`LICENSE`](LICENSE).

MkPFS remains separately licensed under GPL-3.0; see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and the exact source distribution bundled with Windows releases.
