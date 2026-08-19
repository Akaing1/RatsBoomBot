from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS chatter_identities (
            user_id TEXT PRIMARY KEY,
            login TEXT NOT NULL,
            display_name TEXT NOT NULL,
            first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS chatter_channel_observations (
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (broadcaster_id, user_id),
            FOREIGN KEY (user_id) REFERENCES chatter_identities (user_id)
        )
        """
    )

    await connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chatter_channel_user
        ON chatter_channel_observations (user_id)
        """
    )
