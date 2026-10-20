"""One-time command and gambling-streak achievements (no historical backfill)."""

ROLL_BADGES = {
    ("stinky", 100): "shower",
    ("stinky", 0): "spotless",
    ("smart", 0): "lights_out",
    ("smart", 100): "genius",
    ("height", 12): "tiny",
    ("height", 96): "towering",
    ("lucky", 100): "gamble_all",
    ("lucky", 0): "unlucky",
}
CHANNEL_IDS = ("nice_try", *ROLL_BADGES.values(), "loss_streak", "win_streak")
GLOBAL_IDS = ("nice_try_global", "loss_streak_global", "win_streak_global")


async def migrate(connection):
    for achievement_id in CHANNEL_IDS + GLOBAL_IDS:
        thresholds = (1, 10, 50, 100) if achievement_id.startswith("nice_try") else (10,) if "streak" in achievement_id else (1,)
        tiers = range(1, 5) if achievement_id.startswith("nice_try") else (4,)
        for tier, threshold in zip(tiers, thresholds):
            await connection.execute("INSERT INTO achievement_tiers VALUES (?,?,?)", (achievement_id, tier, threshold))

    await connection.execute("""
        CREATE TABLE command_achievement_rolls (
            broadcaster_id TEXT NOT NULL, message_id TEXT NOT NULL, command TEXT NOT NULL,
            user_id TEXT NOT NULL, value INTEGER NOT NULL,
            PRIMARY KEY (broadcaster_id,message_id,command)
        )
    """)
    await connection.execute("""
        CREATE TABLE kamikaze_failures (
            broadcaster_id TEXT NOT NULL, message_id TEXT NOT NULL, user_id TEXT NOT NULL,
            PRIMARY KEY (broadcaster_id,message_id)
        )
    """)
    await connection.execute("CREATE INDEX idx_command_roll_user ON command_achievement_rolls(user_id,broadcaster_id)")
    await connection.execute("CREATE INDEX idx_kamikaze_failure_user ON kamikaze_failures(user_id,broadcaster_id)")
    await connection.execute("""
        CREATE TABLE gamble_streaks (
            broadcaster_id TEXT NOT NULL, user_id TEXT NOT NULL,
            outcome TEXT NOT NULL CHECK(outcome IN ('win','loss')),
            length INTEGER NOT NULL CHECK(length > 0),
            channel_name TEXT NOT NULL,
            PRIMARY KEY (broadcaster_id,user_id)
        )
    """)
    await connection.execute("""
        CREATE TABLE gamble_streak_origins (
            user_id TEXT NOT NULL, achievement_id TEXT NOT NULL,
            broadcaster_id TEXT NOT NULL, channel_name TEXT NOT NULL,
            PRIMARY KEY (user_id,achievement_id)
        )
    """)
    await connection.execute("""
        CREATE VIEW command_achievement_progress AS
        SELECT user_id,broadcaster_id,command,value,
               CASE command
                   WHEN 'height' THEN CASE value WHEN 12 THEN 'tiny' WHEN 96 THEN 'towering' END
                   WHEN 'stinky' THEN CASE value WHEN 0 THEN 'spotless' WHEN 100 THEN 'shower' END
                   WHEN 'smart' THEN CASE value WHEN 0 THEN 'lights_out' WHEN 100 THEN 'genius' END
                   WHEN 'lucky' THEN CASE value WHEN 0 THEN 'unlucky' WHEN 100 THEN 'gamble_all' END
               END AS achievement_id
        FROM command_achievement_rolls
    """)
    await connection.execute("""
        CREATE VIEW secret_channel_progress AS
        SELECT user_id,broadcaster_id,'nice_try' AS achievement_id,COUNT(*) AS progress
        FROM kamikaze_failures GROUP BY user_id,broadcaster_id
        UNION ALL
        SELECT user_id,broadcaster_id,achievement_id,COUNT(*)
        FROM command_achievement_progress WHERE achievement_id IS NOT NULL
        GROUP BY user_id,broadcaster_id,achievement_id
        UNION ALL
        SELECT user_id,broadcaster_id,
               CASE outcome WHEN 'loss' THEN 'loss_streak' ELSE 'win_streak' END,
               length FROM gamble_streaks
    """)
    await connection.execute("""
        CREATE VIEW secret_global_progress AS
        SELECT user_id,'' AS broadcaster_id,'nice_try_global' AS achievement_id,COUNT(*) AS progress
        FROM kamikaze_failures GROUP BY user_id
        UNION ALL
        SELECT user_id,'',achievement_id,10 FROM gamble_streak_origins
    """)

    for name, event in (("roll", "AFTER INSERT ON command_achievement_rolls"), ("failure", "AFTER INSERT ON kamikaze_failures"), ("streak", "AFTER INSERT ON gamble_streaks"), ("streak_update", "AFTER UPDATE OF length ON gamble_streaks")):
        await connection.execute(f"""
            CREATE TRIGGER secret_achievement_{name} {event} BEGIN
                INSERT INTO achievement_unlocks (user_id,broadcaster_id,achievement_id,tier,unlocked_at)
                SELECT p.user_id,p.broadcaster_id,p.achievement_id,t.tier,CURRENT_TIMESTAMP
                FROM secret_channel_progress p JOIN achievement_tiers t ON t.achievement_id=p.achievement_id
                WHERE p.user_id=NEW.user_id AND p.broadcaster_id=NEW.broadcaster_id
                  AND p.progress>=t.threshold
                ON CONFLICT(user_id,broadcaster_id,achievement_id,tier) DO NOTHING;
                INSERT INTO achievement_unlocks (user_id,broadcaster_id,achievement_id,tier,unlocked_at)
                SELECT p.user_id,'',p.achievement_id,t.tier,CURRENT_TIMESTAMP
                FROM secret_global_progress p JOIN achievement_tiers t ON t.achievement_id=p.achievement_id
                WHERE p.user_id=NEW.user_id AND p.progress>=t.threshold
                ON CONFLICT(user_id,broadcaster_id,achievement_id,tier) DO NOTHING;
            END
        """)

    # Only settled !gamble bets generate streaks; record the winning channel
    # before the global unlock so it remains visible if a profile disconnects.
    for event in ("INSERT", "UPDATE OF length"):
        await connection.execute(f"""
            CREATE TRIGGER secret_streak_origin_{event.split()[0].lower()}
            AFTER {event} ON gamble_streaks WHEN NEW.length>=10 BEGIN
                INSERT INTO gamble_streak_origins (user_id,achievement_id,broadcaster_id,channel_name)
                VALUES (NEW.user_id,CASE NEW.outcome WHEN 'loss' THEN 'loss_streak_global' ELSE 'win_streak_global' END,NEW.broadcaster_id,NEW.channel_name)
                ON CONFLICT(user_id,achievement_id) DO NOTHING;
                INSERT INTO achievement_unlocks (user_id,broadcaster_id,achievement_id,tier,unlocked_at)
                VALUES (NEW.user_id,'',CASE NEW.outcome WHEN 'loss' THEN 'loss_streak_global' ELSE 'win_streak_global' END,4,CURRENT_TIMESTAMP)
                ON CONFLICT(user_id,broadcaster_id,achievement_id,tier) DO NOTHING;
            END
        """)

    # The existing channel unlock trigger only knew the original nine IDs.
    await connection.execute("DROP TRIGGER channel_achievement_unlock_reward")
    ids = ",".join(f"'{name}'" for name in ("familiar","channel_messages","collector","winner","damage","channel_bosses","weapons","buffs","consumables",*CHANNEL_IDS))
    await connection.execute(f"""
        CREATE TRIGGER channel_achievement_unlock_reward
        AFTER INSERT ON achievement_unlocks
        WHEN NEW.broadcaster_id != '' AND NEW.achievement_id IN ({ids}) BEGIN
            INSERT INTO channel_achievement_rewards (user_id,broadcaster_id,achievement_id,tier,points)
            SELECT NEW.user_id,NEW.broadcaster_id,NEW.achievement_id,NEW.tier,rewards.points
            FROM channel_achievement_reward_tiers rewards WHERE rewards.tier=NEW.tier
            ON CONFLICT(user_id,broadcaster_id,achievement_id,tier) DO NOTHING;
        END
    """)
