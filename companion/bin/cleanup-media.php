<?php
declare(strict_types=1);

use PostBop\Companion\Config;
use PostBop\Companion\Database;
use PostBop\Companion\MediaStorage;
use PostBop\Companion\MediaUploadRepository;

require dirname(__DIR__) . '/vendor/autoload.php';

try {
    Config::load();
    $database = new Database();

    $repository = new MediaUploadRepository( $database->connection() );

    $storage = new MediaStorage(
        Config::get( 'MEDIA_STORAGE_PATH' ),
        (int) Config::get( 'MEDIA_MAX_BYTES' )
    );

    $expiredUploads = $repository->findExpired( 100 );

    $deleted = 0;
    $failed = 0;

    foreach ($expiredUploads as $upload) {
        $removed = $storage->deleteStoredFile( $upload['storage_filename'] );

        if (!$removed) {
            fwrite( STDERR, sprintf( "Unable to remove media file for upload %d\n", $upload['id'] ) );
            $failed++;
            continue;
        }

        $repository->markDeleted( (int) $upload['id'] );
        $deleted++;
    }

    printf( "PostBop media cleanup: %d deleted, %d failed\n", $deleted, $failed );

    exit( $failed === 0 ? 0 : 1 );

} catch (Throwable $exception) {
    fwrite( STDERR, sprintf( "PostBop media cleanup failed: %s\n", $exception->getMessage() ) );
    exit(1);
}