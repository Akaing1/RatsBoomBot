async def migrate(connection) -> None:
    await connection.execute("ALTER TABLE viewer_queue_entries ADD COLUMN display_name TEXT")
