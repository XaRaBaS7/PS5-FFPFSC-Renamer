# PS5-FFPFSC-Renamer

Windows utility for scanning PS5 `.ffpfsc` files, detecting game metadata (including PPSA / Title ID), previewing a safe filename, and batch-renaming files without modifying their contents.

## Project status

**v0.1.0 development preview.**

The first milestone is intentionally conservative: **read-only analysis first, rename only after an explicit preview**.

Windows CI validates the Python source, unit tests, configurable naming rules, persistent metadata caching, folder-output planning, and a synthetic MkPFS round-trip that creates a small `.ffpfsc`, extracts only `sce_sys/param.json`, and verifies the detected metadata.

## Goals

- Scan one folder or an entire folder tree for `*.ffpfsc` files.
- Read only the minimum metadata needed from each container.
- Detect the PS5 Title ID / PPSA when available.
- Display title and version when available.
- Reuse metadata from unchanged files on later scans.
- Preview the proposed filename or folder layout before making any changes.
- Rename files without rewriting or recompressing the `.ffpfsc` payload.
- Optionally create one folder per game and move the renamed `.ffpfsc` inside it.
- Detect duplicate targets and filesystem collisions before renaming.
- Leave unrecognized or invalid files untouched.

## Output formats

The GUI includes an interactive output designer. Presets include:

```text
PPSA01285.ffpfsc
PPSA01285 - Returnal.ffpfsc
PPSA01285 - Returnal - v1.0.ffpfsc
```

Version display can use either a compact form:

```text
01.000.000 -> 1.0
02.500.000 -> 2.5
01.005.000 -> 1.005
```

or the original metadata value:

```text
PPSA01285 - Returnal - 01.000.000.ffpfsc
```

The optional per-game folder mode produces output such as:

```text
PPSA01285 - Returnal - v1.0\
└── PPSA01285 - Returnal - v1.0.ffpfsc
```

Changing naming options after a completed scan **does not read the FFPFSC files again**. The already detected metadata is reused and the collision-safe rename plan is rebuilt instantly.

## Persistent metadata cache

Large `.ffpfsc` libraries can take time to inspect on the first pass. PS5-FFPFSC-Renamer therefore maintains a local SQLite metadata database at:

```text
%LOCALAPPDATA%\PS5-FFPFSC-Renamer\metadata-cache.sqlite3
```

The selected game directory is not modified by the cache.

For an unchanged file, the fast path checks:

```text
normalized path + file size + modification timestamp
```

If a previously analyzed file has been renamed or moved, the cache can fall back to a lightweight **quick fingerprint** made from:

```text
file size + small samples from the beginning, middle and end of the file
```

This is deliberately **not** a CRC or hash of the entire image. Reading every byte of a 50–150 GB file just to validate the cache would defeat the purpose of caching.

Only files that are new, changed, or cannot be matched safely are sent through MkPFS again. The GUI shows how many files came **FROM CACHE** and how many required a new MkPFS metadata read.

The quick fingerprint is only a cache identity hint; it is not presented as a cryptographic integrity checksum.

## Safety principles

The application never renames a file merely because a PPSA-like string appears somewhere in binary data. Metadata must come from the verified `sce_sys/param.json` extraction path or from a previously stored cache entry created from that path.

Before any rename/move, the program checks that:

- the source file exists;
- the detected Title ID is valid;
- the generated Windows filename is sanitized;
- the destination does not already exist;
- two scanned files do not resolve to the same destination;
- a requested output folder is not occupied by a file;
- source and destination are not already the same path when folder mode is disabled.

The GUI enables the apply action only after a completed plan with no blocked/error entries and then asks for explicit confirmation.

## Legal & Responsible Use

> ⚠️ **Homebrew & Personal Backup Tool**
>
> PS5-FFPFSC-Renamer is intended for lawful homebrew use and for managing personal backup images created from games or content that you legally own and have dumped yourself.
>
> The project does **not** download or distribute games, decrypt retail packages, provide encryption or license keys, bypass DRM or license checks, distribute copyrighted PlayStation files, or include firmware, exploits or payloads.
>
> Users are responsible for complying with the laws and license terms that apply in their country. This project is not affiliated with, sponsored by, or endorsed by Sony Interactive Entertainment.

## Windows quick start

Python 3.11+ is currently required for the development preview. `RUN.bat` automatically detects supported Python 3.11, 3.12, 3.13 or 3.14 installations.

1. Clone or download this repository.
2. Double-click:

```text
RUN.bat
```

