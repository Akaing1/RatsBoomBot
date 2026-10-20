import asqlite
import pytest

from pets.passives import LOYALTY_GAIN
from pets.service import PetService
from storage import migration_runner
from storage.migrations import Migration
from storage.migrations.v065_incoming_raid_recency import migrate as migrate_incoming_raids


@pytest.mark.asyncio
@pytest.mark.parametrize('already_applied_65', [False, True])
@pytest.mark.parametrize('hen_exists', [False, True])
async def test_repair_development_migration_collision(tmp_path, monkeypatch, already_applied_65, hen_exists):
    migrations = migration_runner.MIGRATIONS
    old_migrations = tuple(m for m in migrations if m.version < 64) + (
        Migration(version=64, name='incoming_raid_recency', run=migrate_incoming_raids),
    )
    if already_applied_65:
        old_migrations += tuple(m for m in migrations if m.version == 65)
    async with asqlite.create_pool(str(tmp_path / 'collision.db')) as database:
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', old_migrations)
        await migration_runner.run_migrations(database)
        pets = PetService(database)
        bat = await pets.grant_bat('viewer')
        async with database.acquire() as connection:
            await connection.execute(
                'INSERT INTO incoming_raid_recency VALUES (?, ?, ?)', ('channel', 'raider', 123.0)
            )
            if hen_exists:
                await connection.execute(
                    'INSERT INTO pet_definitions (id, display_name, rarity, sprite_path, frame_count, max_level) '
                    'VALUES (?, ?, ?, ?, ?, ?)',
                    ('honey_hen', 'Custom Hen', 'common', '/custom.png', 4, 50),
                )
            await connection.commit()
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', migrations)
        await migration_runner.run_migrations(database)
        await migration_runner.run_migrations(database)
        assert (await pets.get_equipped_pet('viewer')).user_pet_id == bat.user_pet_id
        async with database.acquire() as connection:
            hen = await connection.fetchone('SELECT display_name FROM pet_definitions WHERE id = ?', ('honey_hen',))
            assert hen['display_name'] == ('Custom Hen' if hen_exists else 'Honey Hen')
            raids = await connection.fetchall('SELECT * FROM incoming_raid_recency')
            assert len(raids) == 1
            assert (raids[0]['broadcaster_id'], raids[0]['raider_id'], raids[0]['received_at']) == ('channel', 'raider', 123.0)
            history = await connection.fetchall('SELECT version, name FROM schema_migrations WHERE version BETWEEN 64 AND 66 ORDER BY version')
            assert [(row['version'], row['name']) for row in history] == [
                (64, 'incoming_raid_recency'), (65, 'incoming_raid_recency'), (66, 'repair_honey_hen_collision'),
            ]


@pytest.mark.asyncio
async def test_honey_hen_upgrade_and_repeat_grant_preserve_existing_loadout(tmp_path, monkeypatch):
    migrations = migration_runner.MIGRATIONS
    async with asqlite.create_pool(str(tmp_path / 'honey-hen.db')) as database:
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', tuple(m for m in migrations if m.version < 64))
        await migration_runner.run_migrations(database)
        pets = PetService(database)
        bat = await pets.grant_bat('viewer')
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', migrations)
        await migration_runner.run_migrations(database)
        await migration_runner.run_migrations(database)
        assert (await pets.get_equipped_pet('viewer')).user_pet_id == bat.user_pet_id

        hen = await pets.grant_pet('viewer', 'honey_hen', LOYALTY_GAIN)
        async with database.acquire() as connection:
            await connection.execute('UPDATE user_pets SET level = 5, xp = 42 WHERE id = ?', (hen.user_pet_id,))
            await connection.commit()
        repeated = await pets.grant_pet('viewer', 'honey_hen', LOYALTY_GAIN)
        assert repeated.user_pet_id == hen.user_pet_id
        assert (repeated.level, repeated.xp) == (5, 42)
        assert (repeated.display_name, repeated.rarity, repeated.sprite_path, repeated.frame_count) == (
            "Honey Hen", 'common', '/assets/Honey%20Hen.png', 4
        )
        assert repeated.passive_type == LOYALTY_GAIN
        assert hen.passive_percent == 10
        assert len(await pets.get_collection('viewer')) == 2
        await pets.grant_pet('viewer', 'royal_raven', 'raid_profit')
        assert await pets.bonus_bps('viewer', LOYALTY_GAIN) == 0
        assert (await pets.equip('viewer', "Honey Hen")).user_pet_id == hen.user_pet_id
