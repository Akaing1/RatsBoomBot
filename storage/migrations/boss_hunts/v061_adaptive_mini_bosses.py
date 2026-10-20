"""Store mini-boss difficulty independently of individual encounter turnout."""


async def migrate(connection) -> None:
    await connection.execute("""
        CREATE TABLE raid_mini_difficulty (
            broadcaster_id TEXT PRIMARY KEY,
            base_tier INTEGER NOT NULL DEFAULT 0 CHECK (base_tier BETWEEN 0 AND 4),
            two_stream_streak INTEGER NOT NULL DEFAULT 0 CHECK (two_stream_streak BETWEEN 0 AND 1),
            lower_clears INTEGER NOT NULL DEFAULT 0 CHECK (lower_clears BETWEEN 0 AND 2)
        )
    """)
