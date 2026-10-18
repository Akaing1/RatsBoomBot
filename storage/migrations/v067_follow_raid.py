async def migrate(connection):
    columns = await connection.fetchall("PRAGMA table_info(broadcaster_settings)")
    if not any(row["name"] == "follow_raid" for row in columns):
        await connection.execute("ALTER TABLE broadcaster_settings ADD COLUMN follow_raid INTEGER NOT NULL DEFAULT 1")
