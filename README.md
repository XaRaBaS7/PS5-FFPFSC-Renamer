# PS5 FFPFSC Renamer

Windows utility for scanning PS5 `.ffpfsc` libraries, reading game metadata, previewing safe output names and renaming files/folders without rewriting the FFPFSC payload.

> **Current stable release: v0.3.1**  
> **Current development line: v0.4 Smart Library (`0.4.0.dev1`)**

## Preview

<p align="center">
  <img src="docs/screenshots/app-preview.svg" alt="PS5 FFPFSC Renamer interface preview" width="100%">
</p>

> The preview is versioned with the source code. Any visible GUI change must refresh it before merge. See [`docs/SCREENSHOT_POLICY.md`](docs/SCREENSHOT_POLICY.md).

## Highlights

- Scan one or more folders as one logical FFPFSC library.
- Restore saved folders and optionally scan them automatically at startup.
- Always-visible **Scan now / F5** action.
- Optional **Live Library Watch** for new, removed or modified `.ffpfsc` files.
- Persistent SQLite metadata cache, including unchanged `PARTIAL` / `ERROR` results.
- Read internal `sce_sys/param.json` through MkPFS when supported.
- On-demand **Game Details** with `icon0.png`, title, PPSA, versions and raw `param.json`.
- Details/artwork cache so repeated selections do not launch MkPFS again.
- Reorder filename components freely: **PPSA / Title ID**, **Game title**, **Version**.
- Reusable **Naming Profiles** plus a custom filename separator.
- Smart / File-only / Always-new-folder organization modes.
- Search, filter and sort large libraries; display size without reading the whole image.
- Multi-selection with Ctrl/Shift and in-memory selection summaries.
- Collision detection before rename.
- Transactional batch rename with rollback and persistent **Undo / Ctrl+Z**.
- Duplicate Title ID comparison using path, version, size and a lightweight sampled fingerprint.
- CSV/JSON export, Library Health and **Library Statistics**.
- Read-only diagnostics for images that fail the fast metadata path.
- Recycle Bin integration instead of permanent deletion.
- Silent MkPFS execution on Windows, dual progress bars and integrated Activity Log.

## Windows quick start

Download the latest Windows ZIP from GitHub **Releases**, extract the complete folder and run:

```text
PS5-FFPFSC-Renamer.exe
```

Keep this helper next to the application:

```text
mkpfs-helper.exe
```

The packaged Windows release does not require Python, `.venv`, source files or development launchers.

## Library workflow

1. Press **Browse** and choose a folder.
2. Press **+ Add folder** to include additional roots.
3. Use **Folders (N)...** to review or remove roots.
4. Saved roots can be restored and scanned automatically on later launches.
5. Use **Scan now / F5** whenever you want a manual refresh.
6. Review metadata, status and proposed output.
7. Change filename order, profile or folder handling without rescanning.
8. Apply the rename plan only after reviewing it.

Selected library roots are protected: Smart mode never renames the root itself.

## Smart Library Watch — v0.4

Live Watch is optional and disabled by default. When enabled it checks the selected roots at a configurable interval:

```text
15 / 30 / 60 / 120 seconds
```

The watcher compares only:

```text
path + file size + modification timestamp
```

It does **not** continuously parse FFPFSC images. MkPFS runs only when a real library change triggers a normal scan, and unchanged files are then resolved from cache.

For archival HDDs, leaving Live Watch disabled avoids waking the disk unnecessarily. If a selected drive is temporarily unavailable, the watcher reports it and waits instead of clearing the library.

## Game Details — v0.4

Selecting one result can open the collapsible **Game details** workspace. The existing scan metadata is shown immediately, then the app selectively requests only:

```text
sce_sys/param.json
sce_sys/icon0.png
```

No full-game extraction is performed.

The Details tab can show:

- game icon (`icon0.png`);
- title;
- Title ID / PPSA;
- content version;
- master version;
- FFPFSC size;
- Renamer status;
- details source;
- full path.

The `param.json` tab shows the raw formatted JSON and supports clipboard copy.

Detail loading is asynchronous, debounced and cancellable. Rapidly moving through rows does not leave obsolete MkPFS reads running. When multiple rows are selected, the panel shows count, total size, unique Title IDs and status distribution **without launching MkPFS**.

