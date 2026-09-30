import asyncio

import asqlite
import pytest

from pets.passives import GAMBLE_ODDS, LOYALTY_GAIN, RAID_DAMAGE
from pets.service import PetService
from storage.migration_runner import run_migrations


async def fund(database, points=100_000):
    async with database.acquire() as connection:
        await connection.execute("INSERT INTO viewers (broadcaster_id, user_id, username, points) VALUES ('source', 'viewer', 'viewer', ?)", (points,))
        await connection.commit()


async def balance(database):
    async with database.acquire() as connection:
        return int((await connection.fetchone("SELECT points FROM viewers WHERE broadcaster_id = 'source' AND user_id = 'viewer'"))["points"])


@pytest.mark.asyncio
@pytest.mark.parametrize('roll,pet_id,passive,rarity,refund', [
    (0, 'explosive_rat', LOYALTY_GAIN, 'common', 12_500),
    (1, 'dungeon_bat', GAMBLE_ODDS, 'common', 12_500),
    (2, 'sleepy_fox', RAID_DAMAGE, 'common', 12_500),
])
async def test_summon_boundaries_fixed_passives_and_duplicate_refund(tmp_path, monkeypatch, roll, pet_id, passive, rarity, refund):
    monkeypatch.setattr('pets.service.randbelow', lambda bound: roll if bound == 3 else 69)
    async with asqlite.create_pool(str(tmp_path / 'pets.db')) as database:
        await run_migrations(database)
        await fund(database)
        pets = PetService(database)
        assert await pets.buy_ticket('source', 'viewer') == 50_000
        assert await pets.ticket_count('viewer') == 1
        result = await pets.summon('viewer', 'viewer')
        assert (result.pet_id, result.rarity, result.duplicate, result.equipped) == (pet_id, rarity, False, True)
        pet = await pets.get_equipped_pet('viewer')
        assert pet.passive_type == passive
        assert (pet.level, pet.xp) == (1, 0)
        await pets.buy_ticket('source', 'viewer')
        duplicate = await pets.summon('viewer', 'viewer')
        assert duplicate.duplicate and duplicate.refund == refund
        assert duplicate.refund_channel == 'source'
        assert await balance(database) == refund
        assert await pets.ticket_count('viewer') == 0
        assert len(await pets.get_collection('viewer')) == 1
        with pytest.raises(ValueError, match='no summon tickets'):
            await pets.summon('viewer', 'viewer')
        assert await balance(database) == refund


@pytest.mark.asyncio
async def test_purchase_is_channel_local_and_atomic(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'pets.db')) as database:
        await run_migrations(database)
        await fund(database, 50_000)
        pets = PetService(database)
        with pytest.raises(ValueError, match='50,000'):
            await pets.buy_ticket('other-channel', 'viewer')
        assert await pets.ticket_count('viewer') == 0
        results = await asyncio.gather(pets.buy_ticket('source', 'viewer'), pets.buy_ticket('source', 'viewer'), return_exceptions=True)
        assert sum(isinstance(result, ValueError) for result in results) == 1
        assert await balance(database) == 0
        assert await pets.ticket_count('viewer') == 1


@pytest.mark.asyncio
async def test_global_collection_equip_and_concurrent_summons(tmp_path, monkeypatch):
    monkeypatch.setattr('pets.service.randbelow', lambda _: 0)
    async with asqlite.create_pool(str(tmp_path / 'pets.db')) as database:
        await run_migrations(database)
        await fund(database)
        pets = PetService(database)
        bat = await pets.grant_poc_bat('viewer')
        await pets.buy_ticket('source', 'viewer')
        results = await asyncio.gather(pets.summon('viewer', 'viewer'), pets.summon('viewer', 'viewer'), return_exceptions=True)
        assert sum(isinstance(result, ValueError) for result in results) == 1
        assert (await pets.get_equipped_pet('viewer')).user_pet_id == bat.user_pet_id
        assert len(await pets.get_collection('viewer')) == 2
        assert (await pets.equip('viewer', 'Little Rat')).passive_type == LOYALTY_GAIN
        assert await pets.bonus_bps('viewer', GAMBLE_ODDS) == 0
        with pytest.raises(ValueError, match="don't own"):
            await pets.equip('other-user', 'Little Rat')
        assert await pets.get_equipped_pet('other-user') is None


