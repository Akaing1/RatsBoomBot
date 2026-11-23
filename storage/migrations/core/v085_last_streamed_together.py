"""Add the last Stream Together time to existing channel user stats."""


async def migrate(connection) -> None:
    await connection.execute("""
        ALTER TABLE chatter_channel_stats
        ADD COLUMN last_streamed_together_at REAL
    """)
    await connection.execute("""
        CREATE INDEX IF NOT EXISTS chatter_channel_stats_stream_together_recent
        ON chatter_channel_stats (broadcaster_id, last_streamed_together_at DESC)
        WHERE last_streamed_together_at IS NOT NULL
    """)
