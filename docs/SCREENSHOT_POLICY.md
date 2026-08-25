# README preview policy

`docs/screenshots/app-preview.svg` is the canonical visual preview used by the project README.

## Rule

Any pull request that materially changes the visible desktop UI must update the preview in the same pull request.

Examples that require a preview refresh:

- new or removed panels, tabs, menus or buttons;
- layout or spacing changes;
- new visible features;
- theme, colors or icon changes;
- result-table structure changes;
- progress/log/details UI changes.

The preview does not need to change for backend-only work that has no visible effect.

## Why this is enforced

The README should show the application users will actually receive, not a historical interface from an older release. CI checks GUI-related changes and reports an error when the preview was not updated in the same change set.

## Release rule

Before a tagged release, the preview must represent the final release UI. Development previews may show the current feature branch, but stale screenshots must not be merged into `main`.
