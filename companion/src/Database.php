<?php
declare(strict_types=1);

namespace PostBop\Companion;

use PDO;

class Database
{
    private PDO $connection;

    public function __construct()
    {
        $dsn = sprintf(
            'mysql:host=%s;dbname=%s;charset=utf8mb4',
            Config::get('DB_HOST'),
            Config::get('DB_NAME')
        );

        $this->connection = new PDO(
            $dsn,
            Config::get('DB_USER'),
            Config::get('DB_PASSWORD'),
            [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES => false,
            ]
        );
    }

    public function connection(): PDO
    {
        return $this->connection;
    }
}