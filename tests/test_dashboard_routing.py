from fastapi.testclient import TestClient

from web.app import app


def test_root_is_the_streamer_entry_point() -> None:
    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/connect"


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
