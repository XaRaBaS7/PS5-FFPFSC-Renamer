# PS5 FFPFSC Renamer v0.4.0 — Smart Library

v0.4.0 evolves PS5 FFPFSC Renamer from a safe metadata-driven renamer into a richer local library workspace while preserving the original rule: **FFPFSC payloads are never rewritten or recompressed by rename/library-management operations.**

## Rename Safety Self-Test

A new **Tools → Rename safety self-test...** command validates the rename engine without touching the user's library. It creates disposable dummy `.ffpfsc` files in an isolated temporary directory and performs real Windows filesystem operations.

The self-test covers:

- file-only rename and Undo;
- Smart loose-file folder creation/move and Undo;
- Smart existing-folder rename and Undo;
- collision protection with no overwrite;
- a late collision during a batch, including automatic rollback of an earlier completed rename;
- SHA-256 checks on the temporary payloads to prove their bytes remain unchanged through the tests.

The same suite also runs automatically in CI.

## Rename pre-flight and post-verification

Generated rename operations now have an additional safety layer around the existing transactional rollback and persistent Undo.

Immediately before filesystem changes, the app performs a fresh **pre-flight** that checks sources and destinations again. This can catch a destination that appeared after the preview but before the user confirmed the rename.

The confirmation summary shows the number of READY files, represented data size, file-path changes, folders to create/rename and blocked rows that will remain untouched.

After the rename, the app verifies that each destination represents the same filesystem object using file size plus Windows filesystem identity (`st_dev` / `st_ino`) when available. If a platform does not expose a usable file ID, it falls back to the existing lightweight sampled fingerprint. This verification does not require reading an entire large FFPFSC image.

## Smart Library Watch

A new optional Live Watch can observe selected library roots for added, removed or changed `.ffpfsc` files.

- disabled by default;
- configurable 15 / 30 / 60 / 120 second interval;
- compares only path, size and modification timestamp;
- does not continuously parse images with MkPFS;
- distinguishes Added / Removed / Modified changes in the Activity Log;
- a real change triggers the normal cached scan;
- unavailable drives are reported without clearing the current library.

This keeps the feature useful on SSD/NVMe while remaining respectful of archival HDDs and removable drives.

## Game Details and artwork

Selecting one game can now show a dedicated Details workspace. MkPFS selectively extracts only:

```text
sce_sys/param.json
sce_sys/icon0.png
```

The panel displays the game icon, title, Title ID/PPSA, content/master versions, file size, Renamer status, path and metadata source. A second tab exposes formatted raw `param.json` with a Copy action.

Details loading is asynchronous, debounced and cancellable. Quickly navigating the results does not leave obsolete metadata reads running.

A dedicated App Data cache stores extracted `param.json` and `icon0.png`. Cache Manager can show valid/stale entries and disk usage, prune stale entries or clear this cache. Rename and Undo operations migrate valid details-cache entries to the correct path so details remain instant after filesystem changes.

When multiple games are selected, the Details panel switches to an in-memory summary with count, total known size, unique Title IDs and status distribution without starting MkPFS.

## Naming Profiles

The Filename Builder now supports reusable profiles. Bundled examples include:

```text
ShadowMount / PPSA only
PPSA + Title
Title + PPSA
Full archive
Title + Version + PPSA
```

Custom profiles remember active components, order, compact/original version format, `v` prefix, folder handling and the new filename separator setting. User profiles are persistent and can be updated or deleted without rescanning the library.

## Library Statistics

`Tools → Library statistics...` creates an instant report from the current in-memory scan:

- number of files;
- total and average known size;
- unique Title IDs;
- duplicate groups/files;
- status distribution;
- largest games;
- details-cache usage;
- unavailable-root count.

No additional MkPFS read is performed to produce these statistics.

## Performance and quality

- Game artwork is loaded on demand instead of during the main library scan.
- Details cache is reused and migrated after rename and Undo operations.
- Multi-selection details never creates unnecessary MkPFS work.
- Existing SQLite verified/failure caching, batch lookups and `os.scandir()` discovery remain active.
- Operation History SQLite connections are explicitly closed after each transaction/read, avoiding lingering Windows file handles.
- README includes a versioned application preview.
- CI enforces preview freshness whenever visible GUI files are changed.
- Expanded automated tests cover Live Watch, details caching/migration, naming profiles, custom separators, library statistics, real temporary filesystem rename/Undo, collision rollback, rename pre-flight and post-verification.

## Existing v0.3 reliability remains

v0.4 retains:

- silent MkPFS helper execution;
- dual scan progress;
- Activity Log;
- multi-root libraries;
- autoscan on startup/Browse/Add folder;
- sortable/searchable/filterable results;
- duplicate comparison;
- transactional batch rename + rollback;
- persistent operation history + Ctrl+Z Undo;
- CSV/JSON export;
- Library Health;
- collision/overwrite protection;
- Recycle Bin integration.

## Windows package

Extract the complete archive and keep these executables together:

```text
PS5-FFPFSC-Renamer.exe
mkpfs-helper.exe
```

No separate Python installation is required.

## Responsible use

This software is intended for lawful homebrew use and personal backups of content you legally own and dumped yourself. It does not download games, decrypt retail packages, provide keys, bypass DRM/license checks or distribute copyrighted PlayStation content.
