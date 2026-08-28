# README preview policy

`docs/screenshots/app-preview.svg` is the canonical visual preview used by the project README.

## Non-optional rule

Every pull request or release refresh that materially changes the visible desktop UI must update the preview in the same change set. The preview must represent the interface users will actually receive; a stale preview must not be merged into `main`.

Examples that require a preview refresh:

- new, removed or reorganized panels, tabs, menus or buttons;
- layout, spacing, footer or table-size changes;
- new visible features or changed user-facing behavior/help text;
- theme, colors, branding or icon changes;
- result-table structure changes;
- progress, log, details, confirmation-dialog or Options UI changes.

Backend-only changes with no visible desktop effect do not require a preview change.

## CI enforcement

`tools/check_readme_preview.py` is run by GitHub Actions. It treats the canonical desktop shell, `ui/` mixins, legacy/current GUI modules, theme/icon files and branding assets as visible UI paths. If one of those paths changes without `docs/screenshots/app-preview.svg` changing in the same PR/commit, CI must fail.

The checker itself has regression coverage so new `ui/` mixin changes cannot silently bypass this rule.

## Release rule

Before a tagged release or a refresh of the existing `v0.5.0` package, the preview must represent the final release UI. Development previews may show the current feature branch, but stale screenshots must not be merged or published.
