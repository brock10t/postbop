<?php
declare(strict_types=1);

namespace PostBop\Companion;

use RuntimeException;

class BufferAccountVerifier {
    public function verify( string $accessToken ): ?string {
        if ($accessToken === '') {
            return null;
        }

        $payload = json_encode([ 'query' => 'query { account { id } }', ], JSON_THROW_ON_ERROR);

        $curl = curl_init( 'https://api.buffer.com' );

        if ($curl === false) {
            throw new RuntimeException( 'buffer_verification_unavailable' );
        }

        try {
            curl_setopt_array($curl, [
                CURLOPT_POST => true,
                CURLOPT_POSTFIELDS => $payload,
                CURLOPT_HTTPHEADER => [
                    'Content-Type: application/json',
                    'Authorization: Bearer ' . $accessToken,
                ],
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_CONNECTTIMEOUT => 5,
                CURLOPT_TIMEOUT => 15,
                CURLOPT_FOLLOWLOCATION => false,
                CURLOPT_SSL_VERIFYPEER => true,
                CURLOPT_SSL_VERIFYHOST => 2,
            ]);

            $response = curl_exec( $curl );

            $status = (int) curl_getinfo( $curl, CURLINFO_HTTP_CODE );

        } finally {
            curl_close( $curl );
        }

        if ( $response === false ) {
            throw new RuntimeException( 'buffer_verification_unavailable' );
        }

        if ($status === 401 || $status === 403) {
            return null;
        }

        if ($status !== 200) {
            throw new RuntimeException( 'buffer_verification_unavailable' );
        }

        $result = json_decode( $response, true );

        if (!is_array($result)) {
            throw new RuntimeException( 'invalid_buffer_response' );
        }

        if ( !empty( $result['errors'] ) ) {
            foreach ( $result['errors'] as $error ) {
                $code = $error['extensions']['code'] ?? '';

                if ( in_array( $code, ['UNAUTHORIZED', 'FORBIDDEN'], true ) ) {
                    return null;
                }
            }

            throw new RuntimeException( 'buffer_verification_unavailable' );
        }

        $accountId = $result['data']['account']['id'] ?? null;

        if ( !is_string($accountId) || $accountId === '' ) {
            throw new RuntimeException( 'invalid_buffer_response' );
        }

        return $accountId;
    }
}