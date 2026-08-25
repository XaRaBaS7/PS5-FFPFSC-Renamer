# PS5 FFPFSC Renamer v0.4.0 — Smart Library

v0.4.0 evolves PS5 FFPFSC Renamer from a safe metadata-driven renamer into a richer local library workspace while preserving the original rule: **FFPFSC payloads are never rewritten or recompressed by rename/library-management operations.**

## Smart Library Watch

A new optional Live Watch can observe selected library roots for added, removed or changed `.ffpfsc` files.

- disabled by default;
- configurable 15 / 30 / 60 / 120 second interval;
- compares only path, size and modification timestamp;
- does not continuously parse images with MkPFS;
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

A dedicated App Data cache stores extracted `param.json` and `icon0.png`. Cache Manager can show valid/stale entries and disk usage, prune stale entries or clear this cache. Rename operations migrate valid details cache entries to the destination path so details remain instant after a rename.

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
- Details cache is reused and migrated after rename operations.
- Multi-selection details never creates unnecessary MkPFS work.
- Existing SQLite verified/failure caching, batch lookups and `os.scandir()` discovery remain active.
- README now includes a versioned application preview.
- CI enforces preview freshness whenever visible GUI files are changed.
- Expanded automated tests cover Live Watch, details caching and migration, naming profiles, custom separators and library statistics.

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
