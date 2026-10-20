from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute("""
        CREATE TABLE achievement_tiers (
            achievement_id TEXT NOT NULL,
            tier INTEGER NOT NULL,
            threshold INTEGER NOT NULL,
            PRIMARY KEY (achievement_id, tier)
        )
    """)
    for name, thresholds in (("explorer", (1, 5, 10, 25)), ("regular", (10, 50, 250, 1000)), ("familiar", (10, 50, 100, 365))):
        for tier, threshold in enumerate(thresholds, 1):
            await connection.execute("INSERT INTO achievement_tiers VALUES (?, ?, ?)", (name, tier, threshold))
    await connection.execute("""
        CREATE TABLE achievement_unlocks (
            user_id TEXT NOT NULL,
            broadcaster_id TEXT NOT NULL DEFAULT '',
            achievement_id TEXT NOT NULL,
            tier INTEGER NOT NULL,
            unlocked_at TEXT,
            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, broadcaster_id, achievement_id, tier),
            FOREIGN KEY (achievement_id, tier) REFERENCES achievement_tiers(achievement_id, tier)
        )
    """)
    await connection.execute("CREATE INDEX idx_achievement_daily_user ON redeem_claims(user_id, redeem_type, broadcaster_id)")
    await connection.execute("CREATE INDEX idx_achievement_import_user ON imported_redeem_totals(user_id, redeem_type, broadcaster_id)")
    await connection.execute("""
        CREATE VIEW achievement_check_ins AS
        SELECT user_id, broadcaster_id, SUM(total) AS total FROM (
            SELECT user_id, broadcaster_id, COUNT(*) AS total
            FROM redeem_claims WHERE redeem_type = 'daily' GROUP BY user_id, broadcaster_id
            UNION ALL
            SELECT user_id, broadcaster_id, claim_count AS total
            FROM imported_redeem_totals WHERE redeem_type = 'daily' AND claim_count > 0
        ) GROUP BY user_id, broadcaster_id
    """)
    await connection.execute("""
        CREATE VIEW achievement_progress AS
        SELECT user_id, broadcaster_id, 'familiar' AS achievement_id, total AS progress FROM achievement_check_ins
        UNION ALL
        SELECT user_id, '', 'regular', SUM(total) FROM achievement_check_ins GROUP BY user_id
        UNION ALL
        SELECT user_id, '', 'explorer', COUNT(*) FROM achievement_check_ins WHERE total > 0 GROUP BY user_id
    """)
    # Historical totals establish eligibility, not the original unlock time.
    await connection.execute("""
        INSERT OR IGNORE INTO achievement_unlocks (user_id, broadcaster_id, achievement_id, tier)
        SELECT p.user_id, p.broadcaster_id, p.achievement_id, t.tier
        FROM achievement_progress p JOIN achievement_tiers t ON t.achievement_id = p.achievement_id
        WHERE p.progress >= t.threshold
    """)
    # Cover both bot check-ins and standalone import tools in the same transaction.
    for table, operation, timestamp in (
        ("redeem_claims", "INSERT", "NEW.created_at"),
        ("imported_redeem_totals", "INSERT", "NULL"),
        ("imported_redeem_totals", "UPDATE", "NULL"),
    ):
        await connection.execute(f"""
            CREATE TRIGGER achievement_{table}_{operation.lower()}
            AFTER {operation} ON {table} WHEN NEW.redeem_type = 'daily'
            BEGIN
                INSERT OR IGNORE INTO achievement_unlocks (user_id, broadcaster_id, achievement_id, tier, unlocked_at)
                SELECT p.user_id, p.broadcaster_id, p.achievement_id, t.tier, {timestamp}
                FROM achievement_progress p JOIN achievement_tiers t ON t.achievement_id = p.achievement_id
                WHERE p.user_id = NEW.user_id AND p.progress >= t.threshold
                  AND NOT EXISTS (
                      SELECT 1 FROM achievement_unlocks u
                      WHERE u.user_id = p.user_id AND u.broadcaster_id = p.broadcaster_id
                        AND u.achievement_id = p.achievement_id AND u.tier = t.tier
                  );
            END
        """)
