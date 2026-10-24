import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException
import pytest
from starlette.requests import Request

from web.admin.auth import CSRF_SESSION_KEY
from web.channel.auth import CHANNEL_USER_ID_KEY
from web.channel.routers import dashboard


def request(user="1"):
    return Request({"type": "http", "session": {CHANNEL_USER_ID_KEY: user, CSRF_SESSION_KEY: "valid"} if user else {}})


@pytest.fixture
def runtime(monkeypatch):
    broadcaster = SimpleNamespace(start_raid=AsyncMock(return_value=SimpleNamespace(created_at=datetime.now(UTC))), cancel_raid=AsyncMock())
    bot = SimpleNamespace(services=SimpleNamespace(broadcasters=SimpleNamespace(get_broadcasters=lambda: {"1": SimpleNamespace(id="1")})),
        create_partialuser=lambda id_: broadcaster,
        fetch_user=AsyncMock(return_value=SimpleNamespace(id="2", name="target", display_name="Target",
            profile_image=SimpleNamespace(url="https://static-cdn.jtvnw.net/jtv_user_pictures/target.png"))))
    monkeypatch.setattr(dashboard, "get_bot", lambda: bot)
    return bot, broadcaster


@pytest.mark.asyncio
async def test_start_is_authenticated_csrf_protected_and_uses_connected_broadcaster(runtime):
    bot, broadcaster = runtime
    assert (await dashboard.channel_raid_action(request(None), action="start", target_id="2", csrf_token="valid")).status_code == 401
    with pytest.raises(HTTPException) as error:
        await dashboard.channel_raid_action(request(), action="start", target_id="2", csrf_token="invalid")
    assert error.value.status_code == 403
    response = await dashboard.channel_raid_action(request(), action="start", target_id="2", csrf_token="valid")
    assert response.status_code == 200
    raid = json.loads(response.body)["raid"]
    assert raid["target_id"] == "2" and raid["login"] == "target"
    assert raid["profile_image_url"] == "https://static-cdn.jtvnw.net/jtv_user_pictures/target.png"
    broadcaster.start_raid.assert_awaited_once_with("2")
    assert json.loads((await dashboard.channel_pending_raid(request())).body)["raid"] == raid
    assert json.loads((await dashboard.channel_pending_raid(request("missing"))).body).get("raid") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["1", "invalid", "", "../2"])
