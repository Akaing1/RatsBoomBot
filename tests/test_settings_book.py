from collections import Counter
from types import SimpleNamespace

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from bot.profiles import ChannelProfile, activate_profile, clear_profiles
from bot.services.channels.feature_toggle import FeatureToggleService
from bot.services.channels.profile_settings import ProfileSettingsService
from web.channel.settings_book import build_settings_sections
from web.shared.common import templates


def settings_context(section='general'):
    profile = ChannelProfile(channel_name='example')
    activate_profile('settings-test', profile)
    features = FeatureToggleService(None)
    groups = ProfileSettingsService(None).get_setting_groups('settings-test')
    states = [features.get_channel_features('settings-test'), features.get_profile_features('settings-test'), features.get_global_groups('settings-test'), features.get_global_commands('settings-test')]
    sections = build_settings_sections(groups, *states)
    return dict(
        request=Request({'type': 'http', 'query_string': f'section={section}'.encode(), 'headers': [], 'path': '/channel/settings'}),
        settings_sections=sections, broadcaster=SimpleNamespace(id='settings-test'),
        active_page='settings', csrf_token='csrf-test', customization_action='/channel/customization',
        channel_settings=SimpleNamespace(discord_url='', youtube_url='', follow_raid=False),
        chat_identity=SimpleNamespace(premium_enabled=True, connected=False),
        youtube_chat=SimpleNamespace(connected=False, configured=False), widget_urls={},
        protected_users=[], social_tab='links', command_tab='responses', loyalty_alias='points',
        url_for=lambda name, path: '/static'+path if name == 'static' else '/assets'+path,
        deployment_stamp=lambda: 'test',
    ), groups, states


def test_every_setting_and_toggle_is_assigned_exactly_once():
    try:
        context, groups, states = settings_context()
        sections = context['settings_sections']
        assert Counter(key for section in sections for key in section['groups']) == Counter(groups.keys())
        assert sum(len(section['toggles']) for section in sections) == sum(map(len, states))
        chat = next(s for s in sections if s['key'] == 'chat')
        assert any(t['name'] == 'kamikaze' for t in chat['toggles'])
        loyalty = next(s for s in sections if s['key'] == 'loyalty')
        assert 'Loyalty points' in loyalty['groups']
        assert {(t['kind'], t['name']) for t in loyalty['toggles']} == {('feature', 'points'), ('global_group', 'points')}
    finally:
        clear_profiles()


def test_notebook_renders_existing_forms_once_and_honors_deep_link():
    try:
        context, groups, states = settings_context('connections')
        html = templates.env.get_template('channel/settings.html').render(**context)
        assert html.count('role="tabpanel"') == 8
        assert html.count('id="protected-users"') == 1
        assert html.count('id="youtube-integration"') == 1
        assert 'data-settings-page="connections" hidden' not in html
        assert 'data-settings-page="general" hidden' in html
        assert 'action="/channel/features/toggles"' in html
        assert 'action="/channel/customization"' in html
        assert 'action="/channel/custom-bot/connect"' in html
        assert 'name="csrf_token"' in html
        for entries in groups.values():
            for entry in entries:
                assert html.count(f'name="setting_name" value="{entry.definition.key}"') == 1
    finally:
        clear_profiles()


@pytest.mark.parametrize('path', ['/channel/settings', '/channel/features', '/channel/customization'])
def test_settings_and_legacy_routes_require_authentication(path):
    from web.app import app
    with TestClient(app) as client:
        response = client.get(path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == '/connect'


def test_header_controls_are_not_duplicated_in_standalone_rows():
    try:
        context, _, _ = settings_context()
        for section in context['settings_sections']:
            assigned = section['standalone_toggles'] + [t for group in section['group_toggles'].values() for t in group]
            assert Counter((t['kind'], t['name']) for t in assigned) == Counter((t['kind'], t['name']) for t in section['toggles'])
        timers = next(s for s in context['settings_sections'] if s['key'] == 'timers')
        assert timers['standalone_toggles'] == []
        assert timers['group_toggles']['Timers'][0]['name'] == 'timers'
        html = templates.env.get_template('channel/settings.html').render(**context)
        assert html.index('<nav class="settings-tabs"') < html.index('<div class="settings-pages"')
        assert 'form="settings-toggle-feature-timers"' in html
        assert 'id="settings-toggle-feature-timers"' in html
        assert '>Enable\n' not in html
    finally:
        clear_profiles()
