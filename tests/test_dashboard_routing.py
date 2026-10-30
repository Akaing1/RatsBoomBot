import pytest

from fastapi.testclient import TestClient
from urllib.parse import parse_qs, urlparse

from config.settings import settings
from web.app import app, create_app
from web.shared.common import templates


def test_root_is_the_public_landing_page() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "An all-in-one bot tailored to your needs" in response.text
    assert "What’s new in RatsBoomBot." in response.text
    assert "Your dashboard, shared with your team" in response.text
    assert "Discover, save, and revisit" in response.text
    assert "Pets and a home for your community profile" in response.text
    assert "v15–16" in response.text
    assert "!pets summon" in response.text
    assert 'href="/patch-notes"' in response.text
    assert "https://github.com/Akaing1/RatsBoomBot/releases" not in response.text
    assert '<details class="landing-feature-card">' in response.text
    assert "!register &lt;Riot ID&gt; [region]" in response.text
    assert "!custom lobby balance" in response.text
    assert "!raid repair &lt;weapon&gt;" in response.text
    assert "Connect with Twitch" in response.text
    assert "Make the dashboard yours" in response.text
    assert "Connect and go live" in response.text
    assert "Core onboarding is self-service." in response.text
    assert "Twitch stream" in response.text
    assert "Combined Chat" in response.text
    assert "Viewer queue" in response.text
    assert "Help keep RatsBoomBot growing." in response.text
    assert 'href="https://ko-fi.com/ninjakaing"' in response.text
    assert "Support never affects features, points, achievements, or raid odds." in response.text
    assert response.text.count('href="/me/connect"') == 2
    assert "Sign in to Your Chatter Profile" in response.text
    assert "Streamer setup" in response.text
    assert "Set Up the Bot" in response.text
    assert response.text.count(f'href="{settings.DASHBOARD_BASE_URL}/connect/twitch"') == 1
    assert response.text.index('href="/me/connect"') < response.text.index(f'href="{settings.DASHBOARD_BASE_URL}/connect/twitch"')


def test_canceling_broadcaster_setup_returns_home() -> None:
    with TestClient(app) as client:
        start = client.get("/connect/twitch", follow_redirects=False)
        state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
        canceled = client.get(f"/oauth/channel/connect?error=access_denied&state={state}", follow_redirects=False)

    assert canceled.status_code == 303
    assert canceled.headers["location"] == "/"


def test_admin_dashboard_uses_admin_prefix() -> None:
    with TestClient(app) as client:
        response = client.get("/admin", follow_redirects=False)
        login = client.get("/admin/login", follow_redirects=False)
        legacy_login = client.get("/login", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"
    assert login.status_code == 200
    assert legacy_login.status_code == 404


def test_admin_layout_uses_standard_dashboard_navigation() -> None:
    layout = templates.env.get_template("admin/layout.html").render(
        active_page="dashboard", administrator=None, csrf_token="test",
        url_for=lambda *args, **kwargs: kwargs.get("path", "/static/resource"),
        deployment_stamp=lambda: "test"
    )

    assert 'class="dashboard-page admin-page admin-page-dashboard"' in layout
    assert "data-dashboard-shell" in layout
    assert 'data-sidebar-storage-key="ratsboombot-admin-sidebar-collapsed"' in layout
    assert "data-sidebar-toggle" in layout
    assert "channel-sidebar.js" in layout


def test_channel_oauth_session_cookie_is_persistent() -> None:
    with TestClient(app) as client:
        response = client.get("/connect/twitch", follow_redirects=False)

    cookie = response.headers["set-cookie"].lower()

    assert "ratsboombot_session=" in cookie
    assert "max-age=2592000" in cookie
    assert "httponly" in cookie


def test_session_cookie_can_be_shared_across_ratsboombot_subdomains(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SESSION_COOKIE_DOMAIN", ".ratsboombot.com")
    application = create_app()

    with TestClient(application, base_url="https://ratsboombot.com") as client:
        response = client.get("/connect/twitch", follow_redirects=False)

    assert "domain=.ratsboombot.com" in response.headers["set-cookie"].lower()


def test_channel_help_requires_channel_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/channel/help", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/connect"


def test_loyalty_tab_requires_channel_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/channel/loyalty", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/connect"


def test_sidebar_uses_settings_instead_of_duplicate_loyalty_page() -> None:
    html = templates.env.get_template("channel/layout.html").render(
        active_page="settings", url_for=lambda *args, **kwargs: "/static",
        deployment_stamp=lambda: "test",
    )
    assert 'href="/channel/settings"' in html
    assert 'href="/channel/loyalty"' not in html


def test_commands_card_contains_protected_user_management() -> None:
    from bot.profiles import ChannelProfile, activate_profile, clear_profiles
    from bot.services.channels.profile_settings import ProfileSettingsService
    from web.shared.common import templates

    activate_profile("channel-1", ChannelProfile(channel_name="example"))
    try:
        service = ProfileSettingsService(None)
        groups = service.get_setting_groups("channel-1")
        html = templates.env.get_template("shared/profile_inputs.html").render(
            setting_groups={"Commands": groups["Commands"]},
            protected_users=[{
                "user_id": "123",
                "login": "viewer",
                "display_name": "Viewer",
                "is_default": False,
                "removable": True
            }],
            command_tab="protected",
            show_social_links=False,
            csrf_token="test",
            customization_action="/channel/customization"
        )

        assert 'data-command-tab="protected"' in html
        assert 'data-protected-user-search' in html
        assert 'action="/channel/protected-users/add"' in html
        assert 'action="/channel/protected-users/remove"' in html
        assert "Viewer <span>(123)</span>" in html
    finally:
        clear_profiles()


@pytest.mark.asyncio
async def test_legacy_settings_redirects_preserve_feedback_and_select_loyalty():
    from fastapi import Request
    from web.channel.routers.dashboard import legacy_channel_settings_page
    from web.channel.auth import CHANNEL_USER_ID_KEY
    for path in ('/channel/features', '/channel/customization', '/channel/loyalty'):
        request = Request({'type': 'http', 'scheme': 'https', 'server': ('example.com', 443),
                           'path': path, 'query_string': b'setting_result=success&setting_message=Saved',
                           'headers': [], 'session': {CHANNEL_USER_ID_KEY: '123'}})
        response = await legacy_channel_settings_page(request)
        target = urlparse(response.headers['location'])
        assert target.path == '/channel/settings'
        query = parse_qs(target.query)
        assert query['setting_message'] == ['Saved']
        if path.endswith('/loyalty'):
            assert query['section'] == ['loyalty']
