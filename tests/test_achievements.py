import asqlite
import pytest

from bot.services.channels.achievements import AchievementService
from storage.migration_runner import run_migrations
from storage.migrations import MIGRATIONS


async def imported(connection, channel, count, user="viewer"):
    await connection.execute("""
        INSERT INTO imported_redeem_totals (broadcaster_id, user_id, username, redeem_type, claim_count)
        VALUES (?, ?, 'viewer', 'daily', ?)
        ON CONFLICT(broadcaster_id, user_id, redeem_type) DO UPDATE SET claim_count = excluded.claim_count
    """, (channel, user, count))


@pytest.mark.asyncio
async def test_achievement_history_unique_channels_and_permanent_tiers(tmp_path):
    async with asqlite.create_pool(str(tmp_path / "achievements.db")) as db:
        async with db.acquire() as c:
            for migration in MIGRATIONS[:28]:
                await migration.run(c)
            await imported(c, "a", 100)
            await imported(c, "b", 0)
            await MIGRATIONS[28].run(c)
            rows = await c.fetchall("SELECT * FROM achievement_unlocks")
            assert len(rows) == 6  # explorer bronze, regular bronze/silver, familiar bronze/silver/gold
            assert all(row["unlocked_at"] is None for row in rows)
            await imported(c, "a", 100)
            assert len(await c.fetchall("SELECT * FROM achievement_unlocks")) == 6
            for channel in ("b", "c", "d", "e"):
                await imported(c, channel, 1)
            assert await c.fetchone("SELECT 1 FROM achievement_unlocks WHERE achievement_id='explorer' AND tier=2")
            assert not await c.fetchone("SELECT 1 FROM achievement_unlocks WHERE broadcaster_id='b' AND achievement_id='familiar'")
            await imported(c, "a", 0)
            assert await c.fetchone("SELECT 1 FROM achievement_unlocks WHERE achievement_id='familiar' AND tier=3")
            assert not await c.fetchone("SELECT 1 FROM achievement_unlocks WHERE user_id='other'")


@pytest.mark.asyncio
async def test_live_claim_unlock_timestamp_and_rollback(tmp_path):
    async with asqlite.create_pool(str(tmp_path / "live.db")) as db:
        await run_migrations(db)
        async with db.acquire() as c:
            await imported(c, "a", 9)
            await c.execute("BEGIN")
            await c.execute("INSERT INTO redeem_claims (broadcaster_id,user_id,username,redeem_type,stream_id,created_at) VALUES ('a','viewer','renamed','daily','s1','2026-09-13 12:00:00')")
            row = await c.fetchone("SELECT * FROM achievement_unlocks WHERE achievement_id='familiar'")
            assert row["unlocked_at"] == "2026-09-13 12:00:00"
            await c.rollback()
            assert not await c.fetchone("SELECT 1 FROM achievement_unlocks WHERE achievement_id='familiar'")
            await c.execute("INSERT INTO redeem_claims (broadcaster_id,user_id,username,redeem_type,stream_id) VALUES ('a','viewer','renamed','first','s1')")
            assert not await c.fetchone("SELECT 1 FROM achievement_unlocks WHERE achievement_id='familiar'")
        collection = await AchievementService(db).get_collection("viewer", lambda channel: {"display_name": channel})
        assert collection["unlocked"] == 1
        familiar = next(card for card in collection["cards"] if card["scope"] == "channel")
        assert familiar["progress"] == 9
        assert familiar["tier"] == "Locked"
        assert familiar["next_tier"]["threshold"] == 10
        empty = await AchievementService(db).get_collection("unknown", lambda channel: {})
        assert len(empty["cards"]) == 2
        assert empty["unlocked"] == 0
