import asyncio

import asqlite
import pytest

from rpg_minigame.config import RaidBossConfig
from rpg_minigame.difficulty import HP_TIERS, MiniDifficulty, load_difficulty, save_difficulty
from rpg_minigame.service import RaidBossService
from storage.migration_runner import run_migrations


@pytest.mark.parametrize('state,hp,win,streams,expected', [
    (MiniDifficulty(), 10000, True, 1, MiniDifficulty(1)),
    (MiniDifficulty(1), 35000, True, 3, MiniDifficulty(2)),
    (MiniDifficulty(1), 35000, True, 1, MiniDifficulty(2)),
    (MiniDifficulty(1), 20000, True, 2, MiniDifficulty(1, 1)),
    (MiniDifficulty(1, 1), 20000, True, 2, MiniDifficulty(2)),
    (MiniDifficulty(1, 1), 20000, True, 3, MiniDifficulty(1)),
    (MiniDifficulty(1, 1), 10000, True, 1, MiniDifficulty(1, 0, 1)),
    (MiniDifficulty(1, 0, 1), 10000, True, 3, MiniDifficulty(1, 0, 2)),
    (MiniDifficulty(1, 0, 2), 10000, True, 1, MiniDifficulty(1, 0, 2)),
    (MiniDifficulty(2, 1, 2), 35000, True, 1, MiniDifficulty(3)),
    (MiniDifficulty(2, 1, 2), 20000, False, 4, MiniDifficulty(1)),
    (MiniDifficulty(2), 50000, False, 4, MiniDifficulty(1)),
    (MiniDifficulty(), 10000, False, 4, MiniDifficulty()),
    (MiniDifficulty(4), 70000, True, 1, MiniDifficulty(4)),
    (MiniDifficulty(4, 1), 70000, True, 2, MiniDifficulty(4)),
    (MiniDifficulty(1, 1), 20000, True, 0, MiniDifficulty(1)),
])
def test_result_rules(state, hp, win, streams, expected):
    assert state.after_result(hp, win, streams) == expected


@pytest.mark.parametrize('state,pool,weights', [
    (MiniDifficulty(1), (10000, 20000, 35000), (15, 60, 25)),
    (MiniDifficulty(1, 0, 1), (10000, 20000, 35000), (10, 65, 25)),
    (MiniDifficulty(1, 0, 2), (10000, 20000, 35000), (5, 70, 25)),
    (MiniDifficulty(), (10000, 20000), (75, 25)),
    (MiniDifficulty(4), (50000, 70000), (15, 85)),
    (MiniDifficulty(4, 0, 2), (50000, 70000), (5, 95)),
])
def test_spawn_weights_and_boundaries(state, pool, weights):
    assert state.rolls() == (pool, weights)
    assert sum(weights) == 100


async def state_for(db, channel='a'):
    async with db.acquire() as connection:
        return await load_difficulty(connection, channel)


async def encounter(service, db, monkeypatch, hp, streams=1, win=True, tier='mini', channel='a'):
    monkeypatch.setattr('rpg_minigame.service.random.choices', lambda *args, **kwargs: [hp])
    event = await service.spawn(channel, 'melee', RaidBossConfig(), tier)
    async with db.acquire() as connection:
        for stream in range(streams):
            await connection.execute("INSERT INTO raid_boss_streams VALUES (?, ?, '2026-10-04')", (event.id, str(stream)))
        if win:
            await connection.execute('UPDATE raid_boss_events SET current_hp = 0 WHERE id = ?', (event.id,))
    await service.resolve(channel, win)
    return event


@pytest.mark.asyncio
async def test_fast_small_clear_escapes_loop_and_persists(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / 'raid.db')) as db:
        await run_migrations(db)
        service = RaidBossService(None, db)
        await encounter(service, db, monkeypatch, 10000)
        assert await state_for(db) == MiniDifficulty(1)
        restarted = RaidBossService(None, db)
        calls = []
        def choose(pool, weights, k):
            calls.append((pool, weights))
            return [pool[1]]
        monkeypatch.setattr('rpg_minigame.service.random.choices', choose)
        event = await restarted.spawn('a', 'melee', RaidBossConfig(), 'mini')
        assert calls == [((10000, 20000, 35000), (15, 60, 25))]
        assert event.current_hp == event.max_hp == event.reward_pool == 20000
        assert await restarted.spawn('a', 'melee', RaidBossConfig(), 'mini') is None
        assert await state_for(db, 'b') == MiniDifficulty()


@pytest.mark.asyncio
async def test_lower_clear_odds_and_promotion_reset(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / 'raid.db')) as db:
        await run_migrations(db)
        service = RaidBossService(None, db)
        await encounter(service, db, monkeypatch, 10000)
        for clears in (1, 2, 2):
            await encounter(service, db, monkeypatch, 10000)
            assert await state_for(db) == MiniDifficulty(1, 0, clears)
        await encounter(service, db, monkeypatch, 35000, streams=3)
        assert await state_for(db) == MiniDifficulty(2)
        await encounter(service, db, monkeypatch, 35000, streams=2)
        assert await state_for(db) == MiniDifficulty(2, 1)
        await encounter(service, db, monkeypatch, 35000, streams=2)
        assert await state_for(db) == MiniDifficulty(3)
        await encounter(service, db, monkeypatch, 70000, win=False)
        assert await state_for(db) == MiniDifficulty(2)


