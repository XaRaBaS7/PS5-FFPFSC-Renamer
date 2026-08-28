# PS5 FFPFSC Renamer v0.5.0 — Library Workflow & Reliability Release

v0.5.0 is a major desktop workflow and reliability update. It keeps the existing rename-safety model intact while adding a canonical non-versioned desktop architecture, multi-root/offline handling, scan-change tracking, library health tools, duplicate management, feedback reporting and official project branding.

## v0.5.0 hotfix refresh

The downloadable Windows package for this same v0.5.0 release is refreshed from the current `main` source after the UX, MkPFS memory-safety and flat-root organization validation. The historical `v0.5.0` tag remains anchored to the original release commit; no v0.5.1 is introduced.

- Fixed automatic startup scans so the modern shell no longer configures a stale, already-destroyed central `Options` Tk widget.
- Added a one-second live scan clock with progress percentage, elapsed time and ETA estimation so long MkPFS operations remain visibly active.
- The final action now reads `Apply changes` / `Apply changes (N)` and uses a distinct green enabled state while continuing to route through the existing safe rename entry point.
- Reworked the bottom project credit into a spaced, inset `PROJECT BY XaRaBaS ↗` element.
- Replaced ambiguous Folder handling with three result-oriented library modes: **One folder per game**, **All files in library root** and **Keep current structure**, with a real Before/After example.
- **All files in library root** now performs the requested final layout: each READY `.ffpfsc` is renamed/moved into its selected library root first, then old source directories are removed only when they are actually empty. Cleanup uses non-recursive empty-directory removal, never deletes the selected root, and retains any folder containing another file, hidden file or subdirectory.
- Flat-root empty-folder cleanup is journaled with the rename transaction so late-failure rollback and `Ctrl+Z` Undo can recreate removed source directories before restoring files to their original paths.
- The dark **Review changes** dialog reports flat-root file moves and empty-folder cleanup candidates before Apply.
- Replaced the native Windows rename prompt with a dark in-app **Review changes** dialog that explains the organization mode, READY items, path changes and folder operations before Apply.
- Replaced the old Options tab strip with a modern vertical settings navigation.
- Reworked the main workspace into compact **Library setup** / **Rename builder** tabs so only one configuration panel occupies vertical space at a time and the results list remains the dominant area.
- The main workspace opens on **Library setup** by default and requests a taller results Treeview for normal library browsing.
- Restored the original styled **File / Edit / Tools / Help** command row instead of replacing it with the native Windows menubar. Each visible Menubutton now owns a cloned popup menu and delegates commands to the canonical product menu, fixing the Windows click-with-no-popup issue while preserving the previous look. The native menu remains attached until the styled row has been built successfully, providing a safe fallback.
- Moved the creator credit into a separated footer/status area with its own spacing and divider; the old results-area overlay is suppressed.
- Refreshed the canonical README Preview so it represents the current tabbed layout, styled command row, larger library list, separated footer and current library-organization controls.
- Strengthened README Preview CI enforcement: material changes under the modern `ui/` mixins, desktop shell, theme/icons or branding now fail CI unless `docs/screenshots/app-preview.svg` is refreshed in the same change set.
- Lowered MkPFS child-process priority on Windows and moved helper stdout/stderr to temporary files with bounded diagnostic-tail reads.
- Added a bounded-memory metadata path in the bundled helper: PFSC block offsets use small 64 KiB pages and exFAT lookup walks only root → `sce_sys` → `param.json` instead of materializing the complete offset table and recursive exFAT tree.
- Packaged metadata reads no longer fall back automatically to full recursive MkPFS unpack when a layout is unsupported; the item is reported unavailable rather than risking unbounded RAM use.
- Packaged Game Details use a dedicated bounded `read-game-details` path for `sce_sys/param.json` and optional `sce_sys/icon0.png`.
- Game Details are not started merely by selecting rows while the details pane is hidden; detailed extraction is explicitly on demand.
- Bundled helper processes are monitored with a 1 GiB working-set safety threshold and stopped with a clear diagnostic if an unexpected image would otherwise exceed it.
- Helper processes are tracked and cleaned up on cancellation, timeout and application shutdown, preventing an orphaned `mkpfs-helper.exe` from continuing after the desktop exits.
- The metadata/details paths remain read-only, keep timeout/cancellation behavior and never rewrite or recompress `.ffpfsc` files.
- Windows packaging keeps both the exact MkPFS 0.0.9 source distribution and the helper wrapper source under `source/third-party/`.
- Removed the temporary one-shot v0.5.0 release-repair script/workflow from the maintained project tree.

## Highlights

