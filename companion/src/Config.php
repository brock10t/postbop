<?php
declare(strict_types=1);

namespace PostBop\Companion;

use Dotenv\Dotenv;
use RuntimeException;

class Config
{
    public static function load(): void
    {
        $dotenv = Dotenv::createImmutable(
            '/etc/postbop',
            'companion.env'
        );

        $dotenv->load();

        $dotenv->required([
            'DB_HOST',
            'DB_NAME',
            'DB_USER',
            'DB_PASSWORD',
            'OAUTH_SESSION_TTL',
        ])->notEmpty();
    }

    public static function get(string $key): string
    {
        if (!isset($_ENV[$key])) {
            throw new RuntimeException(
                "Missing required configuration value: {$key}"
            );
        }

        return $_ENV[$key];
    }
}