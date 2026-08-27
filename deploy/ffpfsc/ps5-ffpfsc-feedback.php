<?php
/*
 * HTTPS feedback receiver for PS5 FFPFSC Renamer.
 * Deploy behind TLS. Configure PS5_FFPFSC_FEEDBACK_DIR to a writable directory
 * that is preferably outside the public document root.
 */

declare(strict_types=1);

const FEEDBACK_SERVICE = 'ps5-ffpfsc-feedback';
const FEEDBACK_SCHEMA = 1;
const MAX_BYTES = 131072;
const MAX_SUMMARY = 500;
const MAX_DESCRIPTION = 24000;

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');

function respond(int $status, array $payload): never
{
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}

function text_length(string $value): int
{
    if (function_exists('mb_strlen')) {
        return mb_strlen($value, 'UTF-8');
    }
    return strlen($value);
}

$method = $_SERVER['REQUEST_METHOD'] ?? '';
if ($method === 'GET' || $method === 'HEAD') {
    if ($method === 'HEAD') {
        http_response_code(200);
        exit;
    }
    respond(200, [
        'ok' => true,
        'service' => FEEDBACK_SERVICE,
        'schema_version' => FEEDBACK_SCHEMA,
    ]);
}

if ($method !== 'POST') {
    header('Allow: GET, HEAD, POST');
    respond(405, ['ok' => false, 'error' => 'method_not_allowed']);
}

$length = isset($_SERVER['CONTENT_LENGTH']) ? (int) $_SERVER['CONTENT_LENGTH'] : 0;
if ($length > MAX_BYTES) {
    respond(413, ['ok' => false, 'error' => 'payload_too_large']);
}

$raw = file_get_contents('php://input', false, null, 0, MAX_BYTES + 1);
if ($raw === false || $raw === '' || strlen($raw) > MAX_BYTES) {
    respond(400, ['ok' => false, 'error' => 'invalid_payload']);
}

$data = json_decode($raw, true);
if (!is_array($data)) {
    respond(400, ['ok' => false, 'error' => 'invalid_json']);
}

$reportId = isset($data['report_id']) ? (string) $data['report_id'] : '';
$schema = isset($data['schema_version']) ? (int) $data['schema_version'] : 0;
$category = isset($data['category']) ? (string) $data['category'] : '';
$summary = isset($data['summary']) ? trim((string) $data['summary']) : '';
$description = isset($data['description']) ? (string) $data['description'] : '';

if ($schema !== FEEDBACK_SCHEMA || !preg_match('/^[A-Za-z0-9._-]{8,100}$/', $reportId)) {
    respond(422, ['ok' => false, 'error' => 'invalid_report_identity']);
}

$allowedCategories = ['Bug report', 'Feature request', 'Suggestion', 'General feedback'];
if (!in_array($category, $allowedCategories, true) || $summary === '') {
    respond(422, ['ok' => false, 'error' => 'invalid_report_fields']);
}
if (text_length($summary) > MAX_SUMMARY || text_length($description) > MAX_DESCRIPTION) {
    respond(422, ['ok' => false, 'error' => 'report_text_too_long']);
}

$storage = getenv('PS5_FFPFSC_FEEDBACK_DIR');
if ($storage === false || trim($storage) === '') {
    $storage = __DIR__ . DIRECTORY_SEPARATOR . 'feedback-data';
}

if (!is_dir($storage) && !mkdir($storage, 0700, true) && !is_dir($storage)) {
    respond(500, ['ok' => false, 'error' => 'storage_unavailable']);
}

/* Best-effort protection when fallback storage is inside an Apache web root. */
$denyFile = rtrim($storage, '/\\') . DIRECTORY_SEPARATOR . '.htaccess';
if (!file_exists($denyFile)) {
    @file_put_contents($denyFile, "Require all denied\nDeny from all\n", LOCK_EX);
}
$indexFile = rtrim($storage, '/\\') . DIRECTORY_SEPARATOR . 'index.html';
if (!file_exists($indexFile)) {
    @file_put_contents($indexFile, '', LOCK_EX);
}

$destination = rtrim($storage, '/\\') . DIRECTORY_SEPARATOR . $reportId . '.json';
if (file_exists($destination)) {
    respond(200, [
        'ok' => true,
        'service' => FEEDBACK_SERVICE,
        'report_id' => $reportId,
        'duplicate' => true,
    ]);
}

$temporary = $destination . '.tmp-' . bin2hex(random_bytes(6));
$encoded = json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
if ($encoded === false || file_put_contents($temporary, $encoded . PHP_EOL, LOCK_EX) === false) {
    @unlink($temporary);
    respond(500, ['ok' => false, 'error' => 'write_failed']);
}

if (!rename($temporary, $destination)) {
    @unlink($temporary);
    respond(500, ['ok' => false, 'error' => 'commit_failed']);
}

respond(202, [
    'ok' => true,
    'service' => FEEDBACK_SERVICE,
    'report_id' => $reportId,
]);