@pytest.mark.asyncio
async def test_failed_summon_rolls_back_ticket_and_pet(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / 'pets.db')) as database:
        await run_migrations(database)
        await fund(database)
        pets = PetService(database)
        await pets.buy_ticket('source', 'viewer')
        def fail(_):
            raise RuntimeError('roll failed')
        monkeypatch.setattr('pets.service.randbelow', fail)
        with pytest.raises(RuntimeError, match='roll failed'):
            await pets.summon('viewer', 'viewer')
        assert await pets.ticket_count('viewer') == 1
        assert await pets.get_collection('viewer') == []
        assert await balance(database) == 50_000


@pytest.mark.asyncio
@pytest.mark.parametrize('alias', ['ticket', 'summon', 'summon ticket', 'SUMMON   TICKET'])
async def test_purchase_command_aliases(alias):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from bot.shared.commands.pets import PetsCommands
    service = SimpleNamespace(buy_ticket=AsyncMock(return_value=123))
    features = SimpleNamespace(is_global_command_enabled=lambda *_: True, is_enabled=lambda *_: True)
    command = PetsCommands(SimpleNamespace(services=SimpleNamespace(pets=service, features=features)))
    ctx = SimpleNamespace(broadcaster=SimpleNamespace(id='source'), chatter=SimpleNamespace(id='viewer'), reply=AsyncMock())
    await command.buy.callback(command, ctx, item=alias)
    service.buy_ticket.assert_awaited_once_with('source', 'viewer')
    assert '50,000' in ctx.reply.call_args.args[0]


@pytest.mark.asyncio
async def test_pet_commands_respect_disabled_flags():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from bot.shared.commands.pets import PetsCommands
    service = SimpleNamespace(buy_ticket=AsyncMock())
    features = SimpleNamespace(is_global_command_enabled=lambda *_: True, is_enabled=lambda *_: False)
    command = PetsCommands(SimpleNamespace(services=SimpleNamespace(pets=service, features=features)))
    ctx = SimpleNamespace(broadcaster=SimpleNamespace(id='source'), chatter=SimpleNamespace(id='viewer'), reply=AsyncMock())
    await command.buy.callback(command, ctx, item='ticket')
    service.buy_ticket.assert_not_awaited()
    assert 'disabled' in ctx.reply.call_args.args[0]
    features.is_global_command_enabled = lambda *_: False
    ctx.reply.reset_mock()
    await command.pets.callback(command, ctx)
    ctx.reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_selected_passive_migration_preserves_collection_loadout_and_progress(tmp_path, monkeypatch):
    from storage import migration_runner
    async with asqlite.create_pool(str(tmp_path / 'pets.db')) as database:
        migrations = migration_runner.MIGRATIONS
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', tuple(m for m in migrations if m.version < 58))
        await migration_runner.run_migrations(database)
        pets = PetService(database)
        bat = await pets.grant_pet('viewer', 'dungeon_bat', LOYALTY_GAIN)
        rat = await pets.grant_pet('viewer', 'explosive_rat', RAID_DAMAGE)
        fox = await pets.grant_pet('viewer', 'sleepy_fox', 'gamble_loss_refund')
        async with database.acquire() as connection:
            await connection.execute("UPDATE user_pets SET level = 3, xp = 42 WHERE user_id = 'viewer'")
            await connection.commit()
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', migrations)
        await migration_runner.run_migrations(database)
        collection = {pet.pet_id: pet for pet in await pets.get_collection('viewer')}
        for old, passive, bps in [(bat, GAMBLE_ODDS, 500), (rat, LOYALTY_GAIN, 1000), (fox, RAID_DAMAGE, 1000)]:
            pet = collection[old.pet_id]
            assert (pet.user_pet_id, pet.passive_type, pet.passive_value_bps) == (old.user_pet_id, passive, bps)
            assert (pet.level, pet.xp) == (3, 42)
        assert (await pets.get_equipped_pet('viewer')).user_pet_id == fox.user_pet_id


