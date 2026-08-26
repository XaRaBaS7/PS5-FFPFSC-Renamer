# Feedback receiver deployment

`feedback_receiver.php` is the minimal HTTPS receiver for the in-app **Feedback & Bug Report** flow.

## Requirements

- PHP 8.1+ behind HTTPS.
- A writable storage directory, preferably outside the public document root.
- Set environment variable `PS5_FFPFSC_FEEDBACK_DIR` to that directory when possible.

The receiver accepts only POSTed JSON, limits request size, validates report schema/category/ID and writes the report atomically. It does not require or expose a GitHub token.

After deployment, configure the Windows build with the final HTTPS endpoint. Until an endpoint is configured, **Send report** still saves the sanitized report safely in the local feedback queue.

Do not place API tokens, GitHub personal-access tokens or hosting credentials in the desktop source or packaged executable.