@pytest.mark.asyncio
async def test_expiry_drops_once_and_non_minis_do_not_change_state(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / 'raid.db')) as db:
        await run_migrations(db)
        service = RaidBossService(None, db)
        await state_for(db)
        async with db.acquire() as connection:
            await save_difficulty(connection, 'a', MiniDifficulty(2, 1, 2))
        monkeypatch.setattr('rpg_minigame.service.random.choices', lambda *args, **kwargs: [35000])
        await service.spawn('a', 'melee', RaidBossConfig(), 'mini')
        for stream in range(4):
            await service.register_stream('a', str(stream))
        assert await state_for(db) == MiniDifficulty(1)
        await service.resolve('a', False)
        assert await state_for(db) == MiniDifficulty(1)
        await encounter(service, db, monkeypatch, 150000, tier='main', win=False)
        assert await state_for(db) == MiniDifficulty(1)


@pytest.mark.asyncio
async def test_resolution_rolls_back_difficulty_on_reward_failure(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / 'raid.db')) as db:
        await run_migrations(db)
        service = RaidBossService(None, db)
        monkeypatch.setattr('rpg_minigame.service.random.choices', lambda *args, **kwargs: [10000])
        event = await service.spawn('a', 'melee', RaidBossConfig(), 'mini')
        await service.register_stream('a', 'one')
        async def fail(*args):
            raise RuntimeError('reward failure')
        monkeypatch.setattr(service, '_add_points', fail)
        with pytest.raises(RuntimeError, match='reward failure'):
            await service.resolve('a', True, 'user', 'user')
        assert (await service.get_active_event('a')).id == event.id
        assert await state_for(db) == MiniDifficulty()
        await asyncio.gather(service.resolve('a', True), service.resolve('a', True))
        assert await state_for(db) == MiniDifficulty(1)


@pytest.mark.asyncio
async def test_bootstrap_uses_unique_mini_participants_only_once(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'raid.db')) as db:
        await run_migrations(db)
        async with db.acquire() as connection:
            async def history(tier, count):
                row = await connection.fetchone("INSERT INTO raid_boss_events (broadcaster_id,boss_name,boss_type,boss_tier,max_hp,current_hp,reward_pool,final_hit_reward,status,spawned_at,stream_limit) VALUES ('a','Boss','melee',?,70000,0,70000,1000,'defeated','2026-10-04',3) RETURNING id", (tier,))
                for user in range(count):
                    await connection.execute("INSERT INTO raid_boss_attacks (event_id,broadcaster_id,stream_id,user_id,username,damage,attacked_at) VALUES (?,'a','s',?,?,100,'2026-10-04')", (row['id'], str(user), str(user)))
                return row['id']
            event_id = await history('mini', 19)
            await connection.execute("INSERT INTO raid_boss_bonus_contributions VALUES (?,'s','0',1,'a','0','0',100)", (event_id,))
            await connection.execute("INSERT INTO raid_boss_bonus_contributions VALUES (?,'s','1',1,'a','supporter','supporter',100)", (event_id,))
            await history('main', 40)
            await history('tutorial', 50)
            assert await load_difficulty(connection, 'a') == MiniDifficulty(2)
            await history('mini', 3)
            assert await load_difficulty(connection, 'a') == MiniDifficulty(2)
        await run_migrations(db)
        assert await state_for(db) == MiniDifficulty(2)


@pytest.mark.asyncio
async def test_upgrade_preserves_active_boss_and_disabled_streams(tmp_path, monkeypatch):
    from storage import migration_runner
    migrations = migration_runner.MIGRATIONS
    async with asqlite.create_pool(str(tmp_path / 'upgrade.db')) as db:
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', tuple(m for m in migrations if m.version < 61))
        await run_migrations(db)
        async with db.acquire() as connection:
            await connection.execute("INSERT INTO raid_boss_events (broadcaster_id,boss_name,boss_type,boss_tier,max_hp,current_hp,reward_pool,final_hit_reward,status,spawned_at,stream_limit) VALUES ('a','Existing','melee','mini',35000,12345,35000,1000,'active','2026-10-04',3)")
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', migrations)
        await run_migrations(db)
        enabled = False
        service = RaidBossService(None, db, enabled_provider=lambda channel: enabled)
        event, reward = await service.register_stream('a', 'disabled-stream')
        assert (event.max_hp, event.current_hp, event.streams_used, reward) == (35000, 12345, 0, 0)
        assert await service.spawn('a', 'magic', RaidBossConfig(), 'mini') is None
        enabled = True
        await service.register_stream('a', 'enabled-stream')
        await service.resolve('a', True)
        assert await state_for(db) == MiniDifficulty(2)
