# Changelog

All notable changes to PS5 FFPFSC Renamer are documented here.

## [0.5.0] - 2026-08-27

### Hotfix refresh

- Fixed startup scans against the modern shell so a stale, already-destroyed central `Options` Tk widget can no longer abort startup with `TclError`; the live sidebar control is preferred and stale-widget configuration is ignored safely.
- Added a live one-second scan clock with progress percentage, elapsed time and ETA estimation so long MkPFS reads remain visibly active even while one file is taking time to complete.
- Renamed the final action to `Apply changes` / `Apply changes (N)` and gave the enabled action a distinct green treatment while retaining the existing `self._rename` / `RenameSafetyMixin` execution path.
- Added the discreet clickable `Created by XaRaBaS` credit to the main desktop shell without adding it to README or About.
- Lowered MkPFS child-process priority on Windows and redirected helper stdout/stderr to temporary files with bounded diagnostic tail reads instead of retaining unbounded process output in Python memory.
- Added a bundled-helper metadata path that reads PFSC block offsets lazily and walks only root → `sce_sys` → `param.json`, avoiding the complete PFSC offset-list materialization and recursive exFAT tree construction used by the generic MkPFS 0.0.9 deep-unpack path.
- The low-memory metadata path is read-only, preserves cancellation/timeout behavior and falls back to the stock MkPFS extractor only for unsupported legacy layouts; `.ffpfsc` files are never rewritten or recompressed.
- Windows packaging now keeps the exact MkPFS 0.0.9 source distribution plus the bundled helper wrapper source under `source/third-party/`; redundant root `assets/` and `app-icon.png` remain forbidden.
- Removed the temporary one-shot v0.5.0 release-repair script and workflow from the maintained tree.

### Architecture

- Replaced the runtime `gui_vXX` inheritance chain with the canonical `desktop.py` / `desktop_core.py` desktop path.
- Extracted feature-specific desktop behavior into focused non-versioned mixins while retaining legacy GUI modules only for compatibility.
- Added regression coverage for desktop method-resolution order and legacy-module isolation.
- Canonical `ui/` modules are guarded from re-introducing runtime imports of versioned `gui_vXX` modules.

### Library workflow

- Added scan snapshot comparison with `ADDED`, `REMOVED` and `CHANGED` tracking.
- Added `ADDED`, `CHANGED`, `HEALTHY`, `PROBLEMS` and `OFFLINE` result filters.
- Added direct Edit-menu selection commands for `ADDED`, `CHANGED` and combined added/changed rows without rescanning or invoking MkPFS.
- Added root-state reporting for removable/network locations and asynchronous availability checks.
- Added scan-change reporting to the Tools menu and Activity Log.
- Added a compact persistent status summary for visible/selected rows, online roots, problems, duplicate groups and scan changes.
- Added multi-selection clipboard actions for unique PPSA/Title ID values and `Title ID - Title` lists.
- Added direct Library Health actions for focusing problem/duplicate rows, managing roots and targeted PARTIAL/ERROR re-analysis.
- Added a non-destructive Duplicate Manager with in-memory Title ID group summaries and explicit sampled comparison.
- Added focused selection commands for all problem rows and all duplicate rows, including `Ctrl+Shift+P` and `Ctrl+Shift+D`.
- Duplicate Manager group focus now selects rows by exact normalized Title ID rather than generic search matches.
- Failed/cancelled scans restore the previous successful library view as stale/read-only context instead of clearing the table.
- Partially successful multi-root scans preserve previous rows belonging to unavailable roots as `OFFLINE` while keeping fresh rows from online roots.
- `OFFLINE` rows never enter generated rename plans and filesystem-backed actions remain disabled until their root is scanned successfully again.
- Scan-diff baseline state for unavailable roots is preserved so a disconnected USB/NAS is not reported falsely as removed/changed content.

### Feedback and diagnostics