The launcher creates a local `.venv`, installs this project plus the currently tested `MkPFS 0.0.9`, and opens the GUI.

## Interface

The Windows UI uses an original dark-violet `tkinter/ttk` design with:

- left navigation/status rail;
- MkPFS engine status;
- SQLite cache entry count and cache-clear action;
- Files / From Cache / Ready / Blocked summary cards;
- folder browser and recursive scan option;
- selectable analysis worker count;
- configurable output presets and components;
- compact/original version formatting;
- optional per-game folder creation;
- live output preview;
- real-time progress bar;
- cache/new-file counters, percentage, elapsed time and ETA;
- cancellable MkPFS metadata reads;
- metadata library table;
- explicit apply confirmation.

The visual direction is inspired by modern PS5 homebrew utilities, while the layout and implementation in this repository are original.

## Performance

FFPFSC files may be very large, but the renamer requests only `sce_sys/param.json`; it does not unpack the full game image. Even so, the first scan of a large library may take time because every previously unknown container must be opened and inspected.

Later scans are designed to be much faster because unchanged files are served from the metadata cache.

The GUI offers these analysis worker settings:

- **1 (HDD / safest)** — recommended for mechanical hard drives and the safest default;
- **2** — useful for faster storage without creating too much parallel I/O;
- **4 (SSD / NVMe)** — intended for fast solid-state storage;
- **Auto** — currently uses up to two concurrent MkPFS readers as a conservative balance.

CPU affinity and GPU acceleration are intentionally not used. The metadata operation is primarily storage-bound, so assigning more CPU cores or a GPU generally does not make it faster and can make a mechanical disk slower if too many reads happen in parallel.

## Architecture

```text
src/ps5_ffpfsc_renamer/
├── cache.py            # persistent SQLite metadata cache + quick fingerprint
├── cli.py              # command-line entry point
├── gui.py              # stable GUI entry point
├── gui_v2.py           # current Windows desktop interface
├── scanner.py          # folder/file discovery
├── metadata.py         # normalized metadata model
├── naming.py           # filename templates, version formatting, sanitization
├── ffpfsc_reader.py    # MkPFS metadata extraction + cache integration
├── rename_plan.py      # dry-run, folder targets and collision checks
├── renamer.py          # explicit filesystem rename/move operation
└── theme.py            # original dark-violet ttk theme
```

### MkPFS integration

The implementation uses the external MkPFS command-line interface to cherry-pick `sce_sys/param.json` from an image:

```text
mkpfs unpack game.ffpfsc temp-dir --deep --only sce_sys/param.json --no-progress
```

MkPFS documents that `--only` reads only matching entries, making this suitable for metadata inspection without extracting the complete image.

MkPFS is a separate GPL-3.0 project and is **not copied into this repository**. The current automated test environment installs MkPFS `0.0.9` from PyPI.

## Development roadmap

### v0.1.0

- [x] Repository bootstrap
- [x] Folder scanner
- [x] Metadata model
- [x] `.ffpfsc` metadata extraction proof of concept
- [x] Title ID / PPSA validation
- [x] Rename dry-run
- [x] Collision detection
- [x] Command-line test interface
- [x] Windows GUI
- [x] Synthetic `.ffpfsc` end-to-end test
- [x] Windows development launcher
- [x] Progress / ETA / cancellation
- [x] Configurable analysis workers
- [x] SQLite metadata cache
- [x] Fast renamed/moved-file fingerprint fallback
- [x] Configurable filename formats
- [x] Compact/original version formatting
- [x] Optional per-game folder creation

### v0.2.0

- [ ] Drag & drop
- [ ] Rename operation log / undo guidance
- [ ] Cover art / richer library metadata
- [ ] User-selectable MkPFS executable path
- [ ] Cache management/details dialog

### v1.0.0

- [ ] Windows executable distribution strategy
- [ ] Automated Windows build
- [ ] Tested error handling on very large real-world libraries
- [ ] Final third-party licensing review

## Development

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev] "mkpfs==0.0.9"
pytest -q
```

Run the GUI:

```powershell
ps5-ffpfsc-renamer-gui
```

Run a dry scan from the command line:

```powershell
ps5-ffpfsc-renamer scan "D:\PS5\FFPFSC"
```

Apply a validated default rename plan explicitly:

```powershell
ps5-ffpfsc-renamer rename "D:\PS5\FFPFSC"
```

## License

No project license has been selected yet. A final license choice should be made before public distribution, together with the third-party dependency review.
