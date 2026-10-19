import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from web.shared import raid_suggestions as suggestions


def payload(channels=None):
    return {"data": {"user": {"id": "1", "channel": {"home": {"shelves": {
        "streamerShelf": {"edges": [{"node": node} for node in (channels if channels is not None else [
            {"id": "2", "login": "StreamerTwo"}])]}}}}}}}


@pytest.fixture
def cache(monkeypatch, tmp_path):
    monkeypatch.setattr(suggestions.settings, "DATABASE_PATH", str(tmp_path / "tokens.db"))
    clock = [2000000.0]
    monkeypatch.setattr(suggestions.time, "time", lambda: clock[0])
    fetch = AsyncMock(return_value=payload())
    monkeypatch.setattr(suggestions, "fetch_public_shelf", fetch)
    return SimpleNamespace(), fetch, clock, tmp_path


def test_parser_validates_owner_shape_and_duplicates():
    result = suggestions.parse_streamer_shelf(payload([
        {"id": "2", "login": "StreamerTwo"}, {"id": "2", "login": "streamertwo"},
        None, {"id": "1", "login": "owner"}]), "1")
    assert result == [{"id": "2", "login": "streamertwo"}]
    for invalid in ({"errors": [{"message": "PersistedQueryNotFound"}]}, {}, payload()):
        with pytest.raises(ValueError):
            suggestions.parse_streamer_shelf(invalid, "99")


@pytest.mark.asyncio
async def test_daily_cache_survives_runtime_restart(cache):
    bot, fetch, clock, directory = cache
    channels, status = await suggestions.get_suggested_streamers(bot, "1", "owner")
    assert status == "fresh"
    assert channels == [{"id": "2", "login": "streamertwo"}]
    clock[0] += 86399
    assert (await suggestions.get_suggested_streamers(bot, "1", "owner"))[1] == "cached"
    assert (await suggestions.get_suggested_streamers(SimpleNamespace(), "1", "owner"))[1] == "cached"
    fetch.assert_awaited_once_with("owner")
    assert json.loads((directory / "raid-suggestions" / "1.json").read_text())["channels"] == channels
    clock[0] += 2
    assert (await suggestions.get_suggested_streamers(bot, "1", "owner"))[1] == "fresh"
    assert fetch.await_count == 2


@pytest.mark.asyncio
async def test_failure_retains_previous_list_and_backs_off(cache):
    bot, fetch, clock, _ = cache
    previous, _ = await suggestions.get_suggested_streamers(bot, "1", "owner")
    clock[0] += 86401
    fetch.side_effect = httpx.ConnectError("Unavailable")
    assert await suggestions.get_suggested_streamers(bot, "1", "owner") == (previous, "stale")
    assert await suggestions.get_suggested_streamers(bot, "1", "owner") == (previous, "stale")
    assert fetch.await_count == 2
    clock[0] += 601
    await suggestions.get_suggested_streamers(bot, "1", "owner")
    assert fetch.await_count == 3


@pytest.mark.asyncio
async def test_missing_shelf_is_not_treated_as_an_empty_list(cache):
    bot, fetch, clock, _ = cache
    previous, _ = await suggestions.get_suggested_streamers(bot, "1", "owner")
    clock[0] += 86401
    fetch.return_value = {"data": {"user": {"id": "1", "channel": {}}}}
    assert await suggestions.get_suggested_streamers(bot, "1", "owner") == (previous, "stale")
    clock[0] += 601
    fetch.return_value = payload([])
    assert await suggestions.get_suggested_streamers(bot, "1", "owner") == ([], "fresh")


@pytest.mark.asyncio
async def test_parallel_requests_only_fetch_once(cache):
    bot, fetch, _, _ = cache
    results = await asyncio.gather(*(suggestions.get_suggested_streamers(bot, "1", "owner") for _ in range(5)))
    assert all(result[0] == [{"id": "2", "login": "streamertwo"}] for result in results)
    assert fetch.await_count == 1


@pytest.mark.asyncio
async def test_invalid_identity_and_cache_cannot_reuse_other_account(cache):
    bot, fetch, _, directory = cache
    assert await suggestions.get_suggested_streamers(bot, "../1", "owner") == ([], "unavailable")
    await suggestions.get_suggested_streamers(bot, "1", "owner")
    await suggestions.get_suggested_streamers(SimpleNamespace(), "1", "renamed_owner")
    assert fetch.await_count == 2
    cache_file = directory / "raid-suggestions" / "1.json"
    cache_file.write_text("invalid json")
    await suggestions.get_suggested_streamers(SimpleNamespace(), "1", "owner")
    assert fetch.await_count == 3


@pytest.mark.asyncio
async def test_network_request_has_no_authorization_or_cookies(monkeypatch):
    captured = {}
    def respond(request):
        captured["request"] = request
        return httpx.Response(200, json=payload())
    real_client = httpx.AsyncClient
    monkeypatch.setattr(suggestions.httpx, "AsyncClient", lambda **kwargs:
        real_client(transport=httpx.MockTransport(respond), **kwargs))
    await suggestions.fetch_public_shelf("owner")
    request = captured["request"]
    assert request.url == "https://gql.twitch.tv/gql"
    assert "authorization" not in request.headers
    assert "cookie" not in request.headers
    assert json.loads(request.content)["operationName"] == "HomeShelfUsers"
