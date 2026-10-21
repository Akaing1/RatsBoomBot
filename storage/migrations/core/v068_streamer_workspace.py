"""Persist private streamer notes and one personal reminder timer."""


async def migrate(connection):
    await connection.execute("""
        CREATE TABLE streamer_workspace (
            broadcaster_id TEXT PRIMARY KEY,
            notes TEXT NOT NULL DEFAULT '',
            notes_revision INTEGER NOT NULL DEFAULT 0,
            timer_id TEXT,
            timer_label TEXT NOT NULL DEFAULT '',
            timer_due_at INTEGER
        )
    """)
