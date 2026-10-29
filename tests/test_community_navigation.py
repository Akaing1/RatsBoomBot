from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from starlette.requests import Request
from web.viewer import routers, auth


def request(session):
    return Request({'type': 'http', 'session': session})


@pytest.mark.asyncio
async def test_community_profile_signin_keeps_destination():
    response = await routers.viewer_community_profile(request({}), 'testchannel')
    assert response.headers['location'] == '/me/connect?next=/me/channels/testchannel/profile'
    session = {}
    auth.start_viewer_oauth(request(session), '/me/channels/testchannel/profile')
    assert session[auth.VIEWER_OAUTH_NEXT_KEY] == '/me/channels/testchannel/profile'
    auth.start_viewer_oauth(request(session), '//evil.example/profile')
    assert session[auth.VIEWER_OAUTH_NEXT_KEY] == '/me'


@pytest.mark.asyncio
async def test_community_profile_uses_signed_in_identity(monkeypatch):
    stats = SimpleNamespace(get_channel_profile=AsyncMock(return_value={
        'identity': {'user_id': '42', 'login': 'alice'},
        'channel': {'id': '1', 'login': 'testchannel'}}))
    monkeypatch.setattr(routers, 'get_bot', lambda: SimpleNamespace(services=SimpleNamespace(chatter_stats=stats)))
    monkeypatch.setattr(routers, 'get_db', lambda: object())
    monkeypatch.setattr(routers, 'valid_viewer_session', AsyncMock(return_value=True))
    response = await routers.viewer_community_profile(request({auth.VIEWER_USER_ID_KEY:'42'}), 'testchannel')
    assert response.headers['location'] == '/chatters/alice/channels/testchannel'
    assert response.headers['cache-control'] == 'no-store'
    stats.get_channel_profile.assert_awaited_once_with('42', 'testchannel')


@pytest.mark.asyncio
async def test_community_profile_rechecks_expired_session(monkeypatch):
    monkeypatch.setattr(routers, 'get_db', lambda: object())
    monkeypatch.setattr(routers, 'valid_viewer_session', AsyncMock(return_value=False))
    response = await routers.viewer_community_profile(request({auth.VIEWER_USER_ID_KEY:'42'}), 'testchannel')
    assert response.headers['location'] == '/me/connect?next=/me/channels/testchannel/profile'
