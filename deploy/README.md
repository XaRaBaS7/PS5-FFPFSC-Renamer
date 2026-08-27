# Feedback receiver deployment

The production feedback subsystem is deployed as a self-contained `/ffpfsc/` area.

## Production layout

```text
public_html/
└── ffpfsc/
    ├── .htaccess
    ├── ps5-ffpfsc-feedback.php
    ├── admin-config.php          # server-only, never commit
    ├── admin/
    │   └── index.php
    └── feedback-data/
        ├── .htaccess
        ├── index.html
        └── *.json
```

The v0.5.0 desktop build probes:

```text
https://www.youstoreinformatica.com/ffpfsc/ps5-ffpfsc-feedback.php
```

The private management panel is:

```text
https://www.youstoreinformatica.com/ffpfsc/admin/
```

## Receiver

`deploy/ffpfsc/ps5-ffpfsc-feedback.php` exposes a lightweight `GET`/`HEAD` health check and accepts feedback through `POST` JSON. It limits request size, validates report schema/category/ID/text length, treats duplicate report IDs idempotently and writes reports atomically.

A successful health response is:

```json
{"ok":true,"service":"ps5-ffpfsc-feedback","schema_version":1}
```

The desktop app verifies this identity before enabling **Send report**. If the receiver is unavailable, the report remains in the local Windows feedback queue.

## Admin authentication

Copy:

```text
admin-config.example.php -> admin-config.php
```

Generate a password hash with PHP:

```text
php -r "echo password_hash('YOUR_PASSWORD', PASSWORD_DEFAULT), PHP_EOL;"
```

Put that hash in `admin-config.php`. The real `admin-config.php` must remain server-only and must never be committed to GitHub.

The admin panel provides:

- New / In analysis / Resolved / Ignored workflow states;
- report detail with description, diagnostics, exception traceback and recent activity;
- JSON download;
- report deletion;
- **Prepare GitHub issue**, which opens a pre-filled GitHub issue without embedding a token in the website.

## Storage

By default reports are written to:

```text
public_html/ffpfsc/feedback-data/
```

That directory is denied from direct web access by `.htaccess` and directory listing is disabled. For stronger isolation, production hosting may set:

```text
PS5_FFPFSC_FEEDBACK_DIR=/path/outside/public_html/ps5-ffpfsc-feedback
```

The receiver and admin panel should point to the same storage location if an external directory is used.

## Development override

Development/test builds can override the production endpoint with:

```text
PS5_FFPFSC_FEEDBACK_ENDPOINT=https://example.tld/path/feedback_receiver.php
```

Never place API tokens, GitHub personal-access tokens, hosting passwords or other secrets in the desktop source, packaged executable, or public repository.
