from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS passive_point_payouts (
            broadcaster_id TEXT NOT NULL,
            stream_id TEXT NOT NULL,
            interval_started_at INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            points INTEGER NOT NULL,
            awarded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (broadcaster_id, stream_id, interval_started_at, user_id)
        )
        """
    )
    await connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_passive_point_payouts_stream
        ON passive_point_payouts (broadcaster_id, stream_id)
        """
    )
