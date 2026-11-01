from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from starlette.requests import Request
from web.channel import authorization
from web.channel.routers import oauth


def request(session=None):
    return Request({'type': 'http', 'method': 'GET', 'path': '/channel/api/authorization',
                    'headers': [], 'session': session or {}})


def mock_validation(monkeypatch, payload, status=200):
    response = httpx.Response(status, json=payload, request=httpx.Request('GET', 'https://id.twitch.tv/oauth2/validate'))
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.get.return_value = response
    monkeypatch.setattr(authorization.httpx, 'AsyncClient', lambda **kwargs: client)
    return client


@pytest.mark.asyncio
async def test_scopes_follow_current_oauth_requirements_and_fresh_grant(monkeypatch):
    monkeypatch.setattr(authorization.settings, 'CHANNEL_SCOPES', 'user:read:chat channel:manage:clips')
    monkeypatch.setattr(authorization.settings, 'CLIENT_ID', 'app')
    bot = SimpleNamespace(tokens={'123': {'token': 'secret'}})
    client = mock_validation(monkeypatch, {'user_id': '123', 'client_id': 'app', 'scopes': ['user:read:chat']})
    assert await authorization.missing_channel_scopes(bot, '123') == ['channel:manage:clips']
    client.get.assert_awaited_once_with('https://id.twitch.tv/oauth2/validate', headers={'Authorization': 'OAuth secret'})
    mock_validation(monkeypatch, {'user_id': '123', 'client_id': 'app', 'scopes': ['user:read:chat', 'channel:manage:clips']})
    assert await authorization.missing_channel_scopes(bot, '123') == []
    monkeypatch.setattr(authorization.settings, 'CHANNEL_SCOPES', 'user:read:chat channel:manage:clips channel:manage:polls')
    assert await authorization.missing_channel_scopes(bot, '123') == ['channel:manage:polls']


@pytest.mark.asyncio
@pytest.mark.parametrize('status,payload', [(401, {}), (200, {'user_id': 'other', 'client_id': 'app', 'scopes': ['test']}), (200, {'user_id': '123', 'client_id': 'other', 'scopes': ['test']})])
async def test_invalid_grants_need_reauthorization(monkeypatch, status, payload):
    monkeypatch.setattr(authorization.settings, 'CHANNEL_SCOPES', 'test')
    monkeypatch.setattr(authorization.settings, 'CLIENT_ID', 'app')
    mock_validation(monkeypatch, payload, status)
    assert await authorization.missing_channel_scopes(SimpleNamespace(tokens={'123': {'token': 'x'}}), '123') == ['test']


@pytest.mark.asyncio
async def test_status_uses_session_identity_and_does_not_expose_credentials(monkeypatch):
    check = AsyncMock(return_value=['channel:manage:clips'])
    monkeypatch.setattr(authorization, 'missing_channel_scopes', check)
    bot = object()
    monkeypatch.setattr(oauth, 'get_bot', lambda: bot)
    req = request({'channel_user_id': '123'})
    req.state.channel_access = {'broadcaster_id': 'different'}
    result = await oauth.channel_authorization_status(req)
    check.assert_awaited_once_with(bot, '123')
    assert result.body == b'{"required":true}'
    assert result.headers['cache-control'] == 'no-store'
    assert (await oauth.channel_authorization_status(request())).status_code == 401
    check.side_effect = httpx.ReadTimeout('temporary')
    assert (await oauth.channel_authorization_status(req)).status_code == 503


@pytest.mark.asyncio
async def test_missing_token_requires_reconnect(monkeypatch):
    monkeypatch.setattr(authorization.settings, 'CHANNEL_SCOPES', 'test')
    assert await authorization.missing_channel_scopes(SimpleNamespace(tokens={}), '123') == ['test']


def test_banner_is_above_content_and_streamer_only():
    from pathlib import Path
    source = Path('web/templates/channel/layout.html').read_text()
    assert source.index('data-channel-auth-banner') < source.index('{% block content %}')
    assert '{% else %}<script src="/static/js/channel-authorization.js' in source