### Details cache

Selected metadata/artwork is cached under:

```text
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\details-cache
```

Cache identity uses path + size + mtime. Cache Manager can show valid/stale entries and disk usage, prune stale entries or clear the details cache. Normal rename transactions migrate an existing details cache entry to the new path so `icon0.png` and `param.json` do not need to be extracted again.

## Filename Builder & Naming Profiles

The builder can combine these components in any order:

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
Returnal - PPSA01285 - v1.0.ffpfsc
v1.0 - Returnal - PPSA01285.ffpfsc
```

v0.4 adds reusable profiles. Bundled profiles include:

- **ShadowMount / PPSA only**;
- **PPSA + Title**;
- **Title + PPSA**;
- **Full archive**;
- **Title + Version + PPSA**.

You can save your current builder as a custom profile, apply it later without rescanning, or delete user-created profiles. Profiles are stored in:

```text
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\naming-profiles.json
```

The separator between components is configurable and persisted too, for example:

```text
" - "
"_"
" "
"."
" + "
```

Windows-invalid filename characters are rejected.

Compact version examples:

```text
01.000.000 -> 1.0
02.500.000 -> 2.5
01.005.000 -> 1.005
```

Changing output settings rebuilds the rename plan from metadata already in memory; `.ffpfsc` files are not rescanned.

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

## Progress and Activity Log

The Analysis area has two indicators:

- **Overall scan** — real determinate progress across the library.
- **Current activity** — animated while discovery, cache checks or MkPFS work is active.

MkPFS selective extraction does not expose a trustworthy per-file percentage, so the app does not invent one.

Typical log output:

```text
[18:24:08] [INFO] Scan requested: 1 root(s)
[18:24:08] [CACHE] Discovery complete: 126 file(s), 124 cache hit(s), 2 MkPFS read(s)
[18:24:10] [MKPFS] Processed PPSA01285.ffpfsc (125/126)
[18:24:12] [OK] Scan complete: 126 file(s), cache 124, MkPFS 2, PARTIAL 0, ERROR 0
```

The Activity Log can be shown/hidden, copied or cleared. A rolling persistent log is stored in:

```text
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\activity.log
```

MkPFS stdout/stderr are captured by the application; normal use does not open console windows.

## Options

The **Options** window keeps advanced configuration out of the main library table.

### General

- autoscan saved folders at startup;
- autoscan after Browse;
- autoscan after Add folder;
- remember window size/position;
- relative or full path display.

### Scan & Performance

- include subfolders;
- worker count (`1`, `2`, `4`, `Auto`);
- optional cache pruning.

Recommended workers:

- **1 (HDD / safest)** — mechanical drives;
- **2** — moderate parallelism;
- **4 (SSD / NVMe)** — faster solid-state storage;
- **Auto** — conservative automatic choice.

GPU acceleration and CPU affinity are intentionally not used for metadata scanning because this workflow is storage-bound and reads only small metadata assets.

### Naming

- components and order;
- version format and optional `v` prefix;
- folder handling;
- custom separator;
- Naming Profiles.

### Cache & Engine

- metadata Cache Manager;
- game-details/artwork cache maintenance;
- App Data folder;
- current MkPFS source;
- custom compatible MkPFS executable.

### Automation — v0.4

- Live Library Watch on/off;
- watch interval.

Settings are stored in:

```text
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\settings.json
```

## Metadata cache & performance

Verified metadata and cached analysis failures are stored in:

```text
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\metadata-cache.sqlite3
```

Fast matching uses:

```text
normalized path + file size + modification timestamp
```

For moved/renamed files or duplicate hints, the app can use a lightweight quick fingerprint:

```text
file size + small samples from beginning + middle + end
```

This is an identity hint, **not** a full checksum or cryptographic integrity proof.

Repeat scans are accelerated through:

- verified metadata cache;
- cached unchanged MkPFS failures;
- batch SQLite lookups;
- iterative `os.scandir()` discovery;
- no directory symlink/reparse traversal;
- on-demand rather than eager artwork extraction;
- details-cache migration after rename.

`Analyze again` explicitly bypasses the failure cache when you want to retry a problematic image.

## Results, statistics and diagnostics

The main table is:

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

- **READY** — current plan can be applied.
- **UNCHANGED** — file/output already match.
- **COLLISION** — target conflicts with another item or existing filesystem object.
- **INVALID** — a safety rule blocks the operation.
- **PARTIAL** — PPSA/title inferred from path but not verified internally; automatic rename stays disabled.
- **ERROR** — metadata could not be read and no safe fallback was available.

### Library Statistics — v0.4

`Tools → Library statistics...` is generated only from current in-memory results. It shows:

- file count;
- total and average known size;
- unique Title IDs;
- duplicate groups/files;
- status distribution;
- largest games;
- details-cache usage;
- unavailable-root information.

It performs no additional MkPFS reads.

### Diagnostics

Normal metadata scanning requests only:

```text
sce_sys/param.json
```

For a problematic image, **Run diagnostics** performs read-only `inspect` and `tree --deep` checks. This helps distinguish wrapped exFAT not detected, direct/raw layouts, truncated images and parser limitations. A `no inner exFAT` result does not by itself prove corruption.

## Transaction safety and Undo

Batch rename is transactional. If a later operation fails, previously completed items are rolled back automatically.

Successful transactions are stored in persistent operation history. **Edit → Undo last rename** or `Ctrl+Z` restores the previous layout only when safe.

Undo never overwrites paths created after the original operation, and app-created folders are removed only when empty.

## Right-click actions

Depending on selection/status, actions include:

- Rename using current plan;
- Rename file manually;
- Show in Explorer / Open folder;
- Run diagnostics;
- Copy full path / Title ID;
- Show details;
- Analyze again;
- Compare duplicates;
- Why blocked?;
- move to Recycle Bin.

Multiple selected rows support batch rename, re-analysis, path copy and Recycle Bin operations. Filesystem-changing actions require confirmation.

## Desktop menus and shortcuts

```text
File  → Scan / Export / Exit
Edit  → Undo / Select all / Clear selection
Tools → Options / History / Health / Statistics / Re-analyze / Cache / MkPFS / App Data
Help  → About
```

```text
F5       Scan library
Ctrl+Z   Undo last rename
Ctrl+A   Select all visible results
Ctrl+E   Export library CSV
```

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
- Live Watch only observes filesystem metadata until an actual change is detected.

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
  External read-only PFS/PFSC inspection and selective-extraction engine. The tested dependency is `MkPFS 0.0.9`. MkPFS remains separately licensed under GPL-3.0.

- **[Send2Trash](https://github.com/arsenetar/send2trash)**  
  Used to move files to the operating-system Recycle Bin instead of permanently deleting them.

### Build / packaging tools

- **[PyInstaller](https://github.com/pyinstaller/pyinstaller)**  
  Used by Windows CI/release packaging to create standalone executables.

### Related projects and inspiration

These projects are useful references in the PS5 FFPFS/PFSC tooling ecosystem. PS5 FFPFSC Renamer does **not** claim their code as its own and does not imply affiliation with their authors.

- **[PS5 exFAT Image Builder — kerrdec97/ps5-exfat-builder](https://github.com/kerrdec97/ps5-exfat-builder)** — library workflow and desktop utility UX reference.
- **[PS5 FFPFSC PRO — KINGDKAK/PS5-FFPFSC-PRO](https://github.com/KINGDKAK/PS5-FFPFSC-PRO)** — related compression utility and progress/log workflow reference.
- **[PS5 FFPFS CLI — bizkut/ps5-ffpfs-cli](https://github.com/bizkut/ps5-ffpfs-cli)** — related CLI whose Title ID auto-naming workflow helped validate metadata-driven naming.

For exact third-party licensing and redistribution notes, see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Development

For source development:

```text
tools\dev\RUN_DEV.bat
```

Or manually:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]" "mkpfs==0.0.9"
pytest -q
ps5-ffpfsc-renamer-gui
```

Windows CI compiles the source, runs tests, verifies README preview freshness and builds the standalone package.

## License

PS5 FFPFSC Renamer is licensed under the **MIT License**. See [`LICENSE`](LICENSE).

MkPFS remains separately licensed under GPL-3.0; see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and the source distribution bundled with Windows releases.
