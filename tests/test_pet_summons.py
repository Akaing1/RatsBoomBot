import asyncio

import asqlite
import pytest

from pets.passives import GAMBLE_LOSS_REFUND, KAMIKAZE_ODDS, LOYALTY_GAIN
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
    (0, 'dungeon_bat', LOYALTY_GAIN, 'common', 12_500),
    (6999, 'dungeon_bat', LOYALTY_GAIN, 'common', 12_500),
    (7000, 'explosive_rat', KAMIKAZE_ODDS, 'rare', 25_000),
    (8999, 'explosive_rat', KAMIKAZE_ODDS, 'rare', 25_000),
    (9000, 'sleepy_fox', GAMBLE_LOSS_REFUND, 'ultra_rare', 50_000),
    (9999, 'sleepy_fox', GAMBLE_LOSS_REFUND, 'ultra_rare', 50_000),
])
async def test_summon_boundaries_fixed_passives_and_duplicate_refund(tmp_path, monkeypatch, roll, pet_id, passive, rarity, refund):
    monkeypatch.setattr('pets.service.randbelow', lambda _: roll)
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
    monkeypatch.setattr('pets.service.randbelow', lambda _: 7000)
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
        assert (await pets.equip('viewer', 'Explosive Rat')).passive_type == KAMIKAZE_ODDS
        assert await pets.bonus_bps('viewer', LOYALTY_GAIN) == 0
        with pytest.raises(ValueError, match="don't own"):
            await pets.equip('other-user', 'Explosive Rat')
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
