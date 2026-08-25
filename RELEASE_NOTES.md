# PS5 FFPFSC Renamer v0.2.0

The first packaged Windows release focuses on safe library management and fast repeat scans.

## Highlights

- Scan one or more FFPFSC folders as a single library.
- Reopen the app with your previous folders and filename preferences restored.
- Reuse cached metadata so unchanged images normally skip MkPFS on later scans.
- Search and filter large libraries, including duplicate Title IDs.
- Build output names in any order using PPSA / title / version.
- Smart folder mode can create or rename a dedicated game folder while protecting selected library roots.
- Right-click one or multiple rows for rename, Explorer, re-analysis, diagnostics and Recycle Bin actions.
- Compare duplicate Title IDs using path, size, version and lightweight sampled fingerprints.
- Diagnose images that do not expose the expected wrapped exFAT layout.

## Windows package

The Windows archive is intended to run without a separate Python installation. It includes a separate `mkpfs-helper.exe` for MkPFS operations and ships the corresponding MkPFS 0.0.9 source distribution under `source/third-party/`.

## Important safety behavior

- Rename operations never rewrite or recompress `.ffpfsc` contents.
- Automatic rename plans use only metadata verified from internal `sce_sys/param.json`.
- `PARTIAL` metadata inferred from a filename/folder is display-only.
- Existing target files/folders are not overwritten automatically.
- Delete commands move files to the Windows Recycle Bin after confirmation.

## Responsible use

This software is intended for homebrew and personal backups of content you legally own and dumped yourself. It does not download games, decrypt retail packages, provide keys, bypass DRM, or distribute copyrighted PlayStation content.
