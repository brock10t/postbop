<?php
declare(strict_types=1);

namespace PostBop\Companion;

use PDO;

class MediaCredentialRepository
{
    public function __construct( private PDO $connection ) {
    }

    public function issue( int $oauthSessionId ): array {
        $token = 'pbm_' . bin2hex( random_bytes(32) );

        $tokenHash = hash( 'sha256', $token );

        $statement = $this->connection->prepare(
            'INSERT INTO media_credentials (oauth_session_id,token_hash)
            VALUES (:oauth_session_id,:token_hash)'
        );

        $statement->execute([
            'oauth_session_id' => $oauthSessionId,
            'token_hash' => $tokenHash,
        ]);

        return [
            'id' => (int) $this->connection->lastInsertId(),
            'token' => $token,
        ];
    }

    public function authenticate( string $token ): ?array {
        if ( !preg_match( '/^pbm_[a-f0-9]{64}$/', $token ) ) {
            return null;
        }

        $tokenHash = hash( 'sha256', $token );

        $statement = $this->connection->prepare(
            'SELECT id, oauth_session_id, created_at, last_used_at
                FROM media_credentials
                WHERE token_hash = :token_hash
                AND revoked_at IS NULL
                LIMIT 1'
        );

        $statement->execute([
            'token_hash' => $tokenHash,
        ]);

        $credential = $statement->fetch();

        if (!$credential) {
            return null;
        }

        $statement = $this->connection->prepare(
            'UPDATE media_credentials
                SET last_used_at = CURRENT_TIMESTAMP
                WHERE id = :id'
        );

        $statement->execute([
            'id' => $credential['id'],
        ]);

        return $credential;
    }
}