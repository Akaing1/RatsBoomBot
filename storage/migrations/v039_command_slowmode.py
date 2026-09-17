async def migrate(connection):
    await connection.execute("CREATE TABLE command_slowmode (broadcaster_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0, 1)))")
