<?php
declare(strict_types=1);

namespace PostBop\Companion;

use PDO;

class OAuthSessionRepository
{
    public function __construct(
        private PDO $connection
    ) {
    }

    public function create(
        string $stateHash,
        int $ttlSeconds
    ): void {
        $statement = $this->connection->prepare(
            '
            INSERT INTO oauth_sessions (
                state_hash,
                expires_at
            )
            VALUES (
                :state_hash,
                TIMESTAMPADD(
                    SECOND,
                    :ttl_seconds,
                    CURRENT_TIMESTAMP
                )
            )
            '
        );

        $statement->execute([
            'state_hash' => $stateHash,
            'ttl_seconds' => $ttlSeconds,
        ]);
    }

    public function completeWithCode(
        string $stateHash,
        string $authorizationCode
    ): bool {
        $statement = $this->connection->prepare(
            '
            UPDATE oauth_sessions
            SET authorization_code = :authorization_code
            WHERE state_hash = :state_hash
            AND authorization_code IS NULL
            AND oauth_error IS NULL
            AND expires_at > CURRENT_TIMESTAMP
            '
        );

        $statement->execute([
            'authorization_code' => $authorizationCode,
            'state_hash' => $stateHash,
        ]);

        return $statement->rowCount() === 1;
    }

    public function completeWithError(
        string $stateHash,
        string $oauthError
    ): bool {
        $statement = $this->connection->prepare(
            '
            UPDATE oauth_sessions
            SET oauth_error = :oauth_error
            WHERE state_hash = :state_hash
            AND authorization_code IS NULL
            AND oauth_error IS NULL
            AND expires_at > CURRENT_TIMESTAMP
            '
        );

        $statement->execute([
            'oauth_error' => $oauthError,
            'state_hash' => $stateHash,
        ]);

        return $statement->rowCount() === 1;
    }
}