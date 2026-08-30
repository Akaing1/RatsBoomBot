from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS viewer_queue_states (
            broadcaster_id TEXT PRIMARY KEY,
            is_open INTEGER NOT NULL DEFAULT 0 CHECK (is_open IN (0, 1)),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS viewer_queue_entries (
            broadcaster_id TEXT NOT NULL,
            username TEXT NOT NULL,
            position INTEGER NOT NULL CHECK (position >= 1),
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (broadcaster_id, username),
            UNIQUE (broadcaster_id, position),
            FOREIGN KEY (broadcaster_id) REFERENCES viewer_queue_states (broadcaster_id) ON DELETE CASCADE
        )
        """
    )

    await connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_viewer_queue_entries_order
        ON viewer_queue_entries (broadcaster_id, position)
        """
    )
