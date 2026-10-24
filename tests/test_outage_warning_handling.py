import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from bot.profiles import LeagueConfig
from bot.services.engagement.league import LeagueProviderError, LeagueService, OpggMcpClient, SummonerNotFoundError
from bot.services.channels.live_chat import LiveChatService
from bot.services.stream.ad_announcements import AdAnnouncementService


@pytest.mark.asyncio
async def test_provider_only_classifies_explicit_missing_summoner():
    client = OpggMcpClient()
    client._post = AsyncMock(return_value=httpx.Response(200, json={
        "error": {"code": -32600, "message": "Summoner not found"}}))
    with pytest.raises(SummonerNotFoundError):
        await client.call_tool("example", {})
    client._post.return_value = httpx.Response(200, json={"error": {"code": -32600, "message": "Other failure"}})
    with pytest.raises(LeagueProviderError) as caught:
        await client.call_tool("example", {})
    assert not isinstance(caught.value, SummonerNotFoundError)


@pytest.mark.asyncio
async def test_missing_summoner_preserves_data_and_skips_duplicate_lookup(caplog):
    settings = SimpleNamespace(invalidate_league_identity=AsyncMock(return_value=True))
    service = LeagueService(SimpleNamespace(services=SimpleNamespace(profile_settings=settings)), None)
    client = SimpleNamespace(fetch_season_summary=AsyncMock(side_effect=SummonerNotFoundError()),
                             fetch_recent_matches=AsyncMock())
    service.save_season_summary = AsyncMock()
    await service.refresh_profile(client, "1", LeagueConfig(game_name="Name", tag_line="TAG"), force_season=True)
    client.fetch_recent_matches.assert_not_awaited()
    service.save_season_summary.assert_not_awaited()
    settings.invalidate_league_identity.assert_awaited_once()
    assert "Re-enter and verify" in caplog.text


@pytest.mark.asyncio
async def test_seventv_transport_backoff_caps_and_cancellation_cleans_registry(monkeypatch, caplog):
    service = LiveChatService(None)
    service.started = True
    service._refresh_seventv_channel = AsyncMock(side_effect=httpx.ConnectTimeout("offline"))
    delays = []

    async def sleep(delay):
        delays.append(delay)
        if len(delays) == 8:
            raise asyncio.CancelledError

    monkeypatch.setattr("bot.services.channels.live_chat.asyncio.sleep", sleep)
    service.seventv_tasks["1"] = asyncio.current_task()
    with pytest.raises(asyncio.CancelledError):
        await service._watch_seventv_channel("1")
    assert delays == [10, 20, 40, 80, 160, 300, 300, 300]
    assert "1" not in service.seventv_tasks
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_announcement_permission_cooldown_retries_and_preserves_fallback(monkeypatch):
    class Forbidden(Exception):
        status = 403

    now = [100.0]
    monkeypatch.setattr("bot.services.stream.ad_announcements.time.monotonic", lambda: now[0])
    schedule = SimpleNamespace(next_ad_at=datetime.now(UTC) + timedelta(seconds=100))
    broadcaster = SimpleNamespace(fetch_ad_schedule=AsyncMock(return_value=schedule))
    identity = SimpleNamespace(send_announcement=AsyncMock(side_effect=Forbidden()), send_message=AsyncMock())
    bot = SimpleNamespace(services=SimpleNamespace(chat_identity=identity,
                          features=SimpleNamespace(is_enabled=lambda *args: True)),
                          create_partialuser=lambda _: broadcaster)
    service = AdAnnouncementService(bot, SimpleNamespace(get_live_broadcasters=AsyncMock(return_value={"1": "channel"})))
    await service.check_ad_schedules()
    schedule.next_ad_at += timedelta(seconds=1)
    await service.check_ad_schedules()
    assert identity.send_announcement.await_count == 1
    assert identity.send_message.await_count == 2
    now[0] += 3601
    schedule.next_ad_at += timedelta(seconds=1)
    identity.send_announcement.side_effect = None
    await service.check_ad_schedules()
    assert identity.send_announcement.await_count == 2
    assert "1" not in service._announcement_retry_at
