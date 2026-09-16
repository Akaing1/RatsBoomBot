import asqlite
import pytest

from bot.profiles import RaidBossConfig
from bot.services.engagement.raid_boss import RaidBossService
from storage.migration_runner import run_migrations


@pytest.mark.parametrize('count,pool', [
    (0,(10000,)), (9,(10000,)), (10,(10000,20000)), (19,(10000,20000)),
    (20,(10000,20000,35000)), (29,(10000,20000,35000)),
    (30,(10000,20000,35000,50000)), (39,(10000,20000,35000,50000)),
    (40,(10000,20000,35000,50000,70000)), (100,(10000,20000,35000,50000,70000)),
])
def test_pool_boundaries(count, pool):
    assert RaidBossService.mini_boss_hp_pool(count) == pool


async def add_event(connection, channel, tier, status, count):
    row = await connection.fetchone("INSERT INTO raid_boss_events (broadcaster_id,boss_name,boss_type,boss_tier,max_hp,current_hp,reward_pool,final_hit_reward,status,spawned_at,stream_limit) VALUES (?,'Boss','melee',?,70000,0,70000,1000,?,'2026-09-16',3) RETURNING id", (channel,tier,status))
    for index in range(count):
        await connection.execute("INSERT INTO raid_boss_attacks (event_id,broadcaster_id,stream_id,user_id,username,damage,attacked_at) VALUES (?,?,'s',?,?,100,'2026-09-16')", (row['id'],channel,str(index),str(index)))
    return row['id']


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['defeated','failed'])
async def test_latest_channel_raid_unique_attackers_and_supporters(tmp_path, monkeypatch, status):
    async with asqlite.create_pool(str(tmp_path/'raid.db')) as db:
        await run_migrations(db)
        async with db.acquire() as connection:
            await add_event(connection,'a','mini','defeated',40)
            event_id = await add_event(connection,'a','main',status,19)
            # The same attacker across streams and support records counts once.
            await connection.execute("INSERT INTO raid_boss_attacks (event_id,broadcaster_id,stream_id,user_id,username,damage,attacked_at) VALUES (?,'a','s2','0','renamed',100,'2026-09-16')", (event_id,))
            await connection.execute("INSERT INTO raid_boss_bonus_contributions VALUES (?,'s','0',1,'a','0','renamed',100)", (event_id,))
            await connection.execute("INSERT INTO raid_boss_bonus_contributions VALUES (?,'s','1',1,'a','supporter','supporter',100)", (event_id,))
            await connection.execute("INSERT INTO raid_boss_attacks (event_id,broadcaster_id,stream_id,user_id,username,damage,attacked_at) VALUES (?,'a','s','zero','zero',0,'2026-09-16')", (event_id,))
            await add_event(connection,'a','tutorial','defeated',50)
            await add_event(connection,'b','mini','defeated',50)
        service = RaidBossService(None,db)
        assert await service.previous_raid_contributors('a') == 20
        choices = []
        def choose(pool):
            choices.append(pool)
            return pool[-1]
        monkeypatch.setattr('bot.services.engagement.raid_boss.random.choice',choose)
        event = await service.spawn('a','melee',RaidBossConfig(),'mini')
        assert choices[-1] == (10000,20000,35000)
        assert event.max_hp == event.current_hp == event.reward_pool == 35000
        # Existing active encounters are never resized.
        assert await service.spawn('a','melee',RaidBossConfig(),'mini') is None
        assert (await service.get_active_event('a')).max_hp == 35000


@pytest.mark.asyncio
async def test_empty_previous_raid_and_no_history_use_smallest_pool(tmp_path):
    async with asqlite.create_pool(str(tmp_path/'empty.db')) as db:
        await run_migrations(db)
        service = RaidBossService(None,db)
        assert (await service.spawn('new','magic',RaidBossConfig(),'mini')).max_hp == 10000
        async with db.acquire() as connection:
            await add_event(connection,'a','main','defeated',40)
            await add_event(connection,'a','mini','failed',0)
        assert await service.previous_raid_contributors('a') == 0
        assert (await service.spawn('a','magic',RaidBossConfig(),'mini')).max_hp == 10000
