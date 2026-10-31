from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from bot.profiles import FeatureName
from web.admin.routers import channels
from web.shared.common import templates


@pytest.mark.asyncio
async def test_channel_summary_does_not_load_stream_operation_services(monkeypatch):
    broadcaster = SimpleNamespace(id='123', name='Test', login='test', is_live=False, profile_image_url=None)
    flags = list(FeatureName)[:2]
    services = SimpleNamespace(
        features=SimpleNamespace(get_channel_features=Mock(return_value={flags[0]: SimpleNamespace(effective_enabled=True), flags[1]: SimpleNamespace(effective_enabled=False)})),
        chat_identity=SimpleNamespace(get_state=Mock(return_value={'connected': False})),
    )
    monkeypatch.setattr(channels, 'require_admin', AsyncMock(return_value=None))
    monkeypatch.setattr(channels, 'get_bot', lambda: SimpleNamespace(services=services))
    monkeypatch.setattr(channels, 'get_broadcaster', lambda *_: broadcaster)
    metadata = AsyncMock(return_value={'title': 'Test stream', 'game': 'Test game'})
    monkeypatch.setattr(channels, 'get_twitch_channel_metadata', metadata)
    monkeypatch.setattr(channels, 'build_admin_context', lambda request, **values: values)
    monkeypatch.setattr(channels.templates, 'TemplateResponse', lambda **values: values)
    result = await channels.channel_details_page(object(), '123')
    assert result['name'] == 'admin/channel_overview.html'
    assert result['context']['broadcaster'] is broadcaster
    assert 'queue_users' not in result['context']
    assert result['context']['channel_features'] == [flags[0]]
    metadata.assert_awaited_once()


def test_channel_summary_has_configuration_links_without_operational_widgets():
    html = templates.env.get_template('admin/channel_overview.html').render(
        active_page='channels', channel_section='overview', administrator=None, csrf_token='test',
        url_for=lambda name, path: '/' + name + path,
        broadcaster=SimpleNamespace(id='123', name='<Test>', login='test', is_live=True, profile_image_url=None),
        channel_features=set(), chat_identity={'connected': False},
        twitch_channel_metadata={'title': 'A stream', 'game': 'A game'},
    )
    assert '&lt;Test&gt;' in html
    assert '/admin/channels/123/features' in html
    assert '/admin/channels/123/customization' in html
    assert 'No channel feature flags are enabled' in html
    for removed in ['viewer-queue-content', 'data-live-chat-feed', 'raid-monitor-details', '/api/activity', 'admin-channel-overview']:
        assert removed not in html
    templates.env.get_template('admin/channel_details.html')


def test_features_template_retains_management_forms():
    html = templates.env.get_template('admin/channel_details.html').render(
        active_page='channels', channel_section='features', administrator=None, csrf_token='test',
        url_for=lambda name, path: '/' + name + path,
        broadcaster=SimpleNamespace(id='123', name='Test', login='test', profile_image_url=None),
        channel_features={}, profile_features={}, global_groups={}, global_commands={},
        chat_identity={'connected': False, 'premium_enabled': False},
    )
    assert 'Feature toggles' in html
    assert '/admin/channels/123/delete' in html
    assert 'data-preserve-scroll' not in html or 'window.sessionStorage' in html
