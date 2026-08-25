# Changelog

All notable changes to PS5 FFPFSC Renamer are documented here.

## [0.2.0] - 2026-08-25

### Added

- Persistent multi-folder libraries stored in `%LOCALAPPDATA%\PS5-FFPFSC-Renamer\settings.json`.
- Automatic scan after **Browse** and **Add folder**.
- Full preference persistence: workers, recursive scan, filename builder, component order, version format, folder mode, result filter and window geometry.
- Search box and result filters (`READY`, `UNCHANGED`, `PARTIAL`, `COLLISION`, `INVALID`, `ERROR`, `DUPLICATES`).
- File-size column.
- Extended multi-selection with Ctrl/Shift and right-click operations for selected files.
- Right-click actions for rename, Explorer, diagnostics, re-analysis, copy path/Title ID and Recycle Bin.
- Duplicate Title ID comparison with size, version, path and lightweight sampled fingerprints.
- `PARTIAL` metadata display when MkPFS cannot verify metadata but a PPSA can be inferred from the file/folder name.
- Read-only MkPFS diagnostics using `inspect` and `tree --deep`.
- Smart folder handling for loose files and already-organized game folders.
- Persistent SQLite metadata cache with quick fingerprint fallback for moved/renamed files.
- Progress, ETA, cancellation and configurable workers.
- Standalone Windows build pipeline with a separate MkPFS helper executable.

### Changed

- Filename builder is compact and reorderable instead of preset-only.
- Scan result table is the dominant area of the interface and shows relative paths when useful.
- Collision explanations are kept out of the visible Status column and shown on hover / context actions.
- MkPFS errors no longer flood the Title column with tracebacks.

### Safety

- FFPFSC contents are never rewritten or recompressed by rename operations.
- Automatic/batch rename only uses metadata verified from internal `sce_sys/param.json`.
- `PARTIAL` metadata inferred from paths is display-only.
- Existing destinations are never overwritten or merged automatically.
- Delete actions use the Windows Recycle Bin and require confirmation.

## [0.1.x] - Development series

Initial scanner, metadata reader, cache, filename planning, GUI and Smart folder handling development.
