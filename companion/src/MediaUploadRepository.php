<?php
declare(strict_types=1);

namespace PostBop\Companion;

use PDO;

class MediaUploadRepository
{
    public function __construct( private PDO $connection ) {
    }

    public function create( int $mediaCredentialId, array $upload, int $retentionDays ): int {
        $statement = $this->connection->prepare(
            'INSERT INTO media_uploads (
                media_credential_id,
                public_id,
                storage_filename,
                original_filename,
                mime_type,
                byte_size,
                sha256,
                expires_at
            ) VALUES (
                :media_credential_id,
                :public_id,
                :storage_filename,
                :original_filename,
                :mime_type,
                :byte_size,
                :sha256,
                TIMESTAMPADD(DAY, :retention_days, CURRENT_TIMESTAMP)
            )'
        );

        $statement->execute([
            'media_credential_id' => $mediaCredentialId,
            'public_id' => $upload['public_id'],
            'storage_filename' => $upload['storage_filename'],
            'original_filename' => $upload['original_filename'],
            'mime_type' => $upload['mime_type'],
            'byte_size' => $upload['byte_size'],
            'sha256' => $upload['sha256'],
            'retention_days' => $retentionDays,
        ]);

        return (int) $this->connection->lastInsertId();
    }

    public function findExpired( int $limit = 100 ): array {
        $statement = $this->connection->prepare(
            'SELECT id, storage_filename
                FROM media_uploads
                WHERE deleted_at IS NULL
                AND expires_at <= CURRENT_TIMESTAMP
                ORDER BY expires_at ASC
                LIMIT :limit'
        );

        $statement->bindValue( ':limit', $limit, PDO::PARAM_INT );
        $statement->execute();

        return $statement->fetchAll();
    }

    public function markDeleted( int $id ): void {
        $statement = $this->connection->prepare(
            'UPDATE media_uploads
                SET deleted_at = CURRENT_TIMESTAMP
                WHERE id = :id
                AND deleted_at IS NULL'
        );

        $statement->execute([ 'id' => $id, ]);
    }
}