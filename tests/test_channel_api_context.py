import json
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from starlette.requests import Request

from web.channel.auth import CHANNEL_USER_ID_KEY, CHANNEL_USER_LOGIN_KEY, YOUTUBE_OAUTH_STATE_KEY
from web.channel.routers import dashboard
from web.channel.api_context import resolve_channel_api_context

ENDPOINTS = [dashboard.channel_raid_contributors, dashboard.channel_dashboard_stats,
             dashboard.channel_redemption_activity, dashboard.channel_viewer_queue_state,
             dashboard.channel_chat_emotes, dashboard.channel_chat_users, dashboard.channel_ad_status]


def request(session):
    return Request({'type':'http', 'session':session})


@pytest.mark.asyncio
@pytest.mark.parametrize('endpoint', ENDPOINTS)
@pytest.mark.parametrize('case,status,detail', [
    ('anonymous', 401, 'Channel authentication required.'),
    ('offline', 503, 'Bot runtime unavailable.'),
    ('no_services', 503, 'Bot runtime unavailable.'),
    ('disconnected', 404, 'Connected channel not found.'),
])
async def test_read_endpoints_preserve_guard_responses(endpoint, case, status, detail, monkeypatch):
    session = {} if case == 'anonymous' else {CHANNEL_USER_ID_KEY:'1', CHANNEL_USER_LOGIN_KEY:'streamer', YOUTUBE_OAUTH_STATE_KEY:'pending'}
    runtime = None if case in {'anonymous','offline'} else NS(services=None) if case == 'no_services' else NS(services=NS(broadcasters=NS(get_broadcasters=lambda: {})))
    provider = Mock(return_value=runtime)
    monkeypatch.setattr(dashboard, 'get_bot', provider)
    response = await endpoint(request(session))
    assert response.status_code == status
    assert json.loads(response.body) == {'detail':detail}
    if case == 'anonymous':provider.assert_not_called()
    if case == 'disconnected':
        assert CHANNEL_USER_ID_KEY not in session
        assert YOUTUBE_OAUTH_STATE_KEY not in session
    elif case != 'anonymous':assert session[CHANNEL_USER_ID_KEY] == '1'


def test_context_returns_existing_runtime_and_broadcaster():
    broadcaster = NS(id='1')
    runtime = NS(services=NS(broadcasters=NS(get_broadcasters=lambda: {'1':broadcaster})))
    context = resolve_channel_api_context(request({CHANNEL_USER_ID_KEY:'1'}), lambda: runtime)
    assert context.broadcaster is broadcaster
    assert context.runtime_bot is runtime
    assert context.services is runtime.services
