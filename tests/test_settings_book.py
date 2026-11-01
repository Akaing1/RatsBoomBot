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
        assert Counter(entry.definition.key for section in sections for entries in section['groups'].values() for entry in entries) == Counter(entry.definition.key for name, entries in groups.items() if name not in ('League of Legends', 'Overwatch') for entry in entries)
        assert sum(len(section['toggles']) for section in sections) == sum(map(len, states)) - 2
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
        assert html.count('class="settings-menu-section"') == 8
        assert 'role="tablist"' not in html
        assert 'role="tabpanel"' not in html
        assert html.count('id="protected-users"') == 1
        assert html.count('id="youtube-integration"') == 1
        assert 'data-settings-page="connections" hidden' not in html
        assert 'data-settings-page="general" hidden' in html
        assert 'action="/channel/features/toggles"' in html
        assert 'action="/channel/customization"' in html
        assert 'action="/channel/custom-bot/connect"' in html
        assert 'name="csrf_token"' in html
        for name, entries in groups.items():
            if name in ('League of Legends', 'Overwatch'):
                continue
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
            assigned = section['standalone_toggles'] + list(section['setting_toggles'].values()) + [t for group in section['group_toggles'].values() for t in group]
            assert Counter((t['kind'], t['name']) for t in assigned) == Counter((t['kind'], t['name']) for t in section['toggles'])
        timers = next(s for s in context['settings_sections'] if s['key'] == 'timers')
        assert timers['standalone_toggles'] == []
        assert timers['group_toggles'] == {}
        assert timers['toggles'] == []
        html = templates.env.get_template('channel/settings.html').render(**context)
        assert html.index('<div class="settings-pages"') < html.index('<nav class="settings-menu"')
        assert 'form="settings-toggle-feature-timers"' not in html
        assert 'data-timer-manager' in html
        assert '>Enable\n' not in html
    finally:
        clear_profiles()


def test_reorganized_sections_and_forms():
    try:
        context, _, _ = settings_context()
        assert [s['label'] for s in context['settings_sections']] == ['General', 'Chat', 'Stream Events', 'Timers', 'Connections', 'Loyalty Points', 'Viewer Queue', 'Pets and Boss Hunt']
        html = templates.env.get_template('channel/settings.html').render(**context)
        general = html.split('id="settings-general"')[1].split('id="settings-chat"')[0]
        events = html.split('id="settings-events"')[1].split('id="settings-timers"')[0]
        assert 'id="protected-users"' in general
        assert 'id="youtube-integration"' in general
        assert 'dashboard.follow_raid' not in general
        assert 'dashboard.follow_raid' in events
        raid_messages, raid_preferences = events.split('id="settings-group-raid-preferences"', 1)
        assert 'dashboard.follow_raid' not in raid_messages
        assert 'dashboard.follow_raid' in raid_preferences
        assert 'Follow outgoing raids' in raid_preferences
        for key, next_key in [('timers', 'connections'), ('loyalty', 'queue')]:
            page = html.split(f'id="settings-{key}"')[1].split(f'id="settings-{next_key}"')[0]
            assert '<details class="settings-group"' not in page
    finally:
        clear_profiles()


def test_games_only_contains_enabled_integrations():
    from bot.profiles import ProfileFeatureName
    try:
        _, groups, states = settings_context()
        profile_states = states[1]
        profile_states[ProfileFeatureName.LEAGUE] = SimpleNamespace(effective_enabled=True)
        profile_states[ProfileFeatureName.OVERWATCH] = SimpleNamespace(effective_enabled=False)
        groups.update({'League of Legends': [], 'Overwatch': []})
        sections = build_settings_sections(groups, *states)
        games = next(s for s in sections if s['key'] == 'games')
        assert 'League of Legends' in games['groups']
        assert 'Overwatch' not in games['groups']
        general = next(s for s in sections if s['key'] == 'general')
        assert any(t['name'] == 'league' for t in general['toggles'])
    finally:
        clear_profiles()


def test_related_response_switches_render_inside_their_message_cards():
    from dataclasses import replace
    try:
        context, _, _ = settings_context('events')
        events = next(section for section in context['settings_sections'] if section['key'] == 'events')
        assert events['setting_toggles']['community_messages.follow']['name'] == 'follow_responses'
        entries = events['groups']['Community messages']
        entries[0] = replace(entries[0], override_value='A custom follow response', effective_value='A custom follow response')
        html = templates.env.get_template('channel/settings.html').render(**context)
        card = html.split('data-setting-key="community_messages.follow"', 1)[1].split('</article>', 1)[0]
        assert 'form="settings-toggle-feature-follow_responses"' in card
        assert 'A custom follow response</textarea>' in card
        assert html.count('form="settings-toggle-feature-follow_responses"') == 1
        assert 'value="reset"' not in html
        assert 'Leave empty to send nothing.' not in html
        assert 'data-settings-finder' in html
        assert '<details class="settings-field-editor">' not in card
        assert '<div class="settings-field-body">' in card
        assert 'settings-finder-note' not in html
        for name in ('daily', 'first', 'second', 'vip'):
            assert f'form="settings-toggle-feature-redeem_{name}"' in html
        assert 'settings-toggle-feature-redeems' not in html
    finally:
        clear_profiles()


def test_sidebar_navigation_and_group_descriptions_use_command_registry():
    from bot.command_registry import get_registered_definitions, CommandVisibility
    from bot.profiles import GlobalCommandGroup
    try:
        context, _, _ = settings_context()
        html = templates.env.get_template('channel/settings.html').render(**context)
        assert html.index('class="settings-tools"') < html.index('data-settings-finder hidden') < html.index('class="settings-menu"')
        assert '<summary>Settings menu</summary>' not in html
        assert 'aria-current="page"' in html
        assert 'Included commands (' in html
        assert 'href="?section=events#settings-group-shoutouts"' not in html
        assert 'href="?section=loyalty#setting-points-display_name"' not in html
        assert 'href="?section=connections#socials"' in html
        assert 'href="?section=connections#settings-control-global_group-socials"' not in html
        toggles = [toggle for section in context['settings_sections'] for toggle in section['toggles']]
        assert all(toggle['description'] for toggle in toggles)
        assert all(link[0] != toggle['section'] for toggle in toggles for link in toggle['related_settings'])
        socials = next(toggle for toggle in toggles if toggle['kind'] == 'global_group' and toggle['name'] == 'socials')
        assert socials['related_settings'] == []
        queue = next(toggle for toggle in toggles if toggle['kind'] == 'global_group' and toggle['name'] == 'viewer_queue')
        expected = [command.syntax for command in get_registered_definitions(ChannelProfile(channel_name='example')) if command.global_group is GlobalCommandGroup.VIEWER_QUEUE and command.visibility is CommandVisibility.PUBLIC]
        assert [command.syntax for command in queue['commands']] == expected
        assert '!join' in expected
    finally:
        clear_profiles()
