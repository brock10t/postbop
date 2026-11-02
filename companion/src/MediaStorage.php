<?php
declare(strict_types=1);

namespace PostBop\Companion;

use RuntimeException;

class MediaStorage
{
    private const MIME_TYPES = [
        'image/jpeg' => 'jpg',
        'image/png' => 'png',
        'image/webp' => 'webp',
    ];

    public function __construct( private string $storagePath, private int $maxBytes ) {
    }

    public function storeUploadedFile( array $file ): array {
        if (
            !isset(
                $file['error'],
                $file['tmp_name'],
                $file['name']
            )
        ) {
            throw new RuntimeException( 'invalid_upload', 400 );
        }

        if ($file['error'] !== UPLOAD_ERR_OK) {
            if ( $file['error'] === UPLOAD_ERR_INI_SIZE || $file['error'] === UPLOAD_ERR_FORM_SIZE ) {
                throw new RuntimeException( 'file_too_large', 413 );
            }
            throw new RuntimeException( 'upload_failed', 400);
        }

        $temporaryPath = $file['tmp_name'];

        if ( !is_uploaded_file($temporaryPath) ) {
            throw new RuntimeException( 'invalid_upload', 400 );
        }

        $byteSize = filesize( $temporaryPath );

        if ( $byteSize === false || $byteSize <= 0 ) {
            throw new RuntimeException( 'invalid_upload', 400 );
        }

        if ( $byteSize > $this->maxBytes ) {
            throw new RuntimeException( 'file_too_large', 413 );
        }

        $finfo = new \finfo( FILEINFO_MIME_TYPE );

        $mimeType = $finfo->file( $temporaryPath );

        if ( !is_string( $mimeType ) || !isset( self::MIME_TYPES[$mimeType] ) ) {
            throw new RuntimeException( 'unsupported_media_type', 415 );
        }

        $imageInfo = @getimagesize( $temporaryPath );

        if ( $imageInfo === false ) {
            throw new RuntimeException( 'invalid_image', 415 );
        }

        $publicId = bin2hex( random_bytes(16) );

        $extension = self::MIME_TYPES[ $mimeType ];

        $storageFilename = sprintf( '%s.%s', $publicId, $extension );

        $destination = sprintf( '%s/%s', rtrim( $this->storagePath, '/' ), $storageFilename );

        $sha256 = hash_file( 'sha256', $temporaryPath );

        if ( $sha256 === false ) {
            throw new RuntimeException( 'unable_to_hash_upload', 500 );
        }

        if ( !move_uploaded_file( $temporaryPath, $destination ) ) {
            throw new RuntimeException( 'unable_to_store_upload', 500 );
        }

        return [
            'public_id' => $publicId,
            'storage_filename' => $storageFilename,
            'original_filename' => substr(
                basename(
                    (string) $file['name']
                ), 0, 255
            ),
            'mime_type' => $mimeType,
            'byte_size' => $byteSize,
            'sha256' => $sha256,
        ];
    }

    public function deleteStoredFile( string $storageFilename ): bool {
        $path = sprintf( '%s/%s', rtrim( $this->storagePath, '/' ), basename( $storageFilename ) );
        if (!is_file($path)) {
            return true;
        }
        return unlink($path);
    }
}