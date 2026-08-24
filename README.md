# PS5-FFPFSC-Renamer

Windows utility for scanning PS5 `.ffpfsc` files, detecting game metadata (including PPSA / Title ID), previewing a safe filename, and batch-renaming files without modifying their contents.

## Project status

Early development / proof of concept.

The first milestone is intentionally conservative: **read-only analysis first, rename only after an explicit preview**.

## Goals

- Scan one folder or an entire folder tree for `*.ffpfsc` files.
- Read only the minimum metadata needed from each container.
- Detect the PS5 Title ID / PPSA when available.
- Display title and version when available.
- Preview the proposed filename before making any changes.
- Rename files in batch without rewriting or recompressing the `.ffpfsc` payload.
- Detect duplicate target names and other filename collisions before renaming.
- Leave unrecognized or invalid files untouched.
- Keep a log of rename operations.

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

The application should never rename a file automatically just because a PPSA-like string is found somewhere in the binary data. Metadata must come from a verified parser/extractor path.

Before any rename, the program will perform a dry run and check:

- source file exists;
- detected Title ID is valid;
- destination filename is valid on Windows;
- destination does not already exist;
- two scanned files do not resolve to the same destination;
- source and destination are not the same path.

## Legal & Responsible Use

> ⚠️ **Homebrew & Personal Backup Tool**
>
> PS5-FFPFSC-Renamer is intended for lawful homebrew use and for managing personal backup images created from games or content that you legally own and have dumped yourself.
>
> The project does **not** download or distribute games, decrypt retail packages, provide encryption or license keys, bypass DRM or license checks, distribute copyrighted PlayStation files, or include firmware, exploits or payloads.
>
> Users are responsible for complying with the laws and license terms that apply in their country. This project is not affiliated with, sponsored by, or endorsed by Sony Interactive Entertainment.

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

The metadata reader is kept separate from the GUI so that parsing can be tested independently before enabling batch rename.

### MkPFS integration

The first implementation uses the external MkPFS command-line interface to cherry-pick `sce_sys/param.json` from an image:

```text
mkpfs unpack game.ffpfsc temp-dir --deep --only sce_sys/param.json --no-progress
```

MkPFS documents that `--only` reads only matching entries, making this suitable for metadata inspection without extracting the complete image.

MkPFS is a separate GPL-3.0 project and is **not copied into this repository**. Install it separately when using the metadata reader.

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

### v0.2.0

- [ ] Drag & drop
- [ ] Rename log
- [ ] Configurable filename formats
- [ ] Cover art / richer library metadata

### v1.0.0

- [ ] Standalone Windows executable
- [ ] Automated Windows build
- [ ] Tested error handling on large libraries

## Development

Python 3.11+ is recommended.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
pip install -U mkpfs
pytest
```

Run the GUI:

```powershell
ps5-ffpfsc-renamer-gui
```

Run a dry scan from the command line:

```powershell
ps5-ffpfsc-renamer scan "D:\PS5\FFPFSC"
```

Apply a previously validated rename plan explicitly:

```powershell
ps5-ffpfsc-renamer rename "D:\PS5\FFPFSC"
```

## License

No project license has been selected yet.
