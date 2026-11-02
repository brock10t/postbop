<?php

declare(strict_types=1);

use PostBop\Companion\Config;
use PostBop\Companion\Database;
use PostBop\Companion\OAuthSessionRepository;
use PostBop\Companion\MediaCredentialRepository;
use PostBop\Companion\MediaStorage;
use PostBop\Companion\MediaUploadRepository;

require dirname(__DIR__) . '/vendor/autoload.php';

try {
    Config::load();

    $database = new Database();

    $method = $_SERVER['REQUEST_METHOD'];
    $path = parse_url( $_SERVER['REQUEST_URI'], PHP_URL_PATH );

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

        if ( !is_string($stateHash) || !preg_match('/^[a-f0-9]{64}$/', $stateHash) ) {
            header('Content-Type: application/json');
            http_response_code(400);
            echo json_encode([
                'error' => 'invalid_state_hash',
            ]);
            exit;
        }

        $repository = new OAuthSessionRepository( $database->connection() );

        $repository->create( $stateHash, (int) Config::get('OAUTH_SESSION_TTL') );

        header('Content-Type: application/json');
        http_response_code(201);

        echo json_encode([
            'status' => 'created',
        ]);

        exit;
    }

    if ($method === 'POST' && $path === '/oauth/result') {
        $body = json_decode(
            file_get_contents('php://input'),
            true
        );

        $state = $body['state'] ?? null;

        if ( !is_string($state) || !preg_match('/^[A-Za-z0-9_-]{32,256}$/', $state) ) {
            header('Content-Type: application/json');
            http_response_code(400);
            echo json_encode([
                'error' => 'invalid_state',
            ]);
            exit;
        }

        $stateHash = hash('sha256', $state);

        $repository = new OAuthSessionRepository( $database->connection() );

        $result = $repository->claimResult( $stateHash );

        header('Content-Type: application/json');

        switch ($result['status']) {

            case 'pending':
                http_response_code(202);
                echo json_encode([
                    'status' => 'pending',
                ]);
                break;

            case 'complete':
                http_response_code(200);
                echo json_encode([
                    'status' => 'complete',
                    'code' => $result['code'],
                    'media_token' => $result['media_token'],
                ]);
                break;

            case 'error':
                http_response_code(200);
                echo json_encode([
                    'status' => 'error',
                    'error' => $result['error'],
                ]);
                break;

            case 'expired':
                http_response_code(410);
                echo json_encode([
                    'error' => 'session_expired',
                ]);
                break;

            case 'claimed':
                http_response_code(410);
                echo json_encode([
                    'error' => 'result_already_claimed',
                ]);
                break;

            default:
                http_response_code(404);
                echo json_encode([
                    'error' => 'session_not_found',
                ]);
                break;
        }

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

    if ( $method === 'POST' && $path === '/media/upload' ) {
        $authorization = $_SERVER['HTTP_AUTHORIZATION'] ?? '';

        if ( !preg_match( '/^Bearer\s+(.+)$/i', $authorization, $matches ) ) {
            header( 'Content-Type: application/json' );
            http_response_code( 401 );
            echo json_encode([ 'error' => 'authentication_required' ]);
            exit;
        }

        $credentialRepository = new MediaCredentialRepository( $database->connection() );

        $credential = $credentialRepository->authenticate( $matches[1] );

        if ( $credential === null ) {
            header( 'Content-Type: application/json' );
            http_response_code( 401 );
            echo json_encode([ 'error' => 'invalid_media_credential' ]);
            exit;
        }

        if ( !isset($_FILES['image']) ) {
            header( 'Content-Type: application/json' );
            http_response_code( 400 );
            echo json_encode([ 'error' => 'image_required' ]);
            exit;
        }

        $storage = new MediaStorage( Config::get( 'MEDIA_STORAGE_PATH' ), (int) Config::get( 'MEDIA_MAX_BYTES' ) );

        $storedFile = null;

        try {
            $storedFile = $storage->storeUploadedFile( $_FILES['image'] );

            $uploadRepository = new MediaUploadRepository( $database->connection() );

            $uploadId = $uploadRepository->create( 
                (int) $credential['id'], $storedFile, 
                (int) Config::get( 'MEDIA_RETENTION_DAYS' )
            );
        } catch ( RuntimeException $exception ) {
            if ( $storedFile !== null ) {
                $storage->deleteStoredFile( $storedFile[ 'storage_filename' ] ); }

            $status = $exception->getCode();
            if ( !in_array( $status, [400, 413, 415, 500], true ) ) {
                $status = 500;
            }

            header( 'Content-Type: application/json' );
            http_response_code($status);
            echo json_encode([
                'error' => (
                    $status === 500
                    ? 'internal_server_error'
                    : $exception->getMessage()
                ),
            ]);

            exit;
        }

        $publicUrl = sprintf( '%s/%s', rtrim( Config::get( 'MEDIA_PUBLIC_BASE_URL' ), '/' ),
                                $storedFile[ 'storage_filename' ] );

        header( 'Content-Type: application/json' );
        http_response_code(201);
        echo json_encode([
            'status' => 'created',
            'media_id' => $uploadId,
            'url' => $publicUrl,
            'mime_type' => $storedFile['mime_type'],
            'byte_size' => $storedFile['byte_size'],
        ]);

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