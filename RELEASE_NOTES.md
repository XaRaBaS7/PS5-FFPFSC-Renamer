# PS5 FFPFSC Renamer v0.4.1 — Version Sync Hotfix

v0.4.1 is a small maintenance release that fixes the version reported inside the Windows application.

## Fixed

- The packaged application now reports **v0.4.1** consistently in the About dialog.
- `pyproject.toml` and `ps5_ffpfsc_renamer.__version__` are synchronized.
- Added an automated regression test that fails CI if the runtime version and project/package version diverge again.

## Unchanged

There are no changes to FFPFSC parsing, MkPFS integration, rename planning, pre-flight checks, post-rename verification, Smart Folder behavior, rollback, Undo, Live Watch, Game Details or Naming Profiles compared with v0.4.0.

FFPFSC payloads are still never rewritten or recompressed by rename/library-management operations.

## Windows package

Extract the complete archive and keep these executables together:

```text
PS5-FFPFSC-Renamer.exe
mkpfs-helper.exe
```

No separate Python installation is required.
