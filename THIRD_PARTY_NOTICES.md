# Third-party notices

## MkPFS

PS5 FFPFSC Renamer uses **MkPFS 0.0.9** as an external helper for read-only inspection/extraction of supported PFS/PFSC images.

- Project: `PSBrew/MkPFS`
- License: **GNU General Public License v3.0 (GPL-3.0)**
- Upstream project: https://github.com/PSBrew/MkPFS
- PyPI package: `mkpfs==0.0.9`

The Windows release build keeps MkPFS in a **separate helper executable** (`mkpfs-helper.exe`). The main renamer communicates with it through the command line and captured stdout/stderr.

For release compliance and reproducibility, the build workflow also places the exact MkPFS 0.0.9 source distribution downloaded from PyPI under:

`source/third-party/`

inside the Windows release archive. That source distribution contains the upstream licensing and source material for the bundled helper dependency.

PS5 FFPFSC Renamer itself is licensed separately under the MIT License; see `LICENSE`.

## send2trash

The desktop application uses `Send2Trash` to move files to the operating system Recycle Bin instead of permanently deleting them from the context menu.

See the installed package metadata/upstream project for its applicable license terms.
