async def migrate(connection):
    await connection.execute("""
        CREATE TABLE IF NOT EXISTS viewer_gambling_totals (
            broadcaster_id TEXT NOT NULL, user_id TEXT NOT NULL,
            winnings INTEGER NOT NULL DEFAULT 0 CHECK(winnings >= 0),
            losses INTEGER NOT NULL DEFAULT 0 CHECK(losses >= 0),
            PRIMARY KEY (broadcaster_id, user_id)
        )
    """)
    await connection.execute("CREATE INDEX idx_gambling_user ON viewer_gambling_totals(user_id)")
    for name, thresholds in (("collector", (10000, 100000, 500000, 1000000)), ("winner", (5000, 50000, 250000, 1000000))):
        for tier, threshold in enumerate(thresholds, 1):
            await connection.execute("INSERT INTO achievement_tiers VALUES (?, ?, ?)", (name, tier, threshold))
    await connection.execute("INSERT INTO achievement_tiers VALUES ('house', 4, 500000)")
    await connection.execute("""
        CREATE VIEW achievement_chat_progress AS
        SELECT user_id, '' AS broadcaster_id, 'collector' AS achievement_id, SUM(lifetime_points_earned) AS progress
        FROM chatter_channel_stats GROUP BY user_id
        UNION ALL
        SELECT user_id, '', 'winner', SUM(winnings) FROM viewer_gambling_totals GROUP BY user_id
        UNION ALL
        SELECT user_id, '', 'house', SUM(losses) FROM viewer_gambling_totals GROUP BY user_id
    """)
    await connection.execute("""
        INSERT INTO achievement_unlocks (user_id, broadcaster_id, achievement_id, tier)
        SELECT p.user_id, '', p.achievement_id, t.tier
        FROM achievement_chat_progress p JOIN achievement_tiers t ON t.achievement_id = p.achievement_id
        WHERE p.progress >= t.threshold
    """)
    for table in ("chatter_channel_stats", "viewer_gambling_totals"):
        for operation in ("INSERT", "UPDATE"):
            event = "UPDATE OF lifetime_points_earned" if table == "chatter_channel_stats" and operation == "UPDATE" else operation
            await connection.execute(f"""
                CREATE TRIGGER achievement_chat_{table}_{operation.lower()}
                AFTER {event} ON {table}
                BEGIN
                    INSERT INTO achievement_unlocks (user_id, broadcaster_id, achievement_id, tier, unlocked_at)
                    SELECT p.user_id, '', p.achievement_id, t.tier, CURRENT_TIMESTAMP
                    FROM achievement_chat_progress p JOIN achievement_tiers t ON t.achievement_id = p.achievement_id
                    WHERE p.user_id = NEW.user_id AND p.progress >= t.threshold
                      AND NOT EXISTS (SELECT 1 FROM achievement_unlocks u WHERE u.user_id = p.user_id
                          AND u.broadcaster_id = '' AND u.achievement_id = p.achievement_id AND u.tier = t.tier);
                END
            """)
