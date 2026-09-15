import sqlite3
from unittest.mock import AsyncMock

import asqlite
import pytest

from bot.profiles import ChannelAchievementNames, RaidBossConfig
from bot.services.channels.achievements import AchievementService
from bot.services.engagement.points import PointsService
from bot.services.engagement.raid_boss import RaidBossService
from storage.migration_runner import run_migrations
from storage.migrations import MIGRATIONS


@pytest.mark.asyncio
async def test_presence_is_deduplicated_channel_scoped_and_survives_restart(tmp_path):
    path = str(tmp_path / 'presence.db')
    async with asqlite.create_pool(path) as db:
        await run_migrations(db)
        async with db.acquire() as c:
            for channel, stream, interval in [('a','s',120), ('a','s',120), ('a','s',240), ('a','next',360), ('b','s',120)]:
                await c.execute("INSERT OR IGNORE INTO passive_point_payouts (broadcaster_id,stream_id,interval_started_at,user_id,points) VALUES (?,?,?,'u',15)", (channel,stream,interval))
            rows = await c.fetchall("SELECT * FROM community_achievement_progress")
            assert {(r['broadcaster_id'], r['achievement_id']): r['progress'] for r in rows} == {
                ('a','watch_time'):6, ('a','stream_regular'):2, ('b','watch_time'):2, ('b','stream_regular'):1}
            await c.execute("UPDATE community_achievement_progress SET progress=1498 WHERE broadcaster_id='a' AND achievement_id='watch_time'")
            await c.execute("INSERT INTO passive_point_payouts (broadcaster_id,stream_id,interval_started_at,user_id,points) VALUES ('a','next',480,'u',15)")
    async with asqlite.create_pool(path) as db:
        await run_migrations(db)
        result = await AchievementService(db).get_channel_collection('u','a',ChannelAchievementNames(),lambda _: {'display_name':'A'},'bread')
        card = next(c for c in result['cards'] if c['title']=='Part of the Furniture')
        assert card['progress']==25 and card['tier']=='Bronze'
        assert [s['threshold'] for s in card['steps']]==[25,100,500,2000]
        async with db.acquire() as c:
            rewards = await c.fetchall("SELECT points FROM channel_achievement_rewards WHERE achievement_id='watch_time'")
            assert len(rewards)==1 and rewards[0]['points']==500


@pytest.mark.asyncio
async def test_migration_keeps_old_collector_badges_and_does_not_backfill_presence(tmp_path):
    async with asqlite.create_pool(str(tmp_path/'migration.db')) as db:
        async with db.acquire() as c:
            for migration in MIGRATIONS[:34]:
                await migration.run(c)
            await c.execute("INSERT INTO chatter_channel_stats (broadcaster_id,user_id,lifetime_points_earned) VALUES ('a','u',1000000)")
            await c.execute("INSERT INTO passive_point_payouts (broadcaster_id,stream_id,interval_started_at,user_id,points) VALUES ('a','s',120,'u',15)")
            before = [tuple(r) for r in await c.fetchall('SELECT * FROM channel_achievement_rewards')]
            await MIGRATIONS[34].run(c)
            assert [tuple(r) for r in await c.fetchall('SELECT * FROM channel_achievement_rewards')]==before
            assert not await c.fetchone('SELECT 1 FROM community_achievement_progress')
            old = await c.fetchall("SELECT * FROM achievement_unlocks WHERE achievement_id='collector' AND tier=4")
            assert {r['broadcaster_id'] for r in old}=={'','a'}
            await c.execute("INSERT INTO chatter_channel_stats (broadcaster_id,user_id,lifetime_points_earned) VALUES ('a','new',1000000)")
            assert not await c.fetchone("SELECT 1 FROM achievement_unlocks WHERE user_id='new' AND achievement_id='collector' AND tier>2")
            await c.execute("UPDATE chatter_channel_stats SET lifetime_points_earned=5000000 WHERE user_id='new'")
            assert len(await c.fetchall("SELECT 1 FROM achievement_unlocks WHERE user_id='new' AND achievement_id='collector' AND tier=4"))==2


@pytest.mark.asyncio
async def test_measurement_sets_and_pairs_pay_once_in_measured_channel(tmp_path):
    async with asqlite.create_pool(str(tmp_path/'rolls.db')) as db:
        await run_migrations(db)
        service = AchievementService(db)
        for index, (channel, command, value) in enumerate([
            ('a','stinky',50), ('a','smart',50), ('b','lucky',50), ('a','lucky',50),
            ('a','lucky',50), ('a','stinky',0), ('b','stinky',100), ('a','stinky',100),
            ('a','smart',0), ('a','smart',100),
        ]):
            await service.record_command_roll(channel,str(index),command,'measured',value)
        async with db.acquire() as c:
            rows = await c.fetchall("SELECT * FROM channel_achievement_rewards WHERE achievement_id IN ('average','character_development')")
            assert len(rows)==2
            assert all(r['broadcaster_id']=='a' and r['user_id']=='measured' and r['points']==25000 for r in rows)
            assert not await c.fetchone("SELECT 1 FROM achievement_unlocks WHERE broadcaster_id='' AND achievement_id IN ('average','character_development')")


