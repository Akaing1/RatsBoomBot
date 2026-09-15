CHANNEL_ACHIEVEMENTS = ("familiar", "channel_messages", "collector", "winner", "damage", "channel_bosses", "weapons", "buffs", "consumables")


async def migrate(connection):
    for name, thresholds in (("channel_messages", (1000, 10000, 50000, 100000)), ("channel_bosses", (1, 10, 50, 100))):
        for tier, threshold in enumerate(thresholds, 1):
            await connection.execute("INSERT INTO achievement_tiers VALUES (?, ?, ?)", (name, tier, threshold))

    await connection.execute("""
        CREATE TABLE channel_live_messages (
            broadcaster_id TEXT NOT NULL, user_id TEXT NOT NULL,
            messages INTEGER NOT NULL DEFAULT 0 CHECK(messages >= 0),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (broadcaster_id, user_id)
        )
    """)
    await connection.execute("CREATE INDEX idx_channel_live_messages_user ON channel_live_messages(user_id)")
    await connection.execute("""
        CREATE TABLE channel_achievement_reward_tiers (
            tier INTEGER PRIMARY KEY,
            points INTEGER NOT NULL CHECK(points > 0)
        )
    """)
    await connection.execute("INSERT INTO channel_achievement_reward_tiers VALUES (1,500),(2,2000),(3,7500),(4,25000)")
    await connection.execute("""
        CREATE TABLE channel_achievement_rewards (
            user_id TEXT NOT NULL, broadcaster_id TEXT NOT NULL,
            achievement_id TEXT NOT NULL, tier INTEGER NOT NULL,
            points INTEGER NOT NULL CHECK(points > 0),
            awarded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, broadcaster_id, achievement_id, tier)
        )
    """)
    await connection.execute("""
        CREATE VIEW achievement_channel_progress AS
        SELECT user_id,broadcaster_id,'familiar' AS achievement_id,total AS progress
        FROM achievement_check_ins
        UNION ALL
        SELECT user_id,broadcaster_id,'channel_messages',messages
        FROM channel_live_messages
        UNION ALL
        SELECT user_id,broadcaster_id,'collector',lifetime_points_earned
        FROM chatter_channel_stats
        UNION ALL
        SELECT user_id,broadcaster_id,'winner',winnings
        FROM viewer_gambling_totals
        UNION ALL
        SELECT user_id,broadcaster_id,'damage',SUM(damage)
        FROM raid_boss_contributions GROUP BY user_id,broadcaster_id
        UNION ALL
        SELECT contributions.user_id,events.broadcaster_id,'channel_bosses',COUNT(DISTINCT events.id)
        FROM raid_boss_contributions AS contributions
        JOIN raid_boss_events AS events ON events.id=contributions.event_id
        WHERE events.status='defeated'
        GROUP BY contributions.user_id,events.broadcaster_id
        UNION ALL
        SELECT user_id,broadcaster_id,category,purchases
        FROM raid_purchase_totals
    """)
    await connection.execute("""
        CREATE TRIGGER channel_achievement_reward_balance
        AFTER INSERT ON channel_achievement_rewards
        BEGIN
            INSERT INTO viewers (broadcaster_id,user_id,username,points,messages)
            VALUES (
                NEW.broadcaster_id,
                NEW.user_id,
                COALESCE(
                    (SELECT username FROM viewers WHERE broadcaster_id=NEW.broadcaster_id AND user_id=NEW.user_id),
                    (SELECT login FROM chatter_identities WHERE user_id=NEW.user_id),
                    NEW.user_id
                ),
                NEW.points,
                0
            )
            ON CONFLICT(broadcaster_id,user_id) DO UPDATE SET points=points+excluded.points;
        END
    """)
    achievement_ids = ",".join(f"'{name}'" for name in CHANNEL_ACHIEVEMENTS)
    await connection.execute(f"""
        CREATE TRIGGER channel_achievement_unlock_reward
        AFTER INSERT ON achievement_unlocks
        WHEN NEW.broadcaster_id != '' AND NEW.achievement_id IN ({achievement_ids})
        BEGIN
            INSERT INTO channel_achievement_rewards (user_id,broadcaster_id,achievement_id,tier,points)
            SELECT NEW.user_id,NEW.broadcaster_id,NEW.achievement_id,NEW.tier,rewards.points
            FROM channel_achievement_reward_tiers AS rewards WHERE rewards.tier=NEW.tier
            ON CONFLICT(user_id,broadcaster_id,achievement_id,tier) DO NOTHING;
        END
    """)
    await connection.execute("""
        INSERT OR IGNORE INTO achievement_unlocks (user_id,broadcaster_id,achievement_id,tier)
        SELECT progress.user_id,progress.broadcaster_id,progress.achievement_id,tiers.tier
        FROM achievement_channel_progress AS progress
        JOIN achievement_tiers AS tiers ON tiers.achievement_id=progress.achievement_id
        WHERE progress.progress>=tiers.threshold
    """)
    await connection.execute(f"""
        INSERT OR IGNORE INTO channel_achievement_rewards (user_id,broadcaster_id,achievement_id,tier,points)
        SELECT unlocks.user_id,unlocks.broadcaster_id,unlocks.achievement_id,unlocks.tier,rewards.points
        FROM achievement_unlocks AS unlocks
        JOIN channel_achievement_reward_tiers AS rewards ON rewards.tier=unlocks.tier
        WHERE unlocks.broadcaster_id != '' AND unlocks.achievement_id IN ({achievement_ids})
    """)

    # The original global achievement triggers used a NOT EXISTS check followed
    # by a plain INSERT. Concurrent purchases could both pass that check before
    # one committed, causing the other command to fail on the unique key.
    global_sources = (
        ("achievement_chat_chatter_channel_stats_insert", "chatter_channel_stats", "INSERT", "achievement_chat_progress"),
        ("achievement_chat_chatter_channel_stats_update", "chatter_channel_stats", "UPDATE OF lifetime_points_earned", "achievement_chat_progress"),
        ("achievement_chat_viewer_gambling_totals_insert", "viewer_gambling_totals", "INSERT", "achievement_chat_progress"),
        ("achievement_chat_viewer_gambling_totals_update", "viewer_gambling_totals", "UPDATE", "achievement_chat_progress"),
        ("achievement_raid_raid_boss_attacks_insert", "raid_boss_attacks", "INSERT", "achievement_raid_progress"),
        ("achievement_raid_raid_boss_attacks_update", "raid_boss_attacks", "UPDATE OF damage", "achievement_raid_progress"),
        ("achievement_raid_raid_boss_bonus_contributions_insert", "raid_boss_bonus_contributions", "INSERT", "achievement_raid_progress"),
        ("achievement_raid_raid_boss_bonus_contributions_update", "raid_boss_bonus_contributions", "UPDATE OF damage", "achievement_raid_progress"),
        ("achievement_raid_raid_purchase_totals_insert", "raid_purchase_totals", "INSERT", "achievement_raid_progress"),
        ("achievement_raid_raid_purchase_totals_update", "raid_purchase_totals", "UPDATE OF purchases", "achievement_raid_progress"),
    )
    for trigger_name, table, event, progress_view in global_sources:
        await connection.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
        await connection.execute(f"""
            CREATE TRIGGER {trigger_name}
            AFTER {event} ON {table}
            BEGIN
                INSERT INTO achievement_unlocks (user_id,broadcaster_id,achievement_id,tier,unlocked_at)
                SELECT progress.user_id,'',progress.achievement_id,tiers.tier,CURRENT_TIMESTAMP
                FROM {progress_view} AS progress
                JOIN achievement_tiers AS tiers ON tiers.achievement_id=progress.achievement_id
                WHERE progress.user_id=NEW.user_id AND progress.progress>=tiers.threshold
                ON CONFLICT(user_id,broadcaster_id,achievement_id,tier) DO NOTHING;
            END
        """)

    sources = (
        ("channel_live_messages", "INSERT", "NEW.user_id", "NEW.broadcaster_id", "'channel_messages'"),
        ("channel_live_messages", "UPDATE OF messages", "NEW.user_id", "NEW.broadcaster_id", "'channel_messages'"),
        ("chatter_channel_stats", "INSERT", "NEW.user_id", "NEW.broadcaster_id", "'collector'"),
        ("chatter_channel_stats", "UPDATE OF lifetime_points_earned", "NEW.user_id", "NEW.broadcaster_id", "'collector'"),
        ("viewer_gambling_totals", "INSERT", "NEW.user_id", "NEW.broadcaster_id", "'winner'"),
        ("viewer_gambling_totals", "UPDATE OF winnings", "NEW.user_id", "NEW.broadcaster_id", "'winner'"),
        ("raid_boss_attacks", "INSERT", "NEW.user_id", "NEW.broadcaster_id", "'damage'"),
        ("raid_boss_attacks", "UPDATE OF damage", "NEW.user_id", "NEW.broadcaster_id", "'damage'"),
        ("raid_boss_bonus_contributions", "INSERT", "NEW.user_id", "NEW.broadcaster_id", "'damage'"),
        ("raid_boss_bonus_contributions", "UPDATE OF damage", "NEW.user_id", "NEW.broadcaster_id", "'damage'"),
        ("raid_purchase_totals", "INSERT", "NEW.user_id", "NEW.broadcaster_id", "NEW.category"),
        ("raid_purchase_totals", "UPDATE OF purchases", "NEW.user_id", "NEW.broadcaster_id", "NEW.category"),
    )
    for index, (table, event, user, broadcaster, achievement) in enumerate(sources):
        await connection.execute(f"""
            CREATE TRIGGER channel_achievement_progress_{index}
            AFTER {event} ON {table}
            BEGIN
                INSERT INTO achievement_unlocks (user_id,broadcaster_id,achievement_id,tier,unlocked_at)
                SELECT progress.user_id,progress.broadcaster_id,progress.achievement_id,tiers.tier,CURRENT_TIMESTAMP
                FROM achievement_channel_progress AS progress
                JOIN achievement_tiers AS tiers ON tiers.achievement_id=progress.achievement_id
                WHERE progress.user_id={user} AND progress.broadcaster_id={broadcaster}
                  AND progress.achievement_id={achievement} AND progress.progress>=tiers.threshold
                ON CONFLICT(user_id,broadcaster_id,achievement_id,tier) DO NOTHING;
            END
        """)
    await connection.execute("""
        CREATE TRIGGER channel_achievement_boss_defeat
        AFTER UPDATE OF status ON raid_boss_events
        WHEN NEW.status='defeated' AND OLD.status!='defeated'
        BEGIN
            INSERT INTO achievement_unlocks (user_id,broadcaster_id,achievement_id,tier,unlocked_at)
            SELECT progress.user_id,progress.broadcaster_id,progress.achievement_id,tiers.tier,CURRENT_TIMESTAMP
            FROM achievement_channel_progress AS progress
            JOIN achievement_tiers AS tiers ON tiers.achievement_id=progress.achievement_id
            WHERE progress.broadcaster_id=NEW.broadcaster_id AND progress.achievement_id='channel_bosses'
              AND progress.user_id IN (SELECT user_id FROM raid_boss_contributions WHERE event_id=NEW.id)
              AND progress.progress>=tiers.threshold
            ON CONFLICT(user_id,broadcaster_id,achievement_id,tier) DO NOTHING;
        END
    """)
