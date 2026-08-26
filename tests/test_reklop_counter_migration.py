import asqlite
import pytest

from storage.migrations.v009_reklop_counter_700 import migrate


@pytest.mark.asyncio
async def test_reklop_counter_is_set_to_700(tmp_path):
    database = await asqlite.create_pool(tmp_path / "tokens.db")

    async with database.acquire() as connection:
        await connection.execute("CREATE TABLE counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL DEFAULT 0)")
        await connection.execute("INSERT INTO counters (name, value) VALUES ('reklop', 42)")
        await migrate(connection)
        row = await connection.fetchone("SELECT value FROM counters WHERE name = 'reklop'")

    await database.close()

    assert row["value"] == 700


@pytest.mark.asyncio
async def test_reklop_counter_is_created_at_700(tmp_path):
    database = await asqlite.create_pool(tmp_path / "tokens.db")

    async with database.acquire() as connection:
        await connection.execute("CREATE TABLE counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL DEFAULT 0)")
        await migrate(connection)
        row = await connection.fetchone("SELECT value FROM counters WHERE name = 'reklop'")

    await database.close()

    assert row["value"] == 700
