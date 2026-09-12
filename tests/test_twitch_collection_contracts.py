from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import twitchio

from bot.profiles import RedeemConfig
from bot.services.engagement.raid_boss import RaidBossService
from bot.services.engagement.redeems import RedeemService


async def iterate_users():
    yield SimpleNamespace(id="viewer-1", name="alice")
    yield SimpleNamespace(id="viewer-2", name="bob")


@pytest.mark.asyncio
async def test_raid_chatter_count_uses_real_twitchio_response():
    response = twitchio.Chatters(iterate_users(), {"total": 2})
    http = SimpleNamespace(get_chatters=AsyncMock(return_value=response))
    broadcaster = twitchio.PartialUser("channel-1", http=http)
    bot = SimpleNamespace(user=SimpleNamespace(id="bot-1"), create_partialuser=lambda _: broadcaster)
    assert await RaidBossService(bot, None)._live_chatter_count("channel-1") == 2
    http.get_chatters.assert_awaited_once()


@pytest.mark.asyncio
async def test_vip_calls_use_broadcaster_token_and_unawaited_iterators():
    async def empty():
        if False:
            yield

    http = SimpleNamespace(get_moderators=Mock(side_effect=lambda **kwargs: empty()), get_vips=Mock(side_effect=lambda **kwargs: empty()), add_vip=AsyncMock())
    broadcaster = twitchio.PartialUser("channel-1", http=http)
    service = RedeemService(SimpleNamespace(create_partialuser=lambda _: broadcaster), None, None)
    result = await service.grant_vip(broadcaster_id="channel-1", user_id="viewer-1", username="alice", config=RedeemConfig())
    assert "now a VIP" in result.message
    for method in (http.get_moderators, http.get_vips, http.add_vip):
        assert method.call_args.kwargs["token_for"] == "channel-1"
    http.add_vip.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 422, 500])
async def test_vip_failure_logs_channel_and_distinguishes_authorization(status, caplog):
    error = RuntimeError("Twitch rejected VIP request")
    error.status = status
    broadcaster = SimpleNamespace(add_vip=AsyncMock(side_effect=error))
    service = RedeemService(SimpleNamespace(create_partialuser=lambda _: broadcaster), None, None)
    service.is_moderator = AsyncMock(return_value=False)
    service.is_vip = AsyncMock(return_value=False)
    config = RedeemConfig()
    result = await service.grant_vip(broadcaster_id="channel-1", user_id="viewer-1", username="alice", config=config)
    assert ("reconnect" in result.message) == (status in (401, 403))
    record = caplog.records[-1]
    assert record.broadcaster_id == "channel-1"
    assert str(status) in record.getMessage()
    assert record.exc_info is not None


def test_custom_channel_scopes_include_vip_permissions(monkeypatch):
    import runpy

    monkeypatch.setenv("CHANNEL_SCOPES", "channel:bot")
    settings = runpy.run_path("config/settings.py")["settings"]
    assert {"channel:bot", "channel:manage:vips", "channel:manage:moderators"} <= set(settings.CHANNEL_SCOPES.split())
