from types import SimpleNamespace

import asqlite
import pytest

from bot.profiles import ChannelAchievementNames
from bot.services.channels.achievements import AchievementService
from storage.migrations import MIGRATIONS


@pytest.mark.asyncio
async def test_channel_achievement_backfill_and_rewards_are_idempotent(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "channel-achievements.db")) as database:
        async with database.acquire() as connection:
            for migration in MIGRATIONS[:32]:
                await migration.run(connection)

            await connection.execute(
                "INSERT INTO viewers (broadcaster_id,user_id,username,points,messages) VALUES ('channel-1','user-1','alice',100,0)"
            )
            await connection.execute(
                "INSERT INTO chatter_channel_stats (broadcaster_id,user_id,lifetime_points_earned) VALUES ('channel-1','user-1',100000)"
            )
            await connection.execute(
                "INSERT INTO imported_redeem_totals (broadcaster_id,user_id,username,redeem_type,claim_count) VALUES ('channel-1','user-1','alice','daily',50)"
            )
            await MIGRATIONS[32].run(connection)

            balance = await connection.fetchone(
                "SELECT points FROM viewers WHERE broadcaster_id='channel-1' AND user_id='user-1'"
            )
            reward_count = await connection.fetchone(
                "SELECT COUNT(*) AS total FROM channel_achievement_rewards WHERE broadcaster_id='channel-1' AND user_id='user-1'"
            )
            assert int(balance["points"]) == 5100
            assert int(reward_count["total"]) == 4

            await connection.execute(
                "UPDATE chatter_channel_stats SET lifetime_points_earned=500000 WHERE broadcaster_id='channel-1' AND user_id='user-1'"
            )
            await connection.execute(
                "UPDATE chatter_channel_stats SET lifetime_points_earned=500000 WHERE broadcaster_id='channel-1' AND user_id='user-1'"
            )
            await connection.execute(
                "INSERT INTO channel_live_messages (broadcaster_id,user_id,messages) VALUES ('channel-1','user-1',999)"
            )
            await connection.execute(
                "UPDATE channel_live_messages SET messages=1000 WHERE broadcaster_id='channel-1' AND user_id='user-1'"
            )

            balance = await connection.fetchone(
                "SELECT points FROM viewers WHERE broadcaster_id='channel-1' AND user_id='user-1'"
            )
            reward_count = await connection.fetchone(
                "SELECT COUNT(*) AS total FROM channel_achievement_rewards WHERE broadcaster_id='channel-1' AND user_id='user-1'"
            )
            assert int(balance["points"]) == 13100
            assert int(reward_count["total"]) == 6

            for migration in MIGRATIONS[33:]:
                await migration.run(connection)

        names = ChannelAchievementNames(points="Breadwinner", messages="Sewer Socialite")
        collection = await AchievementService(database).get_channel_collection(
            "user-1",
            "channel-1",
            names,
            lambda broadcaster_id: {"display_name": "Test Channel", "id": broadcaster_id},
            "bread"
        )
        cards = {card["title"]: card for card in collection["cards"]}
        assert cards["Breadwinner"]["tier"] == "Gold"
        assert cards["Sewer Socialite"]["tier"] == "Bronze"
        assert cards["Sewer Socialite"]["steps"][0]["reward"] == 500
        assert cards["Sewer Socialite"]["steps"][0]["xp"] == 100
        assert collection["currency_name"] == "bread"


@pytest.mark.asyncio
async def test_defeated_boss_unlocks_channel_participation_achievement(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "boss-achievement.db")) as database:
        async with database.acquire() as connection:
            for migration in MIGRATIONS:
                await migration.run(connection)
            await connection.execute(
                "INSERT INTO viewers (broadcaster_id,user_id,username,points,messages) VALUES ('channel-1','user-1','alice',0,0)"
            )
            await connection.execute(
                "INSERT INTO raid_boss_events (id,broadcaster_id,boss_name,boss_type,boss_tier,max_hp,current_hp,reward_pool,final_hit_reward,status,spawned_at,stream_limit) VALUES (1,'channel-1','Test Boss','melee','mini',1000,1,500,100,'active','2026-09-15T00:00:00+00:00',3)"
            )
            await connection.execute(
                "INSERT INTO raid_boss_attacks (event_id,broadcaster_id,stream_id,user_id,username,damage,attacked_at) VALUES (1,'channel-1','stream-1','user-1','alice',100,'2026-09-15T00:01:00+00:00')"
            )
            await connection.execute("UPDATE raid_boss_events SET status='defeated',current_hp=0 WHERE id=1")
            unlock = await connection.fetchone(
                "SELECT tier FROM achievement_unlocks WHERE user_id='user-1' AND broadcaster_id='channel-1' AND achievement_id='channel_bosses'"
            )
            balance = await connection.fetchone(
                "SELECT points FROM viewers WHERE broadcaster_id='channel-1' AND user_id='user-1'"
            )

        assert int(unlock["tier"]) == 1
        assert int(balance["points"]) == 500
