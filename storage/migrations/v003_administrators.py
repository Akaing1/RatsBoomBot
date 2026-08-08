from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS administrators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin'
                CHECK (role IN ('owner', 'admin')),
            is_enabled INTEGER NOT NULL DEFAULT 1
                CHECK (is_enabled IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
