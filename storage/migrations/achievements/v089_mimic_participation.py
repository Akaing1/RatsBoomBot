async def migrate(connection):
    await connection.execute("INSERT INTO achievement_tiers VALUES ('gift_inspector_2026', 4, 1)")
    await connection.execute("""
        CREATE TABLE mistletoe_2026_contributions (
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            damage INTEGER NOT NULL CHECK (damage > 0),
            PRIMARY KEY (broadcaster_id, user_id)
        )
    """)
    await connection.execute("""
        CREATE TRIGGER mistletoe_2026_participation AFTER INSERT ON mistletoe_2026_contributions
        BEGIN
            INSERT INTO achievement_unlocks (user_id, broadcaster_id, achievement_id, tier, unlocked_at)
            VALUES (NEW.user_id, '', 'gift_inspector_2026', 4, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, broadcaster_id, achievement_id, tier) DO NOTHING;
        END
    """)
