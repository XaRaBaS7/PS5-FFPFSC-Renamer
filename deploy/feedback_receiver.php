<?php
/*
 * Minimal HTTPS feedback receiver for PS5 FFPFSC Renamer.
 * Deploy behind TLS. Configure PS5_FFPFSC_FEEDBACK_DIR to a writable directory
 * that is preferably outside the public document root.
 */

declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    header('Allow: POST');
    echo json_encode(['ok' => false, 'error' => 'method_not_allowed']);
    exit;
}

$maxBytes = 131072;
$length = isset($_SERVER['CONTENT_LENGTH']) ? (int) $_SERVER['CONTENT_LENGTH'] : 0;
if ($length > $maxBytes) {
    http_response_code(413);
    echo json_encode(['ok' => false, 'error' => 'payload_too_large']);
    exit;
}

$raw = file_get_contents('php://input', false, null, 0, $maxBytes + 1);
if ($raw === false || $raw === '' || strlen($raw) > $maxBytes) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'invalid_payload']);
    exit;
}

$data = json_decode($raw, true);
if (!is_array($data)) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'invalid_json']);
    exit;
}

$reportId = isset($data['report_id']) ? (string) $data['report_id'] : '';
$schema = isset($data['schema_version']) ? (int) $data['schema_version'] : 0;
$category = isset($data['category']) ? (string) $data['category'] : '';
$summary = isset($data['summary']) ? trim((string) $data['summary']) : '';

if ($schema !== 1 || !preg_match('/^[A-Za-z0-9._-]{8,100}$/', $reportId)) {
    http_response_code(422);
    echo json_encode(['ok' => false, 'error' => 'invalid_report_identity']);
    exit;
}

$allowedCategories = ['Bug report', 'Feature request', 'Suggestion', 'General feedback'];
if (!in_array($category, $allowedCategories, true) || $summary === '') {
    http_response_code(422);
    echo json_encode(['ok' => false, 'error' => 'invalid_report_fields']);
    exit;
}

$storage = getenv('PS5_FFPFSC_FEEDBACK_DIR');
if ($storage === false || trim($storage) === '') {
    $storage = __DIR__ . DIRECTORY_SEPARATOR . 'feedback-data';
}

if (!is_dir($storage) && !mkdir($storage, 0700, true) && !is_dir($storage)) {
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => 'storage_unavailable']);
    exit;
}

$destination = rtrim($storage, '/\\') . DIRECTORY_SEPARATOR . $reportId . '.json';
$temporary = $destination . '.tmp-' . bin2hex(random_bytes(6));
$encoded = json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
if ($encoded === false || file_put_contents($temporary, $encoded . PHP_EOL, LOCK_EX) === false) {
    @unlink($temporary);
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => 'write_failed']);
    exit;
}

if (!rename($temporary, $destination)) {
    @unlink($temporary);
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => 'commit_failed']);
    exit;
}

http_response_code(202);
echo json_encode(['ok' => true, 'report_id' => $reportId]);