async def test_invalid_or_self_target_cannot_start_a_raid(runtime, target):
    _, broadcaster = runtime
    response = await dashboard.channel_raid_action(request(), action="start", target_id=target, csrf_token="valid")
    assert response.status_code == 400
    broadcaster.start_raid.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_target_and_duplicate_clicks_are_safe(runtime):
    bot, broadcaster = runtime
    bot.fetch_user.return_value = None
    assert (await dashboard.channel_raid_action(request(), action="start", target_id="2", csrf_token="valid")).status_code == 404
    broadcaster.start_raid.assert_not_awaited()
    bot.fetch_user.return_value = SimpleNamespace(id="2", name="target", display_name="Target")
    responses = await asyncio.gather(*(dashboard.channel_raid_action(request(), action="start", target_id="2", csrf_token="valid") for _ in range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    broadcaster.start_raid.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_clears_pending_state_after_twitch_accepts(runtime):
    _, broadcaster = runtime
    await dashboard.channel_raid_action(request(), action="start", target_id="2", csrf_token="valid")
    response = await dashboard.channel_raid_action(request(), action="cancel", csrf_token="valid")
    assert response.status_code == 200 and json.loads(response.body)["raid"] is None
    broadcaster.cancel_raid.assert_awaited_once()
    assert json.loads((await dashboard.channel_pending_raid(request())).body)["raid"] is None


@pytest.mark.asyncio
async def test_twitch_failure_does_not_create_a_pending_banner(runtime):
    bot, broadcaster = runtime
    class PermissionFailure(Exception):
        status = 403
    broadcaster.start_raid.side_effect = PermissionFailure("not allowed")
    response = await dashboard.channel_raid_action(request(), action="start", target_id="2", csrf_token="valid")
    assert response.status_code == 403
    assert "Reconnect Twitch" in json.loads(response.body)["detail"]
    assert bot._dashboard_pending_raids == {}


@pytest.mark.asyncio
async def test_cancel_failure_retains_pending_status(runtime):
    bot, broadcaster = runtime
    await dashboard.channel_raid_action(request(), action="start", target_id="2", csrf_token="valid")
    broadcaster.cancel_raid.side_effect = RuntimeError("failed")
    response = await dashboard.channel_raid_action(request(), action="cancel", csrf_token="valid")
    assert response.status_code == 502
    assert bot._dashboard_pending_raids["1"]["target_id"] == "2"


@pytest.mark.asyncio
@pytest.mark.parametrize("stream_count", [0, 42, None])
async def test_raid_count_refreshes_stream_viewers_then_uses_confirmation(runtime, stream_count):
    from bot.shared.events.raids import RaidEvents

    bot, broadcaster = runtime
    own = SimpleNamespace(id="1", viewer_count=stream_count)
    bot.services.broadcasters.get_broadcasters = lambda: {"1": own}
    response = await dashboard.channel_raid_action(request(), action="start", target_id="2", csrf_token="valid")
    assert json.loads(response.body)["raid"]["viewer_count"] == stream_count
    own.viewer_count = 51
    response = await dashboard.channel_pending_raid(request())
    assert json.loads(response.body)["raid"]["viewer_count"] == 51
    await RaidEvents(bot).handle_raid(SimpleNamespace(
        from_broadcaster=SimpleNamespace(id="1", name="sender"),
        to_broadcaster=SimpleNamespace(id="2", name="target"), viewer_count=5))
    own.viewer_count = 999
    response = await dashboard.channel_pending_raid(request())
    raid = json.loads(response.body)["raid"]
    assert raid["completed"] is True
    assert raid["viewer_count"] == 5
    broadcaster.start_raid.assert_awaited_once()
    bot.fetch_user.assert_awaited_once()


@pytest.mark.parametrize("count, expected", [(0, 0), (1, 1), (42, 42), (None, None), (-1, None), (True, None), ("42", None)])
def test_raid_viewer_count_does_not_guess_unknown_counts(runtime, count, expected):
    bot, _ = runtime
    bot.services.broadcasters.get_broadcasters = lambda: {"1": SimpleNamespace(id="1", viewer_count=count)}
    assert dashboard.raid_viewer_count(bot, "1") == expected


@pytest.mark.asyncio
async def test_slash_raid_and_unraid_share_dashboard_state(runtime):
    bot, broadcaster = runtime
    target = bot.fetch_user.return_value
    bot.services.chatters = SimpleNamespace(resolve=AsyncMock(return_value=target))
    await dashboard.execute_twitch_slash_command(bot, "1", "/raid target")
    assert bot._dashboard_pending_raids["1"]["login"] == "target"
    response = await dashboard.channel_pending_raid(request())
    assert json.loads(response.body)["raid"]["target_id"] == "2"
    broadcaster.cancel_raid.side_effect = RuntimeError("failed")
    with pytest.raises(RuntimeError):
        await dashboard.execute_twitch_slash_command(bot, "1", "/unraid")
    assert "1" in bot._dashboard_pending_raids
    broadcaster.cancel_raid.side_effect = None
    await dashboard.execute_twitch_slash_command(bot, "1", "/unraid")
    assert not bot._dashboard_pending_raids


@pytest.mark.asyncio
async def test_slash_raid_failure_does_not_show_popup(runtime):
    bot, broadcaster = runtime
    bot.services.chatters = SimpleNamespace(resolve=AsyncMock(return_value=bot.fetch_user.return_value))
    broadcaster.start_raid.side_effect = RuntimeError("failed")
    with pytest.raises(RuntimeError):
        await dashboard.execute_twitch_slash_command(bot, "1", "/raid target")
    assert not bot._dashboard_pending_raids
