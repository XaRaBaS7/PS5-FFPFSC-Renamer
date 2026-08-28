# PS5 FFPFSC Renamer v0.5.0b — PS5 FTP Compatibility Preview

v0.5.0b hardens the PS5 FTP workspace introduced in v0.5.0a after checking the current etaHEN FTP and ShadowMountPlus implementations at source level. This remains an **alpha / prerelease** intended for testing and feedback; v0.5.0 remains the current stable release.

## FTP compatibility verified against current implementations

- etaHEN's integrated FTP implementation uses port **1337** by default and supports the operations required by the workspace: passive FTP, `MLSD`, `NLST`, `SIZE`, `REST`, `RETR`, `RNFR` and `RNTO`.
- The preferred Explorer path therefore continues to use `MLSD` on the integrated etaHEN server.
- Added a Unix `LIST` parser fallback for standalone PS5 `ftpsrv` variants that do not expose `MLSD`/`NLST`, allowing the remote Explorer to remain usable with both server families.
- Recursive remote discovery is now bounded by both result count and directory count so an unexpectedly broad PS5 root cannot turn into an unbounded traversal.
- Small ShadowMount configuration/status files are size-checked before retrieval when FTP `SIZE` is available.

## ShadowMountPlus rename safety

- Current ShadowMountPlus source recognizes `.ffpfsc` as an image type by extension, so changing only the descriptive base filename does not remove `.ffpfsc` recognition.
- Remote rename now checks all known filename/path-sensitive ShadowMount files: `/data/shadowmount/config.ini`, `/data/shadowmount/autotune.ini`, `/data/shadowmount/manual.lst` and `/data/shadowmount/manual.status`.
- The utility reproduces ShadowMountPlus' current PFSC mount-point rule (`filename stem + FNV-1a(full source path)` under `/mnt/shadowmnt/pfsc`).
- If the exact mount point for the selected `.ffpfsc` currently exists, the rename is refused. The image must be unmounted/stopped before retrying.
- Existing destination-collision preflight, extension preservation and post-rename source/destination verification remain active.
- `.ffpfsc` payload contents are never rewritten or recompressed by FTP rename operations.

## PS5 FTP workspace

- Separate **Local Library** and **PS5 FTP** workspaces keep remote operations visually distinct from local filesystem operations.
- Manual PS5 host/IP, configurable FTP port, username and password are supported; credentials remain session-only.
- **Discover PS5** performs bounded scanning on private local LAN/Wi-Fi ranges for the selected FTP port.
- The themed **PS5 Explorer** supports remote path navigation, Up/Refresh controls, folder browsing and recursive `.ffpfsc` enumeration.
- Manual remote `.ffpfsc` rename includes confirmation, collision preflight and post-rename verification.

## Desktop fixes carried forward

- Fixed the Windows result-row selection path that could surface the automatic **Feedback & Bug Report** dialog when clicking or right-clicking a library row.
- Increased the default result-list height.
- Configuration panels auto-collapse after inactivity to return vertical space to the library list.
- **Scan now F5** remains available beside the progress controls even while configuration is collapsed.
- Existing local `Undo` / `Ctrl+Z`, collision protection, PARTIAL blocking, pre-flight validation and transaction rollback remain unchanged.

## Current preview scope

Connection, discovery, browsing, `.ffpfsc` enumeration and conservative remote rename are implemented. Automatic Title ID / title / version extraction directly from a remote multi-gigabyte `.ffpfsc` is still intentionally not performed by downloading the complete image. The next engineering stage is bounded random-access metadata reading over FTP using etaHEN's `REST`/`RETR` support, isolated from the Explorer control connection.

The FTP path has been validated against source implementations and automated tests, but a real-console test is still required because network conditions, payload versions and console storage layouts can vary. Test first with a non-critical or independently backed-up image.

Project: https://github.com/XaRaBaS7/PS5-FFPFSC-Renamer

PS5 FFPFSC Renamer is an independent homebrew/personal-backup utility and is not affiliated with Sony Interactive Entertainment.
