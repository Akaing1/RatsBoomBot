import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from twitchio.exceptions import HTTPException as TwitchHTTPException
from web.channel.routers import workspace, dashboard


@pytest.fixture
def download(monkeypatch):
    request = SimpleNamespace(session={workspace.CHANNEL_USER_ID_KEY: "123"})
    bot = SimpleNamespace(_http=SimpleNamespace(request_json=AsyncMock(return_value={
        "data": [{"clip_id": "clip", "landscape_download_url": "https://clips-media-assets.twitch.tv/file.mp4"}]
    })))
    monkeypatch.setattr(workspace, "get_db", lambda: object())
    monkeypatch.setattr(workspace, "get_bot", lambda: bot)
    monkeypatch.setattr(workspace, "validate_csrf_token", lambda req, token: None)
    metadata = AsyncMock(return_value={"data": [{"id": "clip", "broadcaster_id": "123"}]})
    monkeypatch.setattr(dashboard, "raid_browser_cached_request", metadata)
    return request, bot, metadata


@pytest.mark.asyncio
async def test_download_uses_broadcaster_token_and_no_cache(download):
    request, bot, _ = download
    response = await workspace.clip_download(request, "clip", "csrf")
    assert json.loads(response.body)["url"].startswith("https:")
    assert response.headers["cache-control"] == "no-store"
    route = bot._http.request_json.call_args.args[0]
    assert route.token_for == "123"
    assert route.params == {"broadcaster_id": "123", "editor_id": "123", "clip_id": "clip"}


@pytest.mark.asyncio
async def test_download_rejects_other_channels(download):
    request, bot, metadata = download
    metadata.return_value = {"data": [{"id": "clip", "broadcaster_id": "456"}]}
    with pytest.raises(HTTPException) as error:
        await workspace.clip_download(request, "clip", "csrf")
    assert error.value.status_code == 404
    bot._http.request_json.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("status,expected", [(401,403),(403,403),(429,429),(500,502)])
async def test_download_reports_upstream_failure(download, status, expected):
    request, bot, _ = download
    bot._http.request_json.side_effect = TwitchHTTPException(status=status, extra={})
    with pytest.raises(HTTPException) as error:
        await workspace.clip_download(request, "clip", "csrf")
    assert error.value.status_code == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("rows", [[], [{"clip_id": "clip", "landscape_download_url": "javascript:bad"}]])
async def test_download_unavailable(download, rows):
    request, bot, _ = download
    bot._http.request_json.return_value = {"data": rows}
    with pytest.raises(HTTPException) as error:
        await workspace.clip_download(request, "clip", "csrf")
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_download_requires_session():
    with pytest.raises(HTTPException) as error:
        await workspace.clip_download(SimpleNamespace(session={}), "clip", "csrf")
    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_download_requires_csrf(download, monkeypatch):
    def reject(*args):
        raise HTTPException(403, "Invalid CSRF")
    monkeypatch.setattr(workspace, "validate_csrf_token", reject)
    request, bot, metadata = download
    with pytest.raises(HTTPException):
        await workspace.clip_download(request, "clip", "bad")
    metadata.assert_not_awaited()
    bot._http.request_json.assert_not_awaited()
