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
