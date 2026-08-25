# Changelog

All notable changes to PS5 FFPFSC Renamer are documented here.

## [0.4.1] - 2026-08-26

### Fixed

- Synchronized the runtime `ps5_ffpfsc_renamer.__version__` value with the packaged project version.
- The Windows About dialog now reports the same release version as the ZIP/tag instead of the stale `0.4.0.dev1` development value.
- Added an automated regression test that fails CI whenever `__version__` and `pyproject.toml` diverge.

### Unchanged

- No changes to FFPFSC parsing, MkPFS integration, rename planning, pre-flight checks, post-rename verification, Smart Folder behavior, rollback, Undo, Live Watch, Game Details or Naming Profiles.

## [0.4.0] - 2026-08-25

### Smart Library

- Optional **Live Library Watch** for selected roots with 15/30/60/120 second intervals.
- Live Watch checks only path, size and modification time; MkPFS is launched only after a real library change triggers a scan.
- Live Watch reports **Added / Removed / Modified** changes separately in the Activity Log.
- Temporarily unavailable drives are reported without clearing or corrupting the current library view.
- Live Watch is disabled by default so archival HDDs are not woken unnecessarily.

### Game Details

- New collapsible **Game details** workspace linked to the selected result row.
- Selective MkPFS extraction of only `sce_sys/param.json` and `sce_sys/icon0.png` rather than the full FFPFSC payload.
- Details view shows icon, title, Title ID/PPSA, content version, master version, FFPFSC size, Renamer status, data source and path.
- Raw formatted `param.json` tab with clipboard copy.
- Detail loading is asynchronous, debounced and cancellable so quickly moving through the results does not keep obsolete disk reads running.
- Dedicated details/artwork cache under App Data.
- Cache Manager reports details-cache entry count, valid/stale entries and disk usage, with prune and clear actions.
- Details cache is migrated after Rename **and Undo** instead of forcing a new selective extraction.
- Multi-selection shows an in-memory summary (count, total size, unique Title IDs and status distribution) without invoking MkPFS.

### Naming

- Reusable **Naming Profiles** that can be applied without rescanning the library.
- Bundled profiles for PPSA-only compatibility, PPSA + Title, Title + PPSA, full archive naming and Title + Version + PPSA.
- User-created profiles are stored persistently in App Data and can be updated or deleted.
- Custom filename separator support, persisted with the rest of the builder configuration and included in profiles.

### Insights & maintenance

- New **Library Statistics** window generated entirely from current in-memory results.
- Shows file count, total/average known size, unique Title IDs, duplicate groups, status distribution, largest games and details-cache usage.
- New details-cache statistics/pruning helpers and tests.
- Operation History now explicitly closes each SQLite connection after use, preventing lingering Windows handles on the journal database.

### Rename safety

- New **Tools → Rename safety self-test...** runs real filesystem rename tests only against disposable temporary `.ffpfsc` files.
- The self-test covers File-only rename/Undo, Smart loose-file organization/Undo, Smart existing-folder rename/Undo, collision protection and late-batch-collision rollback.
- Temporary self-test payloads are SHA-256 checked before/after to verify that rename operations do not alter their bytes.
- Generated rename operations perform a fresh **pre-flight** immediately before filesystem mutation, catching destinations that appeared after the original preview.
- Rename confirmation shows READY count, represented data size, file path changes, folders to create/rename and blocked rows.
- Successful generated renames receive fast **post-rename identity verification** using file size plus filesystem device/file ID when available, with lightweight sampled-fingerprint fallback.
- Pre-flight, post-verification, transactional rollback and persistent Ctrl+Z Undo form separate safety layers.
- Automatic tests exercise the temporary-filesystem self-test and pre-flight/post-verification logic on Windows CI.

### Documentation & quality

- README contains a versioned application Preview near the top of the document.
- Added `docs/SCREENSHOT_POLICY.md` and an automated CI check: visible GUI changes must refresh the canonical README preview before merge.
- Final v0.4 preview reflects Smart Library, Live Watch, Naming Profiles, Game Details and rename-safety state.
- README Credits distinguish runtime dependencies, build tools and related/inspiration projects.
- Expanded test coverage for Smart Library settings, Live Watch snapshots, Game Details cache/migration, naming profiles, custom separators, library statistics, rename safety and the canonical GUI entrypoint.

