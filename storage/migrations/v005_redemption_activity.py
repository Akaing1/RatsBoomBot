from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS redemption_events (
            redemption_id TEXT PRIMARY KEY,
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            reward_title TEXT NOT NULL,
            user_input TEXT,
            stream_id TEXT,
            redeemed_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    await connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_redemption_events_stream
        ON redemption_events (
            broadcaster_id,
            stream_id,
            redeemed_at
        )
        """
    )
