# PS5 FFPFSC Renamer v0.3.0

v0.3.0 turns the renamer into a more complete Windows library-management utility, with faster repeat scans, safer rename transactions and a cleaner desktop workflow.

## Highlights

- Saved library folders can scan automatically as soon as the app starts.
- A dedicated **Scan now / F5** action always remains visible for manual refreshes.
- New **Options** center groups startup, scan/performance, naming, cache and MkPFS settings.
- Faster library discovery with `os.scandir()` and batch SQLite cache lookups.
- Unchanged PARTIAL/ERROR images now reuse a negative cache instead of launching MkPFS again every scan.
- Multi-root libraries keep scanning when one drive or folder is temporarily unavailable.
- Sort results by filename, PPSA, title, version, size, proposed output or status.
- Persistent operation history and **Undo last rename / Ctrl+Z**.
- CSV/JSON export and a Library Health report.
- Cache Manager and MkPFS Engine Manager are available from the Tools menu.
- New consistent in-app icon set plus a branded Windows EXE/taskbar icon.

## Safer rename transactions

Batch rename is now transactional. If a later item fails, earlier completed items are rolled back automatically. Smart-folder failures also report incomplete rollback explicitly instead of silently leaving an uncertain filesystem state.

Undo checks that the original destinations are still safe before moving anything back. It never overwrites newly-created files/folders, and app-created directories are removed only when empty.

## Performance

Repeat scans avoid unnecessary work through three paths:

1. verified metadata cache for unchanged images;
2. failure cache for unchanged images MkPFS could not parse previously;
3. batch SQLite lookup instead of opening/querying the cache separately for every file.

Recursive file discovery now uses iterative `os.scandir()` and does not follow directory symlinks/reparse points.

## Options

The Options window includes settings for:

- scan saved folders automatically on startup;
- scan automatically after Browse;
- scan automatically after Add folder;
- remember window size/position;
- show relative or full paths;
- include subfolders;
- worker count for HDD/SSD/NVMe;
- automatic pruning of missing cache records;
- filename preset/components/version format/folder handling;
- Cache Manager and MkPFS engine configuration.

## Windows package

The Windows archive runs without a separate Python installation. Keep the complete extracted folder together, including `mkpfs-helper.exe`. The application EXE now carries the project icon in Explorer and the taskbar.

The corresponding MkPFS 0.0.9 source distribution remains included under `source/third-party/`.

## Important safety behavior

- Rename operations never rewrite or recompress `.ffpfsc` contents.
- Automatic rename plans use only metadata verified from internal `sce_sys/param.json` or verified metadata cache entries.
- `PARTIAL` metadata inferred from filename/folder remains display-only.
- Existing target files/folders are not overwritten automatically.
- Selected library roots are protected from Smart-folder renaming.
- Delete actions continue to use the Windows Recycle Bin after confirmation.

## Responsible use

This software is intended for lawful homebrew use and personal backups of content you legally own and dumped yourself. It does not download games, decrypt retail packages, provide keys, bypass DRM, or distribute copyrighted PlayStation content.
