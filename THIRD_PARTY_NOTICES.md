# Third-party notices

PS5 FFPFSC Renamer is licensed separately under the MIT License. The projects below remain subject to their own upstream licenses and attribution requirements.

## MkPFS

PS5 FFPFSC Renamer uses **MkPFS 0.0.9** as an external helper for read-only inspection/extraction of supported PFS/PFSC images.

- Project: `PSBrew/MkPFS`
- Upstream: https://github.com/PSBrew/MkPFS
- PyPI package: `mkpfs==0.0.9`
- License: **GNU General Public License v3.0 (GPL-3.0)**

The Windows release keeps MkPFS in a **separate helper executable** (`mkpfs-helper.exe`). The main renamer communicates with it through command-line arguments and captured stdout/stderr.

For release compliance and reproducibility, the build workflow also places the exact MkPFS 0.0.9 source distribution downloaded from PyPI under:

```text
source/third-party/
```

inside the Windows release archive.

## Send2Trash

The desktop application uses **Send2Trash** to move files to the operating-system Recycle Bin instead of permanently deleting them.

- Project: https://github.com/arsenetar/send2trash
- Runtime dependency: `send2trash>=1.8.3`

See the upstream project/package metadata for its applicable license text and notices.

## PyInstaller

Windows standalone executables are produced by **PyInstaller** in GitHub Actions.

- Project: https://github.com/pyinstaller/pyinstaller

PyInstaller is a build/packaging tool; it is not presented as part of the PS5 FFPFSC Renamer source license. See the upstream project for its license and exception terms.

## Related projects / acknowledgements

The following projects are **not bundled as dependencies** by PS5 FFPFSC Renamer, but are acknowledged as useful references in the PS5 FFPFS/PFSC tooling ecosystem:

- PS5 exFAT Image Builder — https://github.com/kerrdec97/ps5-exfat-builder
- PS5 FFPFSC PRO — https://github.com/KINGDKAK/PS5-FFPFSC-PRO
- PS5 FFPFS CLI — https://github.com/bizkut/ps5-ffpfs-cli

Acknowledgement does not imply code reuse, endorsement, affiliation or shared licensing.
