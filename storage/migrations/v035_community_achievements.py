"""New activity counters start at deployment; existing unlocks remain permanent."""

THRESHOLDS = {
    "watch_time": (1500, 6000, 30000, 120000),  # two-minute live chat samples
    "stream_regular": (10, 50, 150, 365),
    "flag_support": (500, 2000, 5000, 10000),
    "crafts": (1, 3, 5, 10),
    "repairs": (1, 3, 5, 10),
}
SECRETS = ("whisker", "not_close", "average", "character_development")


async def migrate(connection):
    for achievement_id, thresholds in THRESHOLDS.items():
        for tier, threshold in enumerate(thresholds, 1):
            await connection.execute("INSERT INTO achievement_tiers VALUES (?,?,?)", (achievement_id, tier, threshold))
    for achievement_id in SECRETS:
        await connection.execute("INSERT INTO achievement_tiers VALUES (?,4,1)", (achievement_id,))
    for tier, threshold in enumerate((25000, 250000, 1250000, 5000000), 1):
        await connection.execute("UPDATE achievement_tiers SET threshold=? WHERE achievement_id='collector' AND tier=?", (threshold, tier))

    await connection.execute("""
        CREATE TABLE community_achievement_progress (
            broadcaster_id TEXT NOT NULL, user_id TEXT NOT NULL,
            achievement_id TEXT NOT NULL, progress INTEGER NOT NULL CHECK(progress>=0),
            PRIMARY KEY(broadcaster_id,user_id,achievement_id)
        )
    """)
    await connection.execute("""
        CREATE TABLE community_stream_visits (
            broadcaster_id TEXT NOT NULL, user_id TEXT NOT NULL, stream_id TEXT NOT NULL,
            PRIMARY KEY(broadcaster_id,user_id,stream_id)
        )
    """)
    ids = ','.join(f"'{key}'" for key in (*THRESHOLDS, *SECRETS))
    await connection.execute(f"""
        CREATE TRIGGER community_achievement_reward AFTER INSERT ON achievement_unlocks
        WHEN NEW.broadcaster_id!='' AND NEW.achievement_id IN ({ids}) BEGIN
            INSERT INTO channel_achievement_rewards (user_id,broadcaster_id,achievement_id,tier,points)
            SELECT NEW.user_id,NEW.broadcaster_id,NEW.achievement_id,NEW.tier,points
            FROM channel_achievement_reward_tiers WHERE tier=NEW.tier
            ON CONFLICT(user_id,broadcaster_id,achievement_id,tier) DO NOTHING;
        END
    """)
    for event in ("INSERT", "UPDATE OF progress"):
        await connection.execute(f"""
            CREATE TRIGGER community_unlock_{event.split()[0].lower()}
            AFTER {event} ON community_achievement_progress BEGIN
                INSERT INTO achievement_unlocks (user_id,broadcaster_id,achievement_id,tier,unlocked_at)
                SELECT NEW.user_id,NEW.broadcaster_id,NEW.achievement_id,tier,CURRENT_TIMESTAMP
                FROM achievement_tiers WHERE achievement_id=NEW.achievement_id AND threshold<=NEW.progress
                ON CONFLICT(user_id,broadcaster_id,achievement_id,tier) DO NOTHING;
            END
        """)
    await connection.execute("""
        CREATE TRIGGER community_live_presence AFTER INSERT ON passive_point_payouts BEGIN
            INSERT INTO community_achievement_progress VALUES (NEW.broadcaster_id,NEW.user_id,'watch_time',2)
            ON CONFLICT(broadcaster_id,user_id,achievement_id) DO UPDATE SET progress=progress+2;
            INSERT INTO community_stream_visits VALUES (NEW.broadcaster_id,NEW.user_id,NEW.stream_id)
            ON CONFLICT(broadcaster_id,user_id,stream_id) DO NOTHING;
        END
    """)
    await connection.execute("""
        CREATE TRIGGER community_stream_visit AFTER INSERT ON community_stream_visits BEGIN
            INSERT INTO community_achievement_progress VALUES (NEW.broadcaster_id,NEW.user_id,'stream_regular',1)
            ON CONFLICT(broadcaster_id,user_id,achievement_id) DO UPDATE SET progress=progress+1;
        END
    """)
    await connection.execute("""
        CREATE TRIGGER community_flag_damage AFTER INSERT ON raid_boss_bonus_contributions
        WHEN NEW.damage>0 AND EXISTS(SELECT 1 FROM raid_boss_events WHERE id=NEW.event_id AND boss_tier IN ('mini','main')) BEGIN
            INSERT INTO community_achievement_progress VALUES (NEW.broadcaster_id,NEW.user_id,'flag_support',NEW.damage)
            ON CONFLICT(broadcaster_id,user_id,achievement_id) DO UPDATE SET progress=progress+NEW.damage;
        END
    """)
    # Evaluate on new rolls only. Old endpoint badges can contribute to a pair,
    # but deployment itself never issues a retroactive reward.
    await connection.execute("""
        CREATE TRIGGER community_roll AFTER INSERT ON command_achievement_rolls BEGIN
            INSERT INTO community_achievement_progress
            SELECT NEW.broadcaster_id,NEW.user_id,'average',1
            WHERE NEW.value=50 AND (
                SELECT COUNT(DISTINCT command) FROM command_achievement_rolls
                WHERE broadcaster_id=NEW.broadcaster_id AND user_id=NEW.user_id
                  AND value=50 AND command IN ('stinky','smart','lucky')
            )=3
            ON CONFLICT(broadcaster_id,user_id,achievement_id) DO NOTHING;
            INSERT INTO community_achievement_progress
            SELECT NEW.broadcaster_id,NEW.user_id,'character_development',1
            WHERE EXISTS (
                SELECT command FROM command_achievement_rolls
                WHERE broadcaster_id=NEW.broadcaster_id AND user_id=NEW.user_id
                  AND ((command IN ('stinky','smart','lucky') AND value IN (0,100))
                    OR (command='height' AND value IN (12,96)))
                GROUP BY command HAVING COUNT(DISTINCT value)=2
            )
            ON CONFLICT(broadcaster_id,user_id,achievement_id) DO NOTHING;
        END
    """)
