import asqlite
import pytest

from bot.profiles import RaidBossConfig
from bot.services.engagement.points import PointsService
from pets import PetService
from pets.passives import (
    GAMBLE_LOSS_REFUND, GAMBLE_ODDS, KAMIKAZE_ODDS, PASSIVES,
    RAID_DAMAGE, RAID_PROFIT, RARE_DROP_CHANCE, scaled_bps,
)
from rpg_minigame import RaidBossService
from storage.migration_runner import run_migrations


@pytest.mark.asyncio
async def test_rat_and_passive_tiers_are_seeded_and_level_scaled(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'pets.db')) as db:
        await run_migrations(db)
        pets = PetService(db)
        rat = await pets.grant_rat('viewer')
        assert (rat.pet_id, rat.display_name, rat.rarity, rat.sprite_path, rat.frame_count) == ('explosive_rat', 'Little Rat', 'common', '/assets/Explosive%20Rat.png', 4)
        assert rat.passive_type == RAID_DAMAGE
        assert (rat.passive_rarity, rat.passive_percent) == ('common', 10)

        async with db.acquire() as conn:
            rows = await conn.fetchall('SELECT id, rarity, min_bps, max_bps FROM pet_passive_definitions')
            await conn.execute('UPDATE user_pets SET level=50 WHERE id=?', (rat.user_pet_id,))
        assert {row['id'] for row in rows} == set(PASSIVES)
        assert {row['rarity'] for row in rows} == {'common', 'rare', 'ultra_rare'}
        assert (await pets.get_equipped_pet('viewer')).passive_percent == 20
        assert scaled_bps(500, 1000, 1, 50) == 500
        assert scaled_bps(500, 1000, 50, 50) == 1000
        assert scaled_bps(100, 500, 50, 50) == 500


@pytest.mark.asyncio
async def test_rat_passives_follow_equipped_pet_and_preserve_bat(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'pets.db')) as db:
        await run_migrations(db)
        pets = PetService(db)
        bat = await pets.grant_poc_bat('viewer')
        assert bat.passive_percent == 10
        await pets.grant_rat('viewer', GAMBLE_ODDS)
        assert await pets.gamble_win_chance('viewer', .5) == .55
        assert await pets.bonus_bps('viewer', RAID_DAMAGE) == 0
        await pets.grant_poc_bat('viewer')
        assert (await pets.get_equipped_pet('viewer')).user_pet_id == bat.user_pet_id
        assert await pets.gamble_win_chance('viewer', .5) == .5
        assert await pets.bonus_bps('viewer', 'loyalty_gain') == 1000


@pytest.mark.asyncio
async def test_gamble_refund_only_reduces_actual_gamble_loss(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'pets.db')) as db:
        await run_migrations(db)
        pets = PetService(db)
        await pets.grant_rat('viewer', GAMBLE_LOSS_REFUND)
        points = PointsService(None, db, pets=pets)
        await points.add_points('channel', 'viewer', 'viewer', 1000, earned=False)
        assert await points.settle_wager('channel', 'viewer', 'viewer', 100, 0, game='gamble') == 910
        assert await points.settle_wager('channel', 'viewer', 'viewer', 100, 0, game='roulette') == 810
        async with db.acquire() as conn:
            outcomes = await conn.fetchone("SELECT wins, losses FROM viewer_gamble_outcomes WHERE broadcaster_id='channel' AND user_id='viewer'")
            totals = await conn.fetchone("SELECT winnings, losses FROM viewer_gambling_totals WHERE broadcaster_id='channel' AND user_id='viewer'")
        assert (outcomes['wins'], outcomes['losses']) == (0, 1)
        assert (totals['winnings'], totals['losses']) == (0, 190)


@pytest.mark.asyncio
async def test_rat_damage_and_profit_change_raid_results(tmp_path, monkeypatch):
    monkeypatch.setattr('rpg_minigame.service.random.random', lambda: 1.0)
    async with asqlite.create_pool(str(tmp_path / 'pets.db')) as db:
        await run_migrations(db)
        pets = PetService(db)
        service = RaidBossService(None, db, pets=pets)
        config = RaidBossConfig(tutorial_enabled=False, max_hp=1000, base_damage_min=100, base_damage_max=100, critical_chance=0)
        await service.spawn('channel', 'melee', config)
        await pets.grant_rat('viewer', RAID_DAMAGE)
        result = await service.attack('channel', 'stream', 'viewer', 'viewer', config)
        assert result.damage == 110
        assert result.current_hp == 890

        await pets.grant_rat('profit-viewer', RAID_PROFIT)
        async with db.acquire() as conn:
            await conn.execute("INSERT INTO raid_boss_attacks (event_id,stream_id,attack_number,broadcaster_id,user_id,username,damage,attacked_at) VALUES (1,'stream',1,'channel','profit-viewer','profit-viewer',100,'2026-09-29')")
            await conn.execute("UPDATE raid_boss_events SET current_hp=790 WHERE id=1")
        # The top contributor earns 157 points; the second earns 105 plus 10%.
        reward = await service.resolve('channel', defeated=False)
        assert reward == 272
        assert await PointsService(None, db).get_points('channel', 'profit-viewer') == 115


@pytest.mark.asyncio
async def test_rare_passive_adds_only_to_mythical_weapon_roll(tmp_path, monkeypatch):
    monkeypatch.setattr('rpg_minigame.service.random.random', lambda: 0.035)
    async with asqlite.create_pool(str(tmp_path / 'pets.db')) as db:
        await run_migrations(db)
        pets = PetService(db)
        await pets.grant_rat('viewer', RARE_DROP_CHANCE)
        service = RaidBossService(None, db, pets=pets)
        config = RaidBossConfig(tutorial_enabled=False, max_hp=100, base_damage_min=100, base_damage_max=100, critical_chance=0,
                                top_contributor_unique_drop_chance=.03, basic_weapon_drop_chance=0, blessed_unique_drop_chance=0)
        await service.spawn('channel', 'melee', config)
        result = await service.attack('channel', 'stream', 'viewer', 'viewer', config)
        assert ('viewer', 'mythical_blade') in result.drops
        assert len(result.drops) == 1
