from fastapi.testclient import TestClient

from config.settings import settings
from config.version import APP_VERSION
from web.app import app, create_app


def test_root_is_the_public_landing_page() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "An all-in-one bot tailored to your needs" in response.text
    assert "What’s new in RatsBoomBot." in response.text
    assert f"v{APP_VERSION}" in response.text
    assert "Highlights of the last few patches~" in response.text
    assert "https://github.com/Akaing1/RatsBoomBot/releases" in response.text
    assert '<details class="landing-feature-card">' in response.text
    assert "!register &lt;Riot ID&gt; [region]" in response.text
    assert "please contact the developer" in response.text.lower()
    assert "Help keep RatsBoomBot growing." in response.text
    assert 'href="https://ko-fi.com/ninjakaing"' in response.text
    assert "Support never affects features, points, achievements, or raid odds." in response.text
    assert f'{settings.DASHBOARD_BASE_URL}/connect/twitch' in response.text


def test_admin_dashboard_uses_admin_prefix() -> None:
    with TestClient(app) as client:
        response = client.get("/admin", follow_redirects=False)
        login = client.get("/admin/login", follow_redirects=False)
        legacy_login = client.get("/login", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"
    assert login.status_code == 200
    assert legacy_login.status_code == 404


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


def test_loyalty_template_only_shows_names_and_responses() -> None:
    from bot.profiles import ChannelProfile, activate_profile, clear_profiles
    from bot.services.channels.profile_settings import LOYALTY_GROUP, ProfileSettingsService
    from web.shared.common import templates

    activate_profile("loyalty-test", ChannelProfile(channel_name="example"))
    try:
        service = ProfileSettingsService(None)
        groups = service.get_setting_groups("loyalty-test")
        html = templates.env.get_template("channel/loyalty.html").render(
            active_page="loyalty", csrf_token="test", show_social_links=False,
            setting_groups={LOYALTY_GROUP: groups[LOYALTY_GROUP]},
            customization_action="/channel/loyalty", url_for=lambda *args, **kwargs: "/static",
            deployment_stamp=lambda: "test"
        )
        assert 'name="setting_name" value="points.display_name"' in html
        assert 'name="setting_name" value="points.messages.gamble_win"' not in html
        assert html.index('href="/channel/loyalty"') < html.index('href="/channel/help"')
        assert 'action="/channel/loyalty"' in html
        assert "Income amounts are fixed" in html
        assert 'type="number"' not in html
        assert 'social.discord_url' not in html
        assert 'redeems.daily_amount' not in html
    finally:
        clear_profiles()
