import asyncio
import importlib
from pathlib import Path

import asqlite
import pytest

from storage import migration_runner
from storage.migrations import MIGRATIONS, Migration, validate_migrations


async def noop(connection):
    pass


@pytest.mark.parametrize('versions', [(1, 1), (1, 3), (2, 1), (0,), (-1,)])
def test_invalid_versions_are_rejected(versions):
    with pytest.raises(ValueError, match='Expected migration'):
        validate_migrations(tuple(Migration(v, 'example', noop) for v in versions))


def test_every_migration_file_is_registered_once():
    root = Path(__file__).resolve().parents[1] / 'storage' / 'migrations'
    modules = {
        'storage.migrations.' + '.'.join(path.relative_to(root).with_suffix('').parts)
        for path in root.rglob('v[0-9]*.py')
    }
    assert modules == {m.run.__module__ for m in MIGRATIONS}
    assert len(modules) == len(MIGRATIONS)
    for migration in MIGRATIONS:
        assert migration.run.__module__.rsplit('.', 1)[1] == f'v{migration.version:03d}_{migration.name}'
        assert importlib.import_module(migration.run.__module__).migrate is migration.run


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [RuntimeError, asyncio.CancelledError])
async def test_failed_migration_rolls_back_schema_data_and_history(tmp_path, monkeypatch, failure):
    async def first(connection):
        await connection.execute('CREATE TABLE sample (value TEXT)')
        await connection.execute("INSERT INTO sample VALUES ('original')")

    async def broken(connection):
        await connection.execute("UPDATE sample SET value = 'changed'")
        await connection.execute('CREATE TABLE partial (value TEXT)')
        raise failure()

    monkeypatch.setattr(migration_runner, 'MIGRATIONS', (
        Migration(1, 'first', first), Migration(2, 'broken', broken),
    ))
    async with asqlite.create_pool(str(tmp_path / 'rollback.db')) as db:
        with pytest.raises(failure):
            await migration_runner.run_migrations(db)
        async with db.acquire() as connection:
            assert (await connection.fetchone('SELECT value FROM sample'))['value'] == 'original'
            assert await connection.fetchone("SELECT name FROM sqlite_master WHERE name = 'partial'") is None
            assert await migration_runner.get_applied_versions(connection) == {1}
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', (
            Migration(1, 'first', first), Migration(2, 'broken', noop),
        ))
        await migration_runner.run_migrations(db)
        await migration_runner.run_migrations(db)
        async with db.acquire() as connection:
            assert await migration_runner.get_applied_versions(connection) == {1, 2}


@pytest.mark.asyncio
@pytest.mark.parametrize('history, message', [
    ([(1, 'wrong')], 'is named'),
    ([(1, 'first'), (2, 'newer')], 'unknown'),
    ([(2, 'second')], 'missing version'),
])
async def test_incompatible_history_stops_before_pending_migrations(tmp_path, monkeypatch, history, message):
    called = []

    async def pending(connection):
        called.append(True)

    registered = (Migration(1, 'first', pending),)
    if message == 'missing version':
        registered += (Migration(2, 'second', pending),)
    monkeypatch.setattr(migration_runner, 'MIGRATIONS', registered)
    async with asqlite.create_pool(str(tmp_path / 'history.db')) as db:
        async with db.acquire() as connection:
            await migration_runner.create_migration_table(connection)
            for version, name in history:
                await connection.execute('INSERT INTO schema_migrations (version, name) VALUES (?, ?)', (version, name))
            await connection.commit()
        with pytest.raises(ValueError, match=message):
            await migration_runner.run_migrations(db)
    assert not called


@pytest.mark.asyncio
async def test_fresh_install_records_complete_history_and_repeat_is_noop(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'fresh.db')) as db:
        await migration_runner.run_migrations(db)
        async with db.acquire() as connection:
            before = [tuple(row) for row in await connection.fetchall('SELECT * FROM schema_migrations ORDER BY version')]
        await migration_runner.run_migrations(db)
        async with db.acquire() as connection:
            after = [tuple(row) for row in await connection.fetchall('SELECT * FROM schema_migrations ORDER BY version')]
    assert before == after
    assert [(row[0], row[1]) for row in after] == [(m.version, m.name) for m in MIGRATIONS]


@pytest.mark.asyncio
@pytest.mark.parametrize('legacy_follower_index', [False, True])
async def test_upgrade_from_release_or_earlier_followers_branch(tmp_path, monkeypatch, legacy_follower_index):
    current = migration_runner.MIGRATIONS
    initial = tuple(migration for migration in current if migration.version <= 70)
    if legacy_follower_index:
        index = next(migration for migration in current if migration.name == 'follower_last_watched_index')
        initial += (Migration(71, index.name, index.run),)
    async with asqlite.create_pool(str(tmp_path / 'followers-upgrade.db')) as db:
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', initial)
        await migration_runner.run_migrations(db)
        async with db.acquire() as connection:
            await connection.execute("INSERT INTO viewers VALUES ('channel','viewer','viewer',123,0)")
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', current)
        await migration_runner.run_migrations(db)
        await migration_runner.run_migrations(db)
        async with db.acquire() as connection:
            history = await connection.fetchall('SELECT version,name FROM schema_migrations ORDER BY version')
            assert [(row['version'], row['name']) for row in history] == [(migration.version, migration.name) for migration in current]
            assert (await connection.fetchone("SELECT points FROM viewers WHERE broadcaster_id='channel' AND user_id='viewer'"))['points'] == 123
            assert await connection.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='channel_access'")
            assert await connection.fetchone("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_passive_point_payouts_follower_presence'")


@pytest.mark.asyncio
async def test_replacing_development_migration_history_is_transactional(tmp_path):
    async def broken(connection):
        await connection.execute('CREATE TABLE partial_repair (value TEXT)')
        raise RuntimeError('repair failed')
    async with asqlite.create_pool(str(tmp_path / 'repair-rollback.db')) as db:
        async with db.acquire() as connection:
            await migration_runner.create_migration_table(connection)
            await connection.execute("INSERT INTO schema_migrations (version,name) VALUES (71,'follower_last_watched_index')")
            with pytest.raises(RuntimeError, match='repair failed'):
                await migration_runner.run_migration(connection, Migration(71, 'channel_access', broken), superseded_name='follower_last_watched_index')
            assert (await connection.fetchone('SELECT name FROM schema_migrations WHERE version=71'))['name'] == 'follower_last_watched_index'
            assert await connection.fetchone("SELECT name FROM sqlite_master WHERE name='partial_repair'") is None
