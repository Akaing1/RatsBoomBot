async def migrate(connection) -> None:
    await connection.execute("""CREATE TABLE IF NOT EXISTS patch_notes (id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, title TEXT NOT NULL, synopsis TEXT NOT NULL, body TEXT NOT NULL, version TEXT, published_at TEXT, discord_announced_at TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
