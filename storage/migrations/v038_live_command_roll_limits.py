"""Persist one achievement-bearing measurement per viewer and live stream."""


async def migrate(connection):
    await connection.execute("""
        CREATE TABLE command_stream_rolls (
            broadcaster_id TEXT NOT NULL,
            stream_id TEXT NOT NULL,
            command TEXT NOT NULL CHECK(command IN ('stinky','smart','lucky','height')),
            user_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            value INTEGER NOT NULL,
            rolled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (broadcaster_id,stream_id,command,user_id)
        )
    """)