- Added **Help → Feedback & Bug Report...** for bug reports, feature requests, suggestions and general feedback without requiring email composition.
- Added privacy-aware diagnostic payloads containing app/platform version, aggregate root/library state, scan metrics and recent Activity Log lines.
- Configured library roots, common profile/AppData/temp paths and usernames are redacted before local storage or submission.
- FFPFSC payload contents, credentials and metadata-cache contents are never included in feedback reports.
- Unexpected Tk callback exceptions are captured into a local feedback queue and reopen the report dialog with the crash details prefilled.
- Feedback is written atomically to the local queue before an HTTPS submission attempt; unsuccessful delivery leaves the report queued without blocking scan or rename workflows.
- Direct submission accepts HTTPS endpoints only, with localhost HTTP allowed solely for receiver testing; no API token or project credential is embedded in the executable.

### Branding

- Added the official PS5 FFPFSC Renamer symbol and horizontal project logo as versioned brand assets.
- Replaced generated placeholder artwork with `.png`/multi-resolution `.ico` output derived from the official symbol.
- Added official window/taskbar branding, sidebar branding and a branded About dialog.
- Added the project logo to the README and refreshed the canonical application preview.
- Windows release packaging includes the brand assets used by the local README and application bundle.

### Performance

- Combined verified metadata and failure-cache lookup into a single batch operation.
- Reused one filesystem-stat pass for cache validation, file-size display and scan snapshots.
- Collapsed overlapping recursive library roots to avoid duplicate directory traversal.
- Added scan-phase timing for root checks, discovery, cache resolution, MkPFS processing and total duration.
- Added JSON/CSV export of aggregate metrics from the last completed scan without rescanning the library.
- Duplicate Manager group summaries use existing in-memory scan results; file samples are read only when comparison is requested explicitly.
- Root identity keys and relative-path rendering use lexical normalization so status/footer refreshes and table rendering do not resolve filesystem paths.
- Multi-root display matching selects the deepest configured root without per-row filesystem resolution and rejects similar path prefixes such as `PS5` versus `PS5-backup`.
- Automatic cache pruning is deferred off the Tk UI thread, runs only when every configured root is confirmed online, and probes only cache entries under currently configured roots.
- Added deterministic scanner regression coverage using 1,024 synthetic `.ffpfsc` files across multiple directories without timing-based assertions.

### Safety and exports

- Added CSV/JSON rename-plan manifest export before filesystem mutation.
- Rename manifests include source, destination, metadata, status, block reason and directory-operation information.
- Added portable JSON backup/restore for application settings only.
- Settings backup import is available under Options → General and validates format, schema, field types and unsupported keys before replacing current configuration.
- Settings restore applies library roots, MkPFS source, sorting and Live Watch runtime state immediately; caches, history, logs and FFPFSC files remain unchanged and no rename or automatic scan is started.
- Failed settings persistence attempts restore the previous runtime configuration rather than leaving a partially applied import.
- Duplicate Manager does not expose rename or delete operations; filesystem mutation remains behind the existing rename/Recycle Bin safety paths.
- Automatic cache pruning preserves cache records for historical or disconnected roots and is skipped when any configured root is offline, unavailable or unchecked.
- Root availability probing now falls back safely when path resolution fails instead of allowing a normalization error to abort the probe.
- Root state produced by optimized scans preserves the configured root identity even when the effective path resolves through a junction/symlink alias.
- Enabling automatic cache pruning from Options takes effect in the running application while settings import remains non-destructive to cache data.
- `Ctrl+Z` and `Ctrl+A` keep normal text-editing behavior when focus is in Entry/Text/Combobox/Spinbox controls, preventing accidental filesystem Undo from the Search field.
- The UI advertises persistent `Ctrl+Z` Undo only when Operation History successfully records the completed rename transaction.

### Documentation and quality

- Updated the canonical README preview for the v0.5 desktop layout.
- Revised README text to use concise technical terminology and explicit dependency/reference roles.
- Added a prominent first-use precaution recommending validation with one non-critical or independently backed-up `.ffpfsc` before processing a complete library, together with a user-data responsibility disclaimer.
- Documented settings backup location/restore behavior, scan-performance export, Library Health actions and offline-root preservation.
- Documented Duplicate Manager behavior and focused problem/duplicate selection shortcuts.
- Added a dedicated README section for feedback, feature requests, bug/crash reporting, privacy/redaction and queued delivery behavior.
- Added tests for feedback redaction/transport, offline-root merge/baseline behavior, stale-view filesystem guards and official brand-asset integrity.
- Added stable-release gates that reject development version strings and require official brand assets in the Windows release package.

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
