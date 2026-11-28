"""Accumulate new activity by UTC day without copying historical balances."""

async def migrate(connection):
    await connection.execute("""
        CREATE TABLE recap_daily (
            user_id TEXT NOT NULL,
            day TEXT NOT NULL,
            broadcaster_id TEXT NOT NULL,
            messages INTEGER NOT NULL DEFAULT 0,
            points_earned INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, day, broadcaster_id)
        )
    """)
    for table, fields in (
        ("chatter_channel_stats", (("messages_sent", "messages"), ("lifetime_points_earned", "points_earned"))),
        ("viewer_gamble_outcomes", (("wins", "wins"), ("losses", "losses"))),
    ):
        sources = ", ".join(source for source, _ in fields)
        targets = ", ".join(target for _, target in fields)
        updates = ", ".join(f"{target} = {target} + excluded.{target}" for _, target in fields)
        for operation in ("INSERT", "UPDATE"):
            event = operation if operation == "INSERT" else f"UPDATE OF {sources}"
            deltas = [
                f"MAX(0, NEW.{source})" if operation == "INSERT" else f"MAX(0, NEW.{source} - OLD.{source})"
                for source, _ in fields
            ]
            await connection.execute(f"""
                CREATE TRIGGER recap_{table}_{operation} AFTER {event} ON {table}
                WHEN ({" + ".join(deltas)}) > 0 BEGIN
                    INSERT INTO recap_daily (user_id, day, broadcaster_id, {targets})
                    VALUES (NEW.user_id, date('now'), NEW.broadcaster_id, {", ".join(deltas)})
                    ON CONFLICT(user_id, day, broadcaster_id) DO UPDATE SET {updates};
                END
            """)