@pytest.mark.asyncio
@pytest.mark.parametrize('roll,expected', [
    (0, 'dungeon_bat'), (69, 'dungeon_bat'),
    (70, 'explosive_rat'), (89, 'explosive_rat'),
    (90, 'sleepy_fox'), (99, 'sleepy_fox'),
])
async def test_rarity_roll_boundaries_before_pet_selection(tmp_path, monkeypatch, roll, expected):
    draws = []
    def choose(bound):
        draws.append(bound)
        return roll if bound == 100 else 0
    monkeypatch.setattr('pets.service.randbelow', choose)
    async with asqlite.create_pool(str(tmp_path / 'pets.db')) as database:
        await run_migrations(database)
        await fund(database)
        async with database.acquire() as connection:
            await connection.execute("UPDATE pet_definitions SET rarity = 'rare' WHERE id = 'explosive_rat'")
            await connection.execute("UPDATE pet_definitions SET rarity = 'ultra_rare' WHERE id = 'sleepy_fox'")
            await connection.commit()
        pets = PetService(database)
        rates = await pets.get_summon_rates()
        assert [tier['effective_percent'] for tier in rates] == [70, 20, 10]
        await pets.buy_ticket('source', 'viewer')
        assert (await pets.summon('viewer', 'viewer')).pet_id == expected
        assert draws == [100, 1]


@pytest.mark.asyncio
async def test_common_only_rates_are_uniform_and_empty_tiers_disabled(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'pets.db')) as database:
        await run_migrations(database)
        pets = PetService(database)
        rates = await pets.get_summon_rates()
        assert [tier['base_percent'] for tier in rates] == [70, 20, 10]
        assert [tier['effective_percent'] for tier in rates] == [100, 0, 0]
        assert {pet['display_name'] for pet in rates[0]['pets']} == {'Silly Bat', 'Little Rat', 'Sleepy Fox'}
        assert [pet['percent'] for pet in rates[0]['pets']] == pytest.approx([100 / 3] * 3)
        assert rates[1]['pets'] == rates[2]['pets'] == []


@pytest.mark.asyncio
async def test_partial_pool_normalizes_and_empty_catalog_keeps_ticket(tmp_path, monkeypatch):
    monkeypatch.setattr('pets.service.randbelow', lambda bound: 70 if bound == 80 else 0)
    async with asqlite.create_pool(str(tmp_path / 'pets.db')) as database:
        await run_migrations(database)
        await fund(database)
        async with database.acquire() as connection:
            await connection.execute("UPDATE pet_definitions SET rarity = 'ultra_rare' WHERE id = 'sleepy_fox'")
            await connection.commit()
        pets = PetService(database)
        assert [tier['effective_percent'] for tier in await pets.get_summon_rates()] == [87.5, 0, 12.5]
        await pets.buy_ticket('source', 'viewer')
        assert (await pets.summon('viewer', 'viewer')).pet_id == 'sleepy_fox'
        await pets.buy_ticket('source', 'viewer')
        # Unsupported tiers cannot be summoned even if catalog rows exist.
        async with database.acquire() as connection:
            await connection.execute("UPDATE pet_definitions SET rarity = 'unavailable'")
            await connection.commit()
        with pytest.raises(ValueError, match='No pets are available'):
            await pets.summon('viewer', 'viewer')
        assert await pets.ticket_count('viewer') == 1
