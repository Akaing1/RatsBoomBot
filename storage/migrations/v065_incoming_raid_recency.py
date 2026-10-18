"""Keep the latest incoming raid per channel/raider for recommendations."""


async def migrate(connection) -> None:
    await connection.execute("""
        CREATE TABLE IF NOT EXISTS incoming_raid_recency (
            broadcaster_id TEXT NOT NULL,
            raider_id TEXT NOT NULL,
            received_at REAL NOT NULL,
            PRIMARY KEY (broadcaster_id, raider_id)
        )
    """)
    await connection.execute("""
        CREATE INDEX IF NOT EXISTS incoming_raid_recency_recent
        ON incoming_raid_recency (broadcaster_id, received_at DESC)
    """)
