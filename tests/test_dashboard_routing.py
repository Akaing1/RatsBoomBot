from fastapi.testclient import TestClient

from config.settings import settings
from web.app import app, create_app


def test_root_is_the_public_landing_page() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "An all-in-one bot tailored to your needs" in response.text
    assert '<details class="landing-feature-card">' in response.text
    assert "!register &lt;Riot ID&gt; [region]" in response.text
    assert "please contact the owner" in response.text.lower()
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
