# PS5-FFPFSC-Renamer

Windows utility for scanning PS5 `.ffpfsc` files, detecting game metadata (including PPSA / Title ID), previewing a safe filename, and batch-renaming files without modifying their contents.

## Project status

**v0.1.0 development preview.**

The first milestone is intentionally conservative: **read-only analysis first, rename only after an explicit preview**.

Windows CI currently validates the full Python source, unit tests, and a synthetic MkPFS round-trip that creates a small `.ffpfsc`, extracts only `sce_sys/param.json`, and verifies the detected metadata.

## Goals

- Scan one folder or an entire folder tree for `*.ffpfsc` files.
- Read only the minimum metadata needed from each container.
- Detect the PS5 Title ID / PPSA when available.
- Display title and version when available.
- Preview the proposed filename before making any changes.
- Rename files in batch without rewriting or recompressing the `.ffpfsc` payload.
- Detect duplicate target names and other filename collisions before renaming.
- Leave unrecognized or invalid files untouched.
- Keep the metadata reader separate from the GUI and rename engine.

## Planned filename formats

Default:

```text
PPSA01285.ffpfsc
```

Optional formats planned for later versions:

```text
PPSA01285 - Returnal.ffpfsc
PPSA01285 - Returnal - v01.000.ffpfsc
```

## Safety principles

The application never renames a file merely because a PPSA-like string appears somewhere in binary data. Metadata must come from the verified `sce_sys/param.json` extraction path.

Before any rename, the program checks that:

- the source file exists;
- the detected Title ID is valid;
- the destination filename is valid;
- the destination does not already exist;
- two scanned files do not resolve to the same destination;
- source and destination are not already the same path.

The GUI enables the rename action only after a completed scan with no blocked/error entries and then asks for explicit confirmation.

## Legal & Responsible Use

> ⚠️ **Homebrew & Personal Backup Tool**
>
> PS5-FFPFSC-Renamer is intended for lawful homebrew use and for managing personal backup images created from games or content that you legally own and have dumped yourself.
>
> The project does **not** download or distribute games, decrypt retail packages, provide encryption or license keys, bypass DRM or license checks, distribute copyrighted PlayStation files, or include firmware, exploits or payloads.
>
> Users are responsible for complying with the laws and license terms that apply in their country. This project is not affiliated with, sponsored by, or endorsed by Sony Interactive Entertainment.

## Windows quick start

Python 3.11+ is currently required for the development preview.

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
- scanned/ready/blocked summary cards;
- folder browser and recursive scan option;
- metadata library table;
- proposed filename preview;
- explicit rename confirmation.

The visual direction is inspired by modern PS5 homebrew utilities, while the layout and implementation in this repository are original.

## Architecture

```text
src/ps5_ffpfsc_renamer/
├── cli.py              # command-line entry point
├── gui.py              # Windows desktop interface
├── scanner.py          # folder/file discovery
├── metadata.py         # normalized metadata model
├── ffpfsc_reader.py    # metadata extraction adapter
├── rename_plan.py      # dry-run and collision checks
├── renamer.py          # explicit filesystem rename operation
└── theme.py            # original dark-violet ttk theme
```

### MkPFS integration

The first implementation uses the external MkPFS command-line interface to cherry-pick `sce_sys/param.json` from an image:

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
- [x] Initial Windows GUI
- [x] Synthetic `.ffpfsc` end-to-end test
- [x] Windows development launcher

### v0.2.0

- [ ] Drag & drop
- [ ] Rename operation log / undo guidance
- [ ] Configurable filename formats
- [ ] Cover art / richer library metadata
- [ ] User-selectable MkPFS executable path

### v1.0.0

- [ ] Windows executable distribution strategy
- [ ] Automated Windows build
- [ ] Tested error handling on large libraries
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

Apply a validated rename plan explicitly:

```powershell
ps5-ffpfsc-renamer rename "D:\PS5\FFPFSC"
```

## License

No project license has been selected yet. A final license choice should be made before public distribution, together with the third-party dependency review.
