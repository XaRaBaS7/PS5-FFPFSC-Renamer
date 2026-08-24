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

## Architecture

```text
src/ps5_ffpfsc_renamer/
├── app.py              # application entry point
├── scanner.py          # folder/file discovery
├── metadata.py         # normalized metadata model
├── ffpfsc_reader.py    # container metadata reader
├── rename_plan.py      # dry-run and collision checks
└── renamer.py          # explicit filesystem rename operation
```

The metadata reader is kept separate from the GUI so that parsing can be tested independently before enabling batch rename.

## Development roadmap

### v0.1.0

- [x] Repository bootstrap
- [ ] Folder scanner
- [ ] Metadata model
- [ ] `.ffpfsc` metadata extraction proof of concept
- [ ] PPSA validation
- [ ] Rename dry-run
- [ ] Collision detection
- [ ] Command-line test interface

### v0.2.0

- [ ] Windows GUI
- [ ] Drag & drop
- [ ] Batch selection
- [ ] Rename log
- [ ] Configurable filename formats

### v1.0.0

- [ ] Standalone Windows executable
- [ ] Automated Windows build
- [ ] Tested error handling on large libraries

## Important

This project does not include game content, keys, firmware, exploits, or copyrighted PS5 files. It is intended to operate only on files the user already possesses.

## License

No license has been selected yet.
