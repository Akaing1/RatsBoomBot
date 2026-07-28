from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS tokens (
            user_id TEXT PRIMARY KEY,
            token TEXT NOT NULL,
            refresh TEXT NOT NULL
        )
        """
    )

    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS viewers (
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            messages INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (broadcaster_id, user_id)
        )
        """
    )

    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS counters (
            name TEXT PRIMARY KEY,
            value INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS broadcaster_settings (
            broadcaster_id TEXT PRIMARY KEY,
            discord_url TEXT,
            youtube_url TEXT,
            timers_enabled INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS redeem_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            redeem_type TEXT NOT NULL,
            stream_id TEXT NOT NULL,
            redemption_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
