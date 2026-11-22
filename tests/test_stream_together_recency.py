from types import SimpleNamespace
from unittest.mock import AsyncMock

import asqlite
import pytest

from bot.services.channels.stream_together import StreamTogetherService
from storage import stream_together_recency
from storage.migrations.core.v001_initial_schema import migrate as migrate_initial
from storage.migrations.core.v008_chatter_identities import migrate as migrate_identities
from storage.migrations.core.v013_chatter_profiles import migrate as migrate_stats
from storage.migrations.core.v085_last_streamed_together import migrate


@pytest.mark.asyncio
async def test_recent_partners_persist_decay_expire_and_stay_scoped(tmp_path, monkeypatch):
    now = 2_000_000_000
    monkeypatch.setattr(stream_together_recency.time, "time", lambda: now)
    path = str(tmp_path / "recent-partners.db")
    async with asqlite.create_pool(path) as db:
        async with db.acquire() as connection:
            await migrate_initial(connection)
            await migrate_identities(connection)
            await migrate_stats(connection)
            await connection.execute("""
                INSERT INTO chatter_channel_stats (broadcaster_id, user_id, messages_sent, lifetime_points_earned)
                VALUES ('1', '2', 25, 100)
            """)
            tables_before = await connection.fetchall("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
            await migrate(connection)
            tables_after = await connection.fetchall("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
            assert [row["name"] for row in tables_before] == [row["name"] for row in tables_after]
            row = await connection.fetchone("SELECT * FROM chatter_channel_stats WHERE broadcaster_id = '1' AND user_id = '2'")
            assert row["last_streamed_together_at"] is None
        await stream_together_recency.record_stream_together_participants(db, "1", ["2", "3"])
        await stream_together_recency.record_stream_together_participants(db, "other", ["4"])
        async with db.acquire() as connection:
            row = await connection.fetchone("SELECT * FROM chatter_channel_stats WHERE broadcaster_id = '1' AND user_id = '2'")
            assert row["messages_sent"] == 25
            assert row["lifetime_points_earned"] == 100
            row = await connection.fetchone("SELECT * FROM chatter_channel_stats WHERE broadcaster_id = '1' AND user_id = '3'")
            assert row["messages_sent"] == row["lifetime_points_earned"] == 0
    recorded_at = now
    async with asqlite.create_pool(path) as db:
        for hours, boost in [(0, 2500), (12, 1850), (24, 1200), (36, 900), (48, 600), (60, 300)]:
            now = recorded_at + hours * 3600
            weights = await stream_together_recency.recent_stream_together_participants(db, "1")
            assert {user_id: round(weight * stream_together_recency.STREAM_TOGETHER_INITIAL_BOOST)
                    for user_id, weight in weights.items()} == {"2": boost, "3": boost}
        now = recorded_at + 36 * 3600
        assert await stream_together_recency.recent_stream_together_participants(db, "1") == {"2": .36, "3": .36}
        await stream_together_recency.record_stream_together_participants(db, "1", ["2"])
        assert await stream_together_recency.recent_stream_together_participants(db, "1") == {"2": 1, "3": .36}
        now += stream_together_recency.RECENT_STREAM_TOGETHER_SECONDS
        assert await stream_together_recency.recent_stream_together_participants(db, "1") == {}
    assert await stream_together_recency.recent_stream_together_participants(None, "1") == {}


@pytest.mark.asyncio
async def test_participant_recording_excludes_self_batches_and_throttles(monkeypatch):
    import bot.services.channels.stream_together as module
    clock = [100]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    record = AsyncMock()
    monkeypatch.setattr(module, "record_stream_together_participants", record)
    db = object()
    service = StreamTogetherService(None, db=db)
    await service.remember_participants("1", ["1", "2", "2", "bad"])
    record.assert_awaited_once_with(db, "1", {"2"})
    await service.remember_participants("1", ["1", "2", "3"])
    assert record.await_count == 2
    assert record.await_args.args == (db, "1", {"3"})
    await service.remember_participants("1", ["2", "3"])
    assert record.await_count == 2
    clock[0] += 60
    await service.remember_participants("1", ["2", "3"])
    assert record.await_args.args == (db, "1", {"2", "3"})


@pytest.mark.asyncio
async def test_shared_chat_records_participants_only_after_successful_lookup(monkeypatch):
    from unittest.mock import Mock
    import httpx
    from bot.services.channels.live_chat import LiveChatService
    live = LiveChatService(None, bot=SimpleNamespace(tokens={"1": {"token": "test"}}))
    live.client = Mock()
    live._fetch_twitch_emote_page = AsyncMock(return_value={"data": [{"participants": [
        {"broadcaster_id": "1"}, {"broadcaster_id": "2"}]}]})
    live._fetch_twitch_owner_names = AsyncMock(return_value={"2": "Friend"})
    live.stream_together.remember_participants = AsyncMock()
    await live.shared_chat_participants("1", refresh=True)
    live.stream_together.remember_participants.assert_awaited_once_with("1", {"2"})
    live._fetch_twitch_emote_page.side_effect = httpx.ConnectError("offline")
    await live.shared_chat_participants("1", refresh=True)
    assert live.stream_together.remember_participants.await_count == 1
