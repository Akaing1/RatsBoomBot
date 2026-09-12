import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from starlette.requests import Request

from bot.services.stream.stream_logs import StreamLogService
from web.admin.routers import channels
from web.shared.common import templates


def test_global_retention_preserves_active_and_newest_across_channels(tmp_path):
    service = StreamLogService(None, None, str(tmp_path))
    paths = []
    for index in range(15):
        folder = tmp_path / f"channel-{index % 3}" / f"session-{index}"
        folder.mkdir(parents=True)
        log = folder / "log.txt"
        log.write_text("test")
        os.utime(log, (index + 1, index + 1))
        paths.append(log)
    service.active_sessions["active"] = SimpleNamespace(log_path=paths[0])
    assert service.prune_all_channels() == 5
    assert paths[0].exists()
    assert sum(path.exists() for path in paths) == 10
    assert all(path.exists() for path in paths[6:])
    assert service.prune_all_channels() == 0


def test_more_than_ten_active_logs_are_protected(tmp_path):
    service = StreamLogService(None, None, str(tmp_path))
    for index in range(11):
        folder = tmp_path / str(index) / "session"
        folder.mkdir(parents=True)
        log = folder / "log.txt"
        log.write_text("test")
        service.active_sessions[str(index)] = SimpleNamespace(log_path=log)
    assert service.prune_all_channels() == 0
    service.active_sessions.pop("0")
    assert service.prune_all_channels() == 1


def test_retention_waits_for_startup_discovery(tmp_path):
    service = StreamLogService(None, None, str(tmp_path))
    service._discovering_live_sessions = True
    assert service.prune_all_channels() == 0


def make_request():
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [], "session": {"csrf_token": "csrf"}})
    request.state.administrator = SimpleNamespace(id=7)
    return request


@pytest.mark.asyncio
async def test_admin_customization_requires_auth(monkeypatch):
    monkeypatch.setattr(channels, "require_admin", AsyncMock(return_value=RedirectResponse("/admin/login")))
    response = await channels.save_admin_channel_customization(make_request(), "123", "lurk_message", "hello", "save", "csrf")
    assert response.headers["location"] == "/admin/login"


@pytest.mark.asyncio
async def test_admin_customization_save_reset_and_csrf(monkeypatch):
    monkeypatch.setattr(channels, "require_admin", AsyncMock(return_value=None))
    profiles = SimpleNamespace(
        get_definition=lambda name: SimpleNamespace(label="Lurk message"),
        set_override=AsyncMock(), clear_override=AsyncMock()
    )
    services = SimpleNamespace(profile_settings=profiles, broadcasters=SimpleNamespace(get_broadcasters=lambda: {"123": object()}))
    monkeypatch.setattr(channels, "get_bot", lambda: SimpleNamespace(services=services))
    request = make_request()
    with pytest.raises(HTTPException):
        await channels.save_admin_channel_customization(request, "123", "lurk_message", "hello", "save", "wrong")
    profiles.set_override.assert_not_awaited()
    await channels.save_admin_channel_customization(request, "123", "lurk_message", "hello", "save", "csrf")
    profiles.set_override.assert_awaited_once_with("123", "lurk_message", "hello", "admin:7")
    await channels.save_admin_channel_customization(request, "123", "lurk_message", "", "reset", "csrf")
    profiles.clear_override.assert_awaited_once_with("123", "lurk_message", "admin:7")


def test_shared_editor_uses_admin_action_and_timer_script():
    html = templates.env.get_template("admin/channel_customization.html").render(
        broadcaster=SimpleNamespace(id="123", name="Test"), administrator=None,
        url_for=lambda *args, **kwargs: "/static/css/style.css",
        customization_action="/admin/channels/123/customization", csrf_token="csrf",
        setting_groups={}, channel_settings=SimpleNamespace(discord_url="", youtube_url="")
    )
    assert 'action="/admin/channels/123/customization"' in html
    assert 'action="/channel/customization"' not in html
    assert 'id="timer-message-template"' in html
