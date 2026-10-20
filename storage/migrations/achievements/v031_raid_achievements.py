async def migrate(connection):
    await connection.execute("""
        CREATE TABLE raid_purchase_totals (
            user_id TEXT NOT NULL, broadcaster_id TEXT NOT NULL,
            category TEXT NOT NULL CHECK(category IN ('weapons', 'buffs', 'consumables')),
            purchases INTEGER NOT NULL DEFAULT 0 CHECK(purchases >= 0),
            PRIMARY KEY (user_id, broadcaster_id, category)
        )
    """)
    for name, thresholds in (("damage", (10000, 100000, 1000000, 10000000)), ("weapons", (1, 10, 50, 100)), ("buffs", (1, 10, 50, 100)), ("consumables", (10, 50, 250, 1000))):
        for tier, threshold in enumerate(thresholds, 1):
            await connection.execute("INSERT INTO achievement_tiers VALUES (?, ?, ?)", (name, tier, threshold))
    await connection.execute("""
        CREATE VIEW achievement_raid_progress AS
        SELECT user_id, '' AS broadcaster_id, 'damage' AS achievement_id, SUM(damage) AS progress
        FROM raid_boss_contributions GROUP BY user_id
        UNION ALL
        SELECT user_id, '', category, SUM(purchases) FROM raid_purchase_totals GROUP BY user_id, category
    """)
    await connection.execute("""
        INSERT INTO achievement_unlocks (user_id, broadcaster_id, achievement_id, tier)
        SELECT p.user_id, '', p.achievement_id, t.tier
        FROM achievement_raid_progress p JOIN achievement_tiers t ON t.achievement_id = p.achievement_id
        WHERE p.progress >= t.threshold
    """)
    for table in ("raid_boss_attacks", "raid_boss_bonus_contributions", "raid_purchase_totals"):
        for operation in ("INSERT", "UPDATE"):
            column = "purchases" if table == "raid_purchase_totals" else "damage"
            event = f"UPDATE OF {column}" if operation == "UPDATE" else operation
            await connection.execute(f"""
                CREATE TRIGGER achievement_raid_{table}_{operation.lower()}
                AFTER {event} ON {table}
                BEGIN
                    INSERT INTO achievement_unlocks (user_id, broadcaster_id, achievement_id, tier, unlocked_at)
                    SELECT p.user_id, '', p.achievement_id, t.tier, CURRENT_TIMESTAMP
                    FROM achievement_raid_progress p JOIN achievement_tiers t ON t.achievement_id = p.achievement_id
                    WHERE p.user_id = NEW.user_id AND p.progress >= t.threshold
                      AND NOT EXISTS (SELECT 1 FROM achievement_unlocks u WHERE u.user_id = p.user_id
                          AND u.broadcaster_id = '' AND u.achievement_id = p.achievement_id AND u.tier = t.tier);
                END
            """)
