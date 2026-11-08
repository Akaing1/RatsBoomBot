from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asqlite
import httpx
import pytest

from bot.services.channels.live_chat import LiveChatService, YouTubeConnection
from web.channel.routers import youtube
from web.shared.youtube_oauth import YouTubeChannel, YouTubeTokenResponse
from storage.migration_runner import run_migrations


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr('bot.services.channels.live_chat.settings.YOUTUBE_CLIENT_ID', 'client')
    monkeypatch.setattr('bot.services.channels.live_chat.settings.YOUTUBE_CLIENT_SECRET', 'secret')
    monkeypatch.setattr('bot.services.channels.live_chat.settings.YOUTUBE_REDIRECT_URI', 'https://example.com/callback')
    live_chat = LiveChatService(None)
    live_chat.connections['owner'] = YouTubeConnection(
        'owner', 'youtube-id', 'YouTube Channel', 'access', 'refresh',
        (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    )
    return live_chat


def http_error(status, reason):
    response = httpx.Response(status, json={'error': {'errors': [{'reason': reason}]}},
                              request=httpx.Request('GET', 'https://www.googleapis.com/youtube/v3/channels'))
    return httpx.HTTPStatusError('Google error', request=response.request, response=response)


@pytest.mark.asyncio
async def test_offline_authorization_is_checked_and_unlinked_accounts_are_ignored(service, monkeypatch):
    check = AsyncMock(return_value=YouTubeChannel('youtube-id', 'YouTube Channel'))
    monkeypatch.setattr('bot.services.channels.live_chat.fetch_youtube_channel', check)
    assert await service.check_youtube_authorization('unlinked') is False
    check.assert_not_awaited()
    assert await service.check_youtube_authorization('owner') is False
    check.assert_awaited_once_with('access')
    assert not service.get_youtube_state('owner').reauth_required


@pytest.mark.asyncio
async def test_unconfigured_deployment_never_requests_reauth(service, monkeypatch):
    monkeypatch.setattr('bot.services.channels.live_chat.settings.YOUTUBE_CLIENT_ID', '')
    check = AsyncMock()
    monkeypatch.setattr('bot.services.channels.live_chat.fetch_youtube_channel', check)
    assert await service.check_youtube_authorization('owner') is False
    check.assert_not_awaited()


@pytest.mark.asyncio
async def test_revoked_refresh_grant_requires_reauth(service):
    service.connections['owner'].expires_at = datetime.now(UTC).isoformat()
    response = httpx.Response(400, json={'error': 'invalid_grant'},
                              request=httpx.Request('POST', 'https://oauth2.googleapis.com/token'))
    service.client = SimpleNamespace(post=AsyncMock(return_value=response))
    assert await service.check_youtube_authorization('owner') is True
    assert service.get_youtube_state('owner').reauth_required
    assert await service.check_youtube_authorization('owner') is True
    service.client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_expired_access_token_is_refreshed_before_requiring_reauth(service, monkeypatch):
    check = AsyncMock(side_effect=[http_error(401, 'authError'), YouTubeChannel('youtube-id', 'Channel')])
    monkeypatch.setattr('bot.services.channels.live_chat.fetch_youtube_channel', check)
    refresh = AsyncMock(return_value=service.connections['owner'])
    service._refresh_access_token_if_needed = refresh
    assert await service.check_youtube_authorization('owner') is False
    assert refresh.await_count == 2
    assert check.await_count == 2
    assert not service.get_youtube_state('owner').reauth_required


@pytest.mark.asyncio
@pytest.mark.parametrize('error', [http_error(401, 'authError'), http_error(403, 'insufficientPermissions')])
async def test_invalid_authorization_and_missing_permissions_are_flagged(service, monkeypatch, error):
    monkeypatch.setattr('bot.services.channels.live_chat.fetch_youtube_channel', AsyncMock(side_effect=error))
    service._refresh_access_token_if_needed = AsyncMock(return_value=service.connections['owner'])
    assert await service.check_youtube_authorization('owner') is True
    assert service.get_youtube_state('owner').reauth_required


@pytest.mark.asyncio
@pytest.mark.parametrize('error', [http_error(403, 'quotaExceeded'), http_error(500, 'backendError'), httpx.ReadTimeout('temporary')])
async def test_temporary_failures_do_not_require_reauth(service, monkeypatch, error):
    monkeypatch.setattr('bot.services.channels.live_chat.fetch_youtube_channel', AsyncMock(side_effect=error))
    with pytest.raises(httpx.HTTPError):
        await service.check_youtube_authorization('owner')
    assert not service.get_youtube_state('owner').reauth_required


@pytest.mark.asyncio
async def test_successful_reconnect_and_disconnect_clear_banner(service, tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'youtube.db')) as db:
        await run_migrations(db)
        service.db = db
        service.require_youtube_reauthorization('owner', 'Reconnect YouTube.')
        result = await service.connect_youtube('owner', YouTubeChannel('youtube-id', 'Channel'),
            YouTubeTokenResponse('new-access', 'new-refresh', (datetime.now(UTC) + timedelta(hours=1)).isoformat()))
        assert not result.reauth_required
        service.require_youtube_reauthorization('owner', 'Reconnect YouTube.')
        await service.disconnect_youtube('owner')
        assert not service.get_youtube_state('owner').reauth_required


@pytest.mark.asyncio
async def test_status_endpoint_is_owner_scoped_and_does_not_expose_tokens(monkeypatch):
    check = AsyncMock(return_value=True)
    monkeypatch.setattr(youtube, 'get_bot', lambda: SimpleNamespace(services=SimpleNamespace(
        live_chat=SimpleNamespace(check_youtube_authorization=check))))
    req = SimpleNamespace(session={'channel_user_id': 'owner'}, state=SimpleNamespace(channel_access={'broadcaster_id': 'other'}))
    response = await youtube.youtube_authorization_status(req)
    check.assert_awaited_once_with('owner')
    assert response.body == b'{"required":true}'
    assert response.headers['cache-control'] == 'no-store'
    assert (await youtube.youtube_authorization_status(SimpleNamespace(session={}))).status_code == 401
    check.side_effect = httpx.ReadTimeout('temporary')
    assert (await youtube.youtube_authorization_status(req)).status_code == 503
    monkeypatch.setattr(youtube, 'get_bot', lambda: None)
    assert (await youtube.youtube_authorization_status(req)).status_code == 503


def test_youtube_banner_is_above_content_and_owner_only():
    from pathlib import Path
    source = Path('web/templates/channel/layout.html').read_text()
    owner_section = source.split('<main class="main-content streamer-main-content">', 1)[1]
    moderator, streamer = owner_section.split('{% else %}', 1)
    assert 'data-auth-platform="YouTube"' not in moderator
    assert 'data-auth-platform="YouTube"' in streamer.split('{% endif %}', 1)[0]
    assert owner_section.index('data-auth-platform="YouTube"') < owner_section.index('{% block content %}')
    assert 'href="/channel/youtube/connect"' in owner_section
