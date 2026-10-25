import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from web.channel.routers import workspace, dashboard


@pytest.mark.asyncio
async def test_clips_scoped_to_session_and_paginated(monkeypatch):
    monkeypatch.setattr(workspace, "get_db", lambda: object())
    monkeypatch.setattr(workspace, "get_bot", lambda: object())
    fetch = AsyncMock(return_value={"data": [{"id": "clip", "title": "<script>"}], "pagination": {"cursor": "next"}})
    monkeypatch.setattr(dashboard, "raid_browser_cached_request", fetch)
    request = SimpleNamespace(session={workspace.CHANNEL_USER_ID_KEY: "123"})
    response = await workspace.channel_clips(request, days=7, after="previous")
    assert json.loads(response.body)["cursor"] == "next"
    assert fetch.call_args.args[1] == "123"
    assert fetch.call_args.args[3]["broadcaster_id"] == "123"
    assert fetch.call_args.args[3]["after"] == "previous"


@pytest.mark.asyncio
async def test_clips_requires_channel_session():
    with pytest.raises(HTTPException) as error:
        await workspace.channel_clips(SimpleNamespace(session={}))
    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_clips_rejects_invalid_filter(monkeypatch):
    monkeypatch.setattr(workspace, "get_db", lambda: object())
    with pytest.raises(HTTPException) as error:
        await workspace.channel_clips(SimpleNamespace(session={workspace.CHANNEL_USER_ID_KEY: "123"}), days=-1)
    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_clip_date_survives_twitchio_url_encoding(monkeypatch):
    from datetime import datetime
    from urllib.parse import parse_qs, urlsplit
    from twitchio.http import Route
    monkeypatch.setattr(workspace, "get_db", lambda: object())
    monkeypatch.setattr(workspace, "get_bot", lambda: object())
    async def fetch(bot, channel, path, params):
        value = parse_qs(urlsplit(Route("GET", path, params=params).url).query)["started_at"][0]
        assert value.endswith("Z")
        assert " " not in value
        assert datetime.fromisoformat(value).utcoffset().total_seconds() == 0
        return {"data": []}
    monkeypatch.setattr(dashboard, "raid_browser_cached_request", fetch)
    response = await workspace.channel_clips(SimpleNamespace(session={workspace.CHANNEL_USER_ID_KEY: "123"}), days=7)
    assert json.loads(response.body)["clips"] == []


@pytest.mark.asyncio
async def test_clip_upstream_error_logs_reason_without_route(monkeypatch, caplog):
    from twitchio.exceptions import HTTPException as TwitchHTTPException
    monkeypatch.setattr(workspace, "get_db", lambda: object())
    monkeypatch.setattr(workspace, "get_bot", lambda: object())
    fetch = AsyncMock(side_effect=TwitchHTTPException(
        "do not log request credentials", status=400, extra={"message": "Invalid started_at"}))
    monkeypatch.setattr(dashboard, "raid_browser_cached_request", fetch)
    with pytest.raises(HTTPException) as error:
        await workspace.channel_clips(SimpleNamespace(session={workspace.CHANNEL_USER_ID_KEY: "123"}))
    assert error.value.status_code == 502
    assert "upstream_status=400" in caplog.text
    assert "Invalid started_at" in caplog.text
    assert "do not log request credentials" not in caplog.text


@pytest.mark.asyncio
async def test_all_time_clips_omit_date_restrictions(monkeypatch):
    monkeypatch.setattr(workspace, "get_db", lambda: object())
    monkeypatch.setattr(workspace, "get_bot", lambda: object())
    fetch = AsyncMock(return_value={"data": [], "pagination": {"cursor": "next"}})
    monkeypatch.setattr(dashboard, "raid_browser_cached_request", fetch)
    await workspace.channel_clips(SimpleNamespace(session={workspace.CHANNEL_USER_ID_KEY: "123"}), after="page2")
    assert fetch.call_args.args[3] == {"broadcaster_id": "123", "first": 50, "after": "page2"}
