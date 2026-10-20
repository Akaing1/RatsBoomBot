BLESSINGS = ('heavens_judgement', 'fools_dagger', 'obsidian_brutalizer', 'forgotten_daggers', 'branch_of_yggdrasil')


async def migrate(connection):
    ids = ','.join(f"'{item}'" for item in BLESSINGS)
    # The empty broadcaster scope stores one shared copy of each blessed weapon.
    await connection.execute(f"""
        INSERT INTO raid_boss_inventory (broadcaster_id,user_id,item_id,quantity,durability)
        SELECT '',user_id,item_id,1,MAX(durability) FROM raid_boss_inventory
        WHERE item_id IN ({ids}) AND quantity > 0 GROUP BY user_id,item_id
        ON CONFLICT(broadcaster_id,user_id,item_id) DO UPDATE SET
            quantity=1,durability=MAX(durability,excluded.durability)
    """)
    await connection.execute(f"DELETE FROM raid_boss_inventory WHERE broadcaster_id != '' AND item_id IN ({ids})")
    await connection.execute("""
        CREATE TABLE kamikaze_successes (
            broadcaster_id TEXT NOT NULL, message_id TEXT NOT NULL,
            user_id TEXT NOT NULL, target_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(broadcaster_id,message_id), CHECK(user_id != target_id)
        )
    """)
    await connection.execute("CREATE INDEX idx_kamikaze_success_user ON kamikaze_successes(user_id)")
    await connection.execute("INSERT INTO achievement_tiers VALUES ('stones',4,5),('exterminator',4,100)")
    await connection.execute(f"""
        CREATE VIEW achievement_hidden_progress AS
        SELECT user_id,'' AS broadcaster_id,'stones' AS achievement_id,COUNT(DISTINCT item_id) AS progress
        FROM (
            SELECT user_id,item_id FROM raid_boss_inventory WHERE quantity>0 AND item_id IN ({ids})
            UNION SELECT user_id,item_id FROM raid_boss_reward_items WHERE item_id IN ({ids})
        ) GROUP BY user_id
        UNION ALL
        SELECT user_id,'','exterminator',COUNT(*) FROM kamikaze_successes GROUP BY user_id
    """)
    await connection.execute("""
        INSERT OR IGNORE INTO achievement_unlocks (user_id,broadcaster_id,achievement_id,tier)
        SELECT p.user_id,'',p.achievement_id,t.tier FROM achievement_hidden_progress p
        JOIN achievement_tiers t ON p.achievement_id=t.achievement_id WHERE p.progress>=t.threshold
    """)
    for table in ('raid_boss_inventory','raid_boss_reward_items','kamikaze_successes'):
        for operation in ('INSERT','UPDATE'):
            await connection.execute(f"""
                CREATE TRIGGER achievement_hidden_{table}_{operation.lower()}
                AFTER {operation} ON {table} BEGIN
                    INSERT OR IGNORE INTO achievement_unlocks (user_id,broadcaster_id,achievement_id,tier,unlocked_at)
                    SELECT p.user_id,'',p.achievement_id,t.tier,CURRENT_TIMESTAMP FROM achievement_hidden_progress p
                    JOIN achievement_tiers t ON p.achievement_id=t.achievement_id
                    WHERE p.user_id=NEW.user_id AND p.progress>=t.threshold;
                END
            """)
