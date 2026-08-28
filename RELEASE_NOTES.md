# PS5 FFPFSC Renamer v0.5.0a — PS5 FTP Preview

v0.5.0a starts the PS5 FTP workspace requested by the community while keeping the existing local-library workflow and rename-safety model intact. This is an **alpha / prerelease** intended for testing and feedback; v0.5.0 remains the current stable release.

## PS5 FTP workspace

- Added separate **Local Library** and **PS5 FTP** workspaces in the sidebar so remote operations are never confused with local filesystem operations.
- Added manual PS5 host/IP, configurable FTP port, username and password fields. Port **1337** is preselected for the common etaHEN FTP setup.
- FTP credentials are kept in application memory for the current session and are not written into project settings or feedback reports.
- Added bounded **Discover PS5** scanning for the selected FTP port across private local `/24` LAN/Wi-Fi networks only.
- Added a themed **PS5 Explorer** with remote path navigation, Up/Refresh controls, folder browsing and recursive `.ffpfsc` enumeration.
- Added manual remote `.ffpfsc` rename with confirmation, destination-collision preflight and post-rename verification.
- Remote rename requires the `.ffpfsc` extension to remain intact and does not rewrite or recompress the game image.
- Known exact-path references in `/data/shadowmount/config.ini` and `/data/shadowmount/manual.lst` are checked before remote rename. When a reference is found, the operation is blocked instead of leaving an obviously stale ShadowMount path.

## Desktop fixes carried into v0.5.0a

- Fixed the Windows result-row selection path that could surface the automatic **Feedback & Bug Report** dialog when clicking or right-clicking a library row.
- Increased the default result-list height.
- Configuration panels auto-collapse after inactivity to return vertical space to the library list.
- **Scan now F5** remains available beside the progress controls even while configuration is collapsed.
- Existing `Undo` / `Ctrl+Z`, collision protection, PARTIAL blocking, pre-flight validation and local transaction rollback remain unchanged.

## Current alpha scope

The first FTP increment intentionally focuses on safe connection, discovery, browsing, `.ffpfsc` enumeration and verified remote rename. Automatic Title ID / title / version extraction directly from a remote multi-gigabyte `.ffpfsc` is not faked by downloading the complete image in the background; selective remote metadata access is the next stage of the FTP work.

Please test this prerelease on non-critical or independently backed-up files first. Reports about FTP-server compatibility, PS5 folder layouts, ShadowMount configurations and UI workflow are especially useful.

Project: https://github.com/XaRaBaS7/PS5-FFPFSC-Renamer

PS5 FFPFSC Renamer is an independent homebrew/personal-backup utility and is not affiliated with Sony Interactive Entertainment.
