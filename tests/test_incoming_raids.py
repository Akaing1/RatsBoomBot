from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import asqlite
import pytest

from storage import incoming_raids
from storage.migrations.core.v065_incoming_raid_recency import migrate
from bot.shared.events.raids import RaidEvents


@pytest.mark.asyncio
async def test_latest_raid_is_scoped_persistent_and_expires(tmp_path, monkeypatch):
    path = str(tmp_path / "incoming.db")
    now = 2_000_000_000
    monkeypatch.setattr(incoming_raids.time, "time", lambda: now)
    async with asqlite.create_pool(path) as db:
        async with db.acquire() as connection:
            await migrate(connection)
        await incoming_raids.record_incoming_raid(db, "1", "2")
        await incoming_raids.record_incoming_raid(db, "other", "3")
        now += incoming_raids.RECENT_RAID_SECONDS / 2
        assert await incoming_raids.recent_incoming_raids(db, "1") == {"2": 0.5}
        await incoming_raids.record_incoming_raid(db, "1", "2")
    async with asqlite.create_pool(path) as db:
        assert await incoming_raids.recent_incoming_raids(db, "1") == {"2": 1}
        now += incoming_raids.RECENT_RAID_SECONDS
        assert await incoming_raids.recent_incoming_raids(db, "1") == {}


@pytest.mark.asyncio
async def test_raid_records_even_when_raid_responses_are_disabled(monkeypatch):
    record = AsyncMock()
    monkeypatch.setattr("bot.shared.events.raids.record_incoming_raid", record)
    services = SimpleNamespace(db=object(), stream_logs=Mock(), features=Mock())
    services.features.is_enabled.return_value = False
    events = RaidEvents(SimpleNamespace(services=services))
    await events.handle_raid(SimpleNamespace(from_broadcaster=SimpleNamespace(id="2", name="raider"),
        to_broadcaster=SimpleNamespace(id="1", name="recipient"), viewer_count=5))
    record.assert_awaited_once_with(services.db, "1", "2")


@pytest.mark.asyncio
@pytest.mark.parametrize("count, expected", [(0, 0), (1, 1), (5, 5), (None, None), (-1, None), (True, None), ("5", None)])
async def test_outgoing_confirmation_updates_only_matching_pending_raid(monkeypatch, count, expected):
    record = AsyncMock()
    monkeypatch.setattr("bot.shared.events.raids.record_incoming_raid", record)
    raid = {"target_id": "2", "expires_at": 10**12}
    bot = SimpleNamespace(_dashboard_pending_raids={"1": raid}, services=SimpleNamespace(
        broadcasters=SimpleNamespace(get_broadcasters=lambda: {"1": object()})))
    events = RaidEvents(bot)
    payload = SimpleNamespace(from_broadcaster=SimpleNamespace(id="1", name="sender"),
                              to_broadcaster=SimpleNamespace(id="3", name="other"), viewer_count=count)
    await events.handle_raid(payload)
    assert "completed" not in raid
    assert "viewer_count" not in raid
    payload.to_broadcaster.id = "2"
    await events.handle_raid(payload)
    assert raid["completed"] is True
    assert raid["viewer_count"] == expected
    record.assert_not_awaited()
