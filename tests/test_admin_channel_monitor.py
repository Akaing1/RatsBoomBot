import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.responses import RedirectResponse
from starlette.requests import Request
from bot.profiles import FeatureName
from web.admin.routers import channels
from web.shared.common import templates


def request(query=b''):
    return Request({'type': 'http', 'method': 'GET', 'path': '/admin/channels/123/settings',
        'headers': [], 'query_string': query, 'session': {'channel_user_id': 'other'}})


@pytest.mark.asyncio
@pytest.mark.parametrize('endpoint', [channels.channel_features_page, channels.channel_monitor_page,
    channels.channel_monitor_state, channels.admin_channel_chat_stream, channels.admin_channel_customization])
async def test_admin_views_require_admin_before_loading_channel(monkeypatch, endpoint):
    monkeypatch.setattr(channels, 'require_admin', AsyncMock(return_value=RedirectResponse('/admin/login')))
    runtime = Mock(side_effect=AssertionError('Must authenticate first'))
    monkeypatch.setattr(channels, 'get_bot', runtime)
    response = await endpoint(request(), '123')
    assert response.status_code in (307, 401)
    runtime.assert_not_called()


@pytest.mark.asyncio
async def test_legacy_links_keep_feedback_and_target_admin_settings(monkeypatch):
    monkeypatch.setattr(channels, 'require_admin', AsyncMock(return_value=None))
    for endpoint in (channels.admin_channel_customization, channels.channel_features_redirect):
        response = await endpoint(request(b'command_tab=protected&setting_result=success'), '123')
        assert response.headers['location'] == '/admin/channels/123/settings?command_tab=protected&setting_result=success'


@pytest.mark.asyncio
async def test_unified_settings_keep_master_controls_and_admin_endpoints(monkeypatch):
    state = SimpleNamespace(effective_enabled=True, default_enabled=True, override_enabled=False,
        blocked_by_profile=False, blocked_by_globals=False)
    flags = {FeatureName.TIMERS: state, FeatureName.REDEEMS: state}
    services = SimpleNamespace(features=SimpleNamespace(
        get_channel_features=Mock(return_value=flags), get_profile_features=Mock(return_value={}),
        get_admin_profile_features=Mock(return_value={}), get_global_groups=Mock(return_value={}), get_global_commands=Mock(return_value={})),
        profile_settings=SimpleNamespace(get_setting_groups=Mock(return_value={})),
        broadcaster_settings=SimpleNamespace(get_settings=AsyncMock(return_value=SimpleNamespace())),
        chat_identity=SimpleNamespace(get_state=Mock(return_value={})))
    monkeypatch.setattr(channels, 'require_admin', AsyncMock(return_value=None))
    monkeypatch.setattr(channels, 'get_bot', lambda: SimpleNamespace(services=services))
    monkeypatch.setattr(channels, 'get_broadcaster', lambda *_: SimpleNamespace(id='123', name='<Channel>'))
    monkeypatch.setattr(channels, 'get_active_profile', lambda _: None)
    monkeypatch.setattr(channels, 'get_protected_user_rows', AsyncMock(return_value=[]))
    monkeypatch.setattr(channels, 'build_admin_context', lambda request, **values: dict(values,
        request=request, administrator=None, csrf_token='token', url_for=lambda name, path: '/static' + path))
    monkeypatch.setattr(channels.templates, 'TemplateResponse', lambda **values: values)
    req = request()
    session = dict(req.session)
    result = await channels.channel_features_page(req, '123')
    html = templates.env.get_template(result['name']).render(**result['context'])
    assert req.session == session
    assert '&lt;Channel&gt;' in html
    assert 'data-channel-root="/admin/channels/123"' in html
    assert 'id="settings-toggle-feature-timers"' in html
    assert 'id="settings-toggle-feature-redeems"' in html
    assert 'Use default: Timers master switch' in html
    assert 'action="/admin/channels/123/toggles"' in html
    assert 'action="/admin/channels/123/customization"' in html
    assert 'action="/channel/' not in html
    assert '/admin/channels/123/delete' in html


@pytest.mark.asyncio
async def test_monitor_is_scoped_and_has_no_queue_dependency(monkeypatch):
    activity = {'feed': [{'user_label': '<viewer>'}], 'mod_actions': [], 'automod': []}
    services = SimpleNamespace()
    monkeypatch.setattr(channels, 'require_admin', AsyncMock(return_value=None))
    monkeypatch.setattr(channels, 'get_bot', lambda: SimpleNamespace(services=services))
    monkeypatch.setattr(channels, 'get_broadcaster', lambda _, identity: SimpleNamespace(is_live=identity == '123'))
    loader = AsyncMock(return_value=activity)
    monkeypatch.setattr(channels, 'get_redemption_dashboard_data', loader)
    response = await channels.channel_monitor_state(request(), '123')
    loader.assert_awaited_once_with(services, '123')
    assert json.loads(response.body) == {'is_live': True, 'activity': activity}
    assert response.headers['cache-control'] == 'no-store'
    monkeypatch.setattr(channels, 'get_broadcaster', lambda *_: None)
    assert (await channels.channel_monitor_state(request(), 'missing')).status_code == 404


def test_monitor_renders_read_only_shared_player_and_feeds():
    html = templates.env.get_template('admin/channel_monitor.html').render(
        active_page='channels', channel_section='monitor', administrator=None,
        url_for=lambda name, path: '/static' + path,
        broadcaster=SimpleNamespace(id='123', name='<Channel>', login='channel', is_live=False),
        twitch_channel_metadata={'title': '<script>bad</script>', 'game': 'Games'})
    assert '&lt;script&gt;bad&lt;/script&gt;' in html
    assert '/admin/channels/123/api/chat/stream?view=chat' in html
    assert '/admin/channels/123/api/chat/stream?view=commands' in html
    assert 'data-stream-player' in html
    assert 'AutoMod holds' in html
    for forbidden in ('data-moderation-url', 'data-pinned-url', '/api/chat/send', 'action="/admin/channels/', 'viewer-queue'):
        assert forbidden not in html


@pytest.mark.asyncio
async def test_open_chat_stream_rechecks_admin_session(monkeypatch):
    from fastapi import HTTPException
    auth = AsyncMock(return_value=None)
    monkeypatch.setattr(channels, 'require_admin', auth)
    monkeypatch.setattr(channels, 'get_bot', lambda: SimpleNamespace(services=SimpleNamespace(live_chat=object())))
    monkeypatch.setattr(channels, 'get_broadcaster', lambda *_: object())
    clock = [0]
    monkeypatch.setattr(channels.time, 'monotonic', lambda: clock[0])
    req = request()
    await channels.admin_channel_chat_stream(req, '123')
    await req.state.check_channel_access()
    assert auth.await_count == 1
    clock[0] = 6
    auth.return_value = RedirectResponse('/admin/login')
    with pytest.raises(HTTPException) as error:
        await req.state.check_channel_access()
    assert error.value.status_code == 401