- Canonical `desktop.py` / `desktop_core.py` runtime with focused feature mixins and legacy GUI modules retained only for compatibility.
- Multi-root library workflow with explicit `ONLINE`, `OFFLINE`, `ERROR` and `UNKNOWN` root states.
- Read-only preservation of previous rows from temporarily unavailable USB/NAS roots without feeding stale rows into rename plans.
- Scan snapshot comparison with `ADDED`, `REMOVED` and `CHANGED` tracking, plus direct selection actions for added/changed results.
- `HEALTHY`, `PROBLEMS` and `OFFLINE` filters and a compact in-memory status summary.
- Library Health actions and a non-destructive Duplicate Manager with exact Title ID focus and explicit sampled comparison.
- Rename-plan manifest export, scan-performance export and portable settings backup/restore.
- Privacy-aware **Help → Feedback & Bug Report...** workflow with sanitized diagnostics, crash capture and a local queue before any network submission attempt.
- Official PS5 FFPFSC Renamer branding for the Windows executable, taskbar/window icon, sidebar, About dialog and README.

## Safety and reliability

- FFPFSC payload contents are never rewritten or recompressed by rename/library-management operations.
- `PARTIAL` metadata remains display-only and cannot be auto-renamed.
- Destination collisions continue to block affected rename steps.
- Selected library roots remain protected from folder rename and removal.
- Batch rename retains fresh pre-flight validation, transactional rollback, post-rename identity verification and persistent conservative Undo.
- **All files in library root** moves/renames each READY file first and only then attempts non-recursive removal of the old source directory. Only directories left completely empty are removed; any directory containing another file, hidden file or subdirectory remains untouched. Empty parent directories may be removed upward only until the selected library root boundary, which is never removed.
- Flat-root cleanup candidates are included in the rename manifest and pre-flight summary; cleanup directory steps are recorded so rollback/Undo can rebuild the original directory path before restoring a file.
- `OFFLINE` rows are informational/read-only and filesystem-backed actions are blocked until the root is available and scanned successfully again.
- Failed or cancelled scans restore the previous successful library view as stale/read-only context instead of clearing it.
- Automatic cache pruning runs only in the background when every configured root is confirmed online and remains scoped to current configured roots.
- `Ctrl+Z` and `Ctrl+A` preserve normal text-editing behavior while focus is inside text-entry controls.

## Feedback and crash reports

The application can create a sanitized technical report containing app/platform version, aggregate root/library state, last-scan metrics and recent Activity Log lines. Library paths, common user-profile/AppData/temp locations and usernames are redacted. FFPFSC payload contents, credentials and metadata-cache contents are not included.

Every report is written atomically to the local feedback queue first. Production submission targets `https://www.youstoreinformatica.com/ffpfsc/ps5-ffpfsc-feedback.php`; if the receiver is unavailable the queued copy is preserved and normal application workflows continue.

## Performance and quality

- Combined verified/failure cache lookup and one reused filesystem-stat pass.
- Iterative `os.scandir()` discovery and overlapping recursive-root collapse.
- Aggregate scan-phase timing without per-file report I/O.
- Bundled metadata and Game Details reads avoid the generic MkPFS 0.0.9 full-tree `--deep --only` path in packaged builds.
- Regression coverage simulates a PFSC table with ten million blocks and verifies that initialization reads only bounded 64 KiB offset pages rather than materializing a table proportional to image size.
- Tests verify that unsupported packaged metadata layouts do not enter the heavy fallback, Game Details stay idle until requested, and registered helper processes are terminated on cleanup.
- Flat-root safety tests verify move-before-cleanup ordering, nested empty-folder cleanup, preservation of non-empty folders, shared-folder behavior, selected-root protection, rollback and persistent Undo.
- The Rename Safety Self-Test now includes a real disposable flat-root move, empty-directory cleanup, content hash verification and Undo cycle.
- Deterministic synthetic scanner regression coverage with 1,024 `.ffpfsc` files.
- Expanded tests for offline-root preservation, stale-view guards, feedback redaction/transport, branding assets, release gates, scan snapshots and desktop MRO.

## Windows package

Extract the complete archive and keep these executables together:

```text
PS5-FFPFSC-Renamer.exe
mkpfs-helper.exe
```

The release archive contains the application, `mkpfs-helper.exe`, `_internal/`, the required documentation/license files and `source/third-party/` with MkPFS source material. Branding is bundled under `_internal/assets/brand`; redundant root `assets/` and `app-icon.png` are not included. No separate Python installation is required.

## First-use recommendation

Before processing a complete library, validate the workflow with one non-critical `.ffpfsc` file or a file backed up independently. Keep an external backup of original files whenever practical.