@pytest.mark.asyncio
@pytest.mark.parametrize('tier', ['main','mini','tutorial'])
@pytest.mark.parametrize('hp,badge', [(101,'not_close'),(1,'whisker'),(102,None)])
async def test_exact_hp_achievements_use_successful_attack_state(tmp_path, monkeypatch, tier, hp, badge):
    monkeypatch.setattr('bot.services.engagement.raid_boss.random.random',lambda:1.0)
    async with asqlite.create_pool(str(tmp_path/'hp.db')) as db:
        await run_migrations(db)
        raid = RaidBossService(None,db)
        raid.resolve = AsyncMock(return_value=0)
        config = RaidBossConfig(base_damage_min=100,base_damage_max=100)
        async with db.acquire() as c:
            await c.execute("INSERT INTO raid_boss_events (broadcaster_id,boss_name,boss_type,boss_tier,max_hp,current_hp,reward_pool,final_hit_reward,status,spawned_at,stream_limit) VALUES ('a','Boss','melee',?,1000,?,500,100,'active','2026-09-15',3)", (tier,hp))
        attack = await raid.attack('a','s','u','viewer',config)
        assert attack.damage==min(hp,100)
        await raid.attack('a','s','u','viewer',config)
        async with db.acquire() as c:
            rows = await c.fetchall("SELECT * FROM channel_achievement_rewards WHERE achievement_id IN ('whisker','not_close')")
            if tier!='tutorial' and badge:
                assert len(rows)==1 and rows[0]['achievement_id']==badge and rows[0]['points']==25000
            else:
                assert not rows


@pytest.mark.asyncio
async def test_craft_repair_success_failure_and_transaction_rollback(tmp_path):
    async with asqlite.create_pool(str(tmp_path/'craft.db')) as db:
        await run_migrations(db)
        raid, points = RaidBossService(None,db), PointsService(None,db)
        config = RaidBossConfig()
        await points.add_points('a','u','viewer',100000,earned=False)
        async with db.acquire() as c:
            await c.execute("INSERT INTO raid_boss_inventory VALUES ('a','u','basic_sword',2,1)")
        assert await raid.craft('a','u','viewer','sword',config)=='crafted:refined_sword'
        assert await raid.craft('a','u','viewer','sword',config)=='materials'
        assert await raid.repair('a','u','refined_sword',config)=='full'
        async with db.acquire() as c:
            await c.execute("UPDATE raid_boss_inventory SET durability=1 WHERE item_id='refined_sword'")
        assert await raid.repair('a','u','refined_sword',config)=='repaired'
        assert await raid.repair('a','u','refined_sword',config)=='full'
        async with db.acquire() as c:
            rows = await c.fetchall("SELECT achievement_id,progress FROM community_achievement_progress")
            assert {r['achievement_id']:r['progress'] for r in rows}=={'crafts':1,'repairs':1}
            await c.execute("UPDATE raid_boss_inventory SET quantity=2 WHERE item_id='refined_sword'")
            await c.execute("CREATE TRIGGER fail_progress BEFORE UPDATE ON community_achievement_progress BEGIN SELECT RAISE(ABORT,'test failure'); END")
        before = await points.get_points('a','u')
        with pytest.raises(sqlite3.IntegrityError):
            await raid.craft('a','u','viewer','sword',config)
        assert await points.get_points('a','u')==before
        async with db.acquire() as c:
            assert (await c.fetchone("SELECT quantity FROM raid_boss_inventory WHERE item_id='refined_sword'"))['quantity']==2
            assert not await c.fetchone("SELECT 1 FROM raid_boss_inventory WHERE item_id='masterwork_sword'")


@pytest.mark.asyncio
async def test_flag_damage_credits_supporter_and_excludes_tutorial(tmp_path):
    async with asqlite.create_pool(str(tmp_path/'flag.db')) as db:
        await run_migrations(db)
        async with db.acquire() as c:
            for event_id, tier in enumerate(('main','mini','tutorial'),1):
                await c.execute("INSERT INTO raid_boss_events (id,broadcaster_id,boss_name,boss_type,boss_tier,max_hp,current_hp,reward_pool,final_hit_reward,status,spawned_at,stream_limit) VALUES (?,'a','Boss','melee',?,1000,1000,500,100,'active','2026-09-15',3)", (event_id,tier))
                await c.execute("INSERT INTO raid_boss_bonus_contributions VALUES (?,'s','attacker',1,'a','supporter','supporter',250)",(event_id,))
                await c.execute("UPDATE raid_boss_events SET status='defeated' WHERE id=?", (event_id,))
            row = await c.fetchone("SELECT * FROM community_achievement_progress WHERE achievement_id='flag_support'")
            assert row['user_id']=='supporter' and row['progress']==500
            assert not await c.fetchone("SELECT 1 FROM community_achievement_progress WHERE user_id='attacker'")
            reward = await c.fetchone("SELECT points FROM channel_achievement_rewards WHERE achievement_id='flag_support'")
            assert reward['points']==500
