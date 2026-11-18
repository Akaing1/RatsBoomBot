async def migrate(connection):
    await connection.execute("""
        CREATE TABLE streamer_setup (
            broadcaster_id TEXT PRIMARY KEY,
            step INTEGER NOT NULL DEFAULT 0 CHECK (step BETWEEN 0 AND 5),
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'dismissed', 'finished')),
            moderator_confirmed INTEGER NOT NULL DEFAULT 0,
            command_confirmed INTEGER NOT NULL DEFAULT 0
        )
    """)
