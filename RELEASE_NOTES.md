# PS5 FFPFSC Renamer v0.3.1

v0.3.1 is a focused Windows UX/reliability hotfix for the v0.3 series.

## Highlights

- **MkPFS now runs silently on Windows** during normal scans, diagnostics and engine tests. The helper still runs exactly as required, but no console/CMD windows are shown to the user.
- New integrated **Activity Log** at the bottom of the application with timestamped `INFO`, `CACHE`, `MKPFS`, `OK`, `WARN` and `ERROR` events.
- The Activity Log can be shown/hidden, copied or cleared and is also persisted as a rolling log under `%LOCALAPPDATA%\PS5-FFPFSC-Renamer\activity.log`.
- New **dual progress display**:
  - determinate Overall scan percentage;
  - animated Current activity bar for discovery/cache/MkPFS work.
- README now includes clear Credits & Acknowledgements for MkPFS, Send2Trash, PyInstaller and related PS5 tooling projects.
- The development launcher moved from root `RUN.bat` to `tools\dev\RUN_DEV.bat`; end users only need the standalone Windows release package.

## Why two progress bars?

The whole-library percentage can be measured accurately. MkPFS selective metadata extraction does not expose a trustworthy percentage for one individual FFPFSC file, so the app uses an animated activity bar instead of presenting a fabricated per-file percentage.

## Windows package

Extract the complete archive and keep these executables together:

```text
PS5-FFPFSC-Renamer.exe
mkpfs-helper.exe
```

No separate Python installation is required.

## Safety

Rename behavior is unchanged from v0.3.0: FFPFSC contents are never rewritten/recompressed, collisions are blocked, batch operations are rollback-protected and Undo refuses unsafe overwrites.

## Responsible use

This software is intended for lawful homebrew use and personal backups of content you legally own and dumped yourself. It does not download games, decrypt retail packages, provide keys, bypass DRM, or distribute copyrighted PlayStation content.
