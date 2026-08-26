# PS5 FFPFSC Renamer v0.5.0 — Library Workflow & Reliability Release

v0.5.0 is a major desktop workflow and reliability update. It keeps the existing rename-safety model intact while adding a canonical non-versioned desktop architecture, multi-root/offline handling, scan-change tracking, library health tools, duplicate management, feedback reporting and official project branding.

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
- Selected library roots remain protected from Smart-folder rename.
- Batch rename retains fresh pre-flight validation, transactional rollback, post-rename identity verification and persistent conservative Undo.
- `OFFLINE` rows are informational/read-only and filesystem-backed actions are blocked until the root is available and scanned successfully again.
- Failed or cancelled scans restore the previous successful library view as stale/read-only context instead of clearing it.
- Automatic cache pruning runs only in the background when every configured root is confirmed online and remains scoped to current configured roots.
- `Ctrl+Z` and `Ctrl+A` preserve normal text-editing behavior while focus is inside text-entry controls.

## Feedback and crash reports

The application can create a sanitized technical report containing app/platform version, aggregate root/library state, last-scan metrics and recent Activity Log lines. Library paths, common user-profile/AppData/temp locations and usernames are redacted. FFPFSC payload contents, credentials and metadata-cache contents are not included.

Every report is written atomically to the local feedback queue first. When a project HTTPS feedback receiver is configured, **Send report** submits the same payload in the background; if the receiver is unavailable the queued copy is preserved and normal application workflows continue.

## Performance and quality

- Combined verified/failure cache lookup and one reused filesystem-stat pass.
- Iterative `os.scandir()` discovery and overlapping recursive-root collapse.
- Aggregate scan-phase timing without per-file report I/O.
- Deterministic synthetic scanner regression coverage with 1,024 `.ffpfsc` files.
- Expanded tests for offline-root preservation, stale-view guards, feedback redaction/transport, branding assets, release gates, scan snapshots and desktop MRO.

## Windows package

Extract the complete archive and keep these executables together:

```text
PS5-FFPFSC-Renamer.exe
mkpfs-helper.exe
```

The package includes the official branding assets, README, CHANGELOG, license/notices and the MkPFS source archive required by the release packaging workflow. No separate Python installation is required.

## First-use recommendation

Before processing a complete library, validate the workflow with one non-critical `.ffpfsc` file or a file backed up independently. Keep an external backup of original files whenever practical.
