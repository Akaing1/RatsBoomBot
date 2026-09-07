async def migrate(connection) -> None:
    await connection.execute("""
    CREATE TABLE IF NOT EXISTS gambling_loss_totals (
        broadcaster_id TEXT PRIMARY KEY,
        points_lost INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)
