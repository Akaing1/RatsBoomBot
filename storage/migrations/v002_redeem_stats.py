import asqlite


async def migrate(connection: asqlite.Connection) -> None:
    table = await connection.fetchone(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'redeem_claims'
        """
    )

    if table is None:
        await connection.execute(
            """
            CREATE TABLE redeem_claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                broadcaster_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                username TEXT NOT NULL,
                redeem_type TEXT NOT NULL,
                stream_id TEXT NOT NULL,
                redemption_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    columns = await connection.fetchall(
        "PRAGMA table_info(redeem_claims)"
    )

    column_names = {
        column["name"]
        for column in columns
    }

    if "stream_id" not in column_names:
        await connection.execute(
            """
            ALTER TABLE redeem_claims
            ADD COLUMN stream_id TEXT NOT NULL DEFAULT 'legacy'
            """
        )

    await connection.execute(
        "DROP INDEX IF EXISTS idx_redeem_claims_daily"
    )

    await connection.execute(
        "DROP INDEX IF EXISTS idx_redeem_claims_first"
    )

    await connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_redeem_claims_daily
        ON redeem_claims (
            broadcaster_id,
            user_id,
            redeem_type,
            stream_id
        )
        WHERE redeem_type = 'daily'
        """
    )

    await connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_redeem_claims_first
        ON redeem_claims (
            broadcaster_id,
            redeem_type,
            stream_id
        )
        WHERE redeem_type = 'first'
        """
    )