### Performance

- Game artwork/JSON is loaded on demand instead of during the main scan.
- Cached details survive Rename and Undo through cache-key migration.
- Batch/multi-selection inspection never starts unnecessary MkPFS processes.
- Existing SQLite verified/failure caching, batch lookups and iterative `os.scandir()` discovery remain active.
- Post-rename verification uses filesystem identity when available rather than hashing complete multi-gigabyte images.

### Safety

- All v0.3 transactional rename, collision, Undo and selected-root protections remain in force.
- FFPFSC contents are never rewritten or recompressed by these features.
- Late destination collisions are blocked by the fresh pre-flight instead of relying only on the earlier UI preview.
- Runtime batch failures still trigger rollback of already-completed steps.

## [0.3.1] - 2026-08-25

### Fixed

- MkPFS helper processes now run silently on Windows without opening a console window for every scanned file.
- The same hidden-process behavior is used by normal metadata reads, diagnostics and MkPFS engine tests.

### Added

- Integrated collapsible **Activity Log** at the bottom of the application.
- Timestamped `INFO`, `CACHE`, `MKPFS`, `OK`, `WARN` and `ERROR` events.
- Persistent rolling activity log under `%LOCALAPPDATA%\PS5-FFPFSC-Renamer\activity.log`.
- Activity Log copy/clear/show/hide actions.
- Dual analysis progress display:
  - real determinate **Overall scan** progress;
  - animated **Current activity** bar while discovery/cache/MkPFS work is active.
- Expanded Credits & Acknowledgements in the README for runtime dependencies, build tools and related PS5 tooling projects.

### Changed

- Moved the source-development launcher from root `RUN.bat` to `tools\dev\RUN_DEV.bat` so the repository root better reflects the packaged end-user experience.
- README clearly distinguishes development files from the standalone Windows release package.

## [0.3.0] - 2026-08-25

### Added

- Automatic scan of previously saved library folders at application startup.
- Always-visible **Scan now / F5** action even when automatic scanning is disabled.
- Central **Options** window with General, Scan & Performance, Naming, Cache and MkPFS settings.
- Configurable startup/Browse/Add-folder autoscan behavior.
- Configurable relative/full path display and window-geometry persistence.
- Optional automatic pruning of cache records whose files no longer exist.
- Persistent operation history with undo support for rename transactions.
- `Ctrl+Z` undo, `F5` scan, `Ctrl+A` select-all and `Ctrl+E` export shortcuts.
- CSV and JSON library export for all rows or only visible/filtered results.
- Library Health report.
- Cache Manager and MkPFS Engine Manager entries in the desktop Tools menu.
- Sortable result columns with persisted ascending/descending order.
- Total size of visible results shown beside the result count.
- Negative cache for unchanged MkPFS failures so persistent PARTIAL/ERROR files do not get re-parsed on every scan.
- Branded procedural in-app icon set for Browse, Add folder, Scan, Options, Cache, Engine, Undo, Export and Health actions.
- Branded Windows application icon embedded in packaged EXE builds.

### Performance

- Replaced recursive `Path.glob()` discovery with iterative `os.scandir()` traversal for lower Windows filesystem overhead.
- Avoids following directory symlinks/reparse points during recursive discovery.
- Batch SQLite metadata-cache lookups replace one connection/query cycle per FFPFSC file.
- Batch failure-cache lookups avoid unnecessary MkPFS launches for unchanged problematic files.
- Multi-root scans continue when one selected drive/folder is temporarily unavailable instead of failing the whole library.

### Reliability & Safety

- Batch rename is transactional: if a later item fails, previously completed items are rolled back automatically.
- Smart-folder operations report incomplete rollback explicitly instead of hiding a partially restored filesystem state.
- Undo validates destinations and refuses to overwrite files/folders created after the original rename.
- Folders created by the app are removed during undo only when they are empty.
- Selected library roots remain protected from Smart-folder renaming.

### Changed

- Restored libraries become immediately useful after reopening the app; Browse is no longer required just to trigger a scan.
- The old scan control that could be visually squeezed out is replaced by an always-visible dedicated action row.
- Advanced actions are consolidated under `File / Edit / Tools / Help` menus and the Options window so the main library remains focused on scan results.

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