from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS point_reward_events (
            broadcaster_id TEXT NOT NULL,
            source TEXT NOT NULL,
            event_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            points INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (broadcaster_id, source, event_id)
        )
        """
    )
