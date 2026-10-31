<?php

declare(strict_types=1);

use PostBop\Companion\Config;
use PostBop\Companion\Database;
use PostBop\Companion\OAuthSessionRepository;

require dirname(__DIR__) . '/vendor/autoload.php';

try {
    Config::load();

    $database = new Database();

    $method = $_SERVER['REQUEST_METHOD'];
    $path = parse_url(
        $_SERVER['REQUEST_URI'],
        PHP_URL_PATH
    );

    if ($method === 'GET' && $path === '/') {
        header('Content-Type: application/json');
        echo json_encode([
            'service' => 'postbop-companion',
            'status' => 'ok',
        ]);

        exit;
    }

    if ($method === 'POST' && $path === '/oauth/session') {
        $body = json_decode(
            file_get_contents('php://input'),
            true
        );

        $stateHash = $body['state_hash'] ?? null;

        if (
            !is_string($stateHash) ||
            !preg_match('/^[a-f0-9]{64}$/', $stateHash)
        ) {
            header('Content-Type: application/json');
            http_response_code(400);

            echo json_encode([
                'error' => 'invalid_state_hash',
            ]);

            exit;
        }

        $repository = new OAuthSessionRepository(
            $database->connection()
        );

        $repository->create(
            $stateHash,
            (int) Config::get('OAUTH_SESSION_TTL')
        );

        header('Content-Type: application/json');
        http_response_code(201);

        echo json_encode([
            'status' => 'created',
        ]);

        exit;
    }

    if ($method === 'GET' && $path === '/oauth/callback') {
        $state = $_GET['state'] ?? null;
        $code = $_GET['code'] ?? null;
        $oauthError = $_GET['error'] ?? null;

        if (!is_string($state) || $state === '') {
            http_response_code(400);
            header('Content-Type: text/html; charset=utf-8');

            echo '<h1>PostBop authorization failed</h1>';
            echo '<p>The OAuth state value was missing.</p>';

            exit;
        }

        $stateHash = hash('sha256', $state);

        $repository = new OAuthSessionRepository(
            $database->connection()
        );

        if (is_string($code) && $code !== '') {
            $completed = $repository->completeWithCode(
                $stateHash,
                $code
            );
        } elseif (is_string($oauthError) && $oauthError !== '') {
            $completed = $repository->completeWithError(
                $stateHash,
                $oauthError
            );
        } else {
            http_response_code(400);
            header('Content-Type: text/html; charset=utf-8');

            echo '<h1>PostBop authorization failed</h1>';
            echo '<p>Buffer returned neither an authorization code nor an error.</p>';

            exit;
        }

        if (!$completed) {
            http_response_code(400);
            header('Content-Type: text/html; charset=utf-8');

            echo '<h1>PostBop authorization failed</h1>';
            echo '<p>This authorization session is invalid, expired, or has already been used.</p>';

            exit;
        }

        header('Content-Type: text/html; charset=utf-8');

        echo '<h1>Authorization received</h1>';
        echo '<p>You can return to PostBop.</p>';

        exit;
    }

    header('Content-Type: application/json');
    http_response_code(404);

    echo json_encode([
        'error' => 'not_found',
    ]);
} catch (Throwable $exception) {
    header('Content-Type: application/json');
    http_response_code(500);

    echo json_encode([
        'error' => 'internal_server_error',
    ]);
}