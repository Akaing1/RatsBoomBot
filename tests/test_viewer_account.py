import base64
import json
import re
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from web.app import app
from web.shared.oauth import TwitchTokenResponse, TwitchUser


def test_viewer_oauth_uses_identity_scope_and_never_onboards_broadcaster(monkeypatch):
    seen = []

    async def exchange(*, code, redirect_uri):
        seen.append((code, redirect_uri))
        return TwitchTokenResponse("viewer-token", "viewer-refresh", 3600, [], "bearer")

    async def fetch(token):
        assert token == "viewer-token"
        return TwitchUser("42", "alice", "Alice")

    class Stats:
        async def get_global_profile(self, user_id):
            assert user_id == "42"
            return None

    monkeypatch.setattr("web.viewer.routers.exchange_code_for_token", exchange)
    monkeypatch.setattr("web.viewer.routers.fetch_twitch_user", fetch)
    monkeypatch.setattr("web.viewer.routers.get_bot", lambda: SimpleNamespace(services=SimpleNamespace(chatter_stats=Stats())))

    with TestClient(app) as client:
        start = client.get("/me/connect", follow_redirects=False)
        query = parse_qs(urlparse(start.headers["location"]).query, keep_blank_values=True)
        assert query["scope"] == [""]
        assert query["redirect_uri"][0].endswith("/oauth/viewer/connect")

        failed = client.get("/oauth/viewer/connect?code=bad&state=incorrect")
        assert failed.status_code == 400
        assert not seen

        start = client.get("/me/connect", follow_redirects=False)
        state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
        callback = client.get(f"/oauth/viewer/connect?code=valid&state={state}", follow_redirects=False)
        assert callback.status_code == 303
        assert callback.headers["location"] == "/me"
        assert len(seen) == 1
        assert client.get(f"/oauth/viewer/connect?code=valid&state={state}").status_code == 400

        account = client.get("/me")
        assert account.status_code == 200
        assert "Welcome, Alice" in account.text
        assert account.headers["cache-control"] == "no-store"

        cookie = client.cookies.get("ratsboombot_session")
        session = json.loads(base64.b64decode(cookie.split(".")[0]))
        assert "viewer-token" not in str(session)
        assert "viewer-refresh" not in str(session)
        assert client.post("/me/logout", data={"csrf_token": "bad"}).status_code == 403
        assert client.get("/me").status_code == 200
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', account.text).group(1)
        assert client.post("/me/logout", data={"csrf_token": csrf}, follow_redirects=False).status_code == 303
        assert client.get("/me", follow_redirects=False).headers["location"] == "/me/connect"


def test_viewer_account_requires_matching_twitch_id(monkeypatch):
    async def exchange(*, code, redirect_uri):
        return TwitchTokenResponse("token", "refresh", 3600, [], "bearer")

    async def fetch(token):
        return TwitchUser("42", "alice", "Alice")

    class Stats:
        async def get_global_profile(self, user_id):
            assert user_id == "42"
            return {"identity": {"user_id": "other-user", "login": "alice"}}

    monkeypatch.setattr("web.viewer.routers.get_bot", lambda: SimpleNamespace(services=SimpleNamespace(chatter_stats=Stats())))
    monkeypatch.setattr("web.viewer.routers.exchange_code_for_token", exchange)
    monkeypatch.setattr("web.viewer.routers.fetch_twitch_user", fetch)

    with TestClient(app) as client:
        start = client.get("/me/connect", follow_redirects=False)
        state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
        client.get(f"/oauth/viewer/connect?code=valid&state={state}", follow_redirects=False)
        # A profile resolved through an old login must not be treated as this user's account.
        account = client.get("/me")
        assert account.status_code == 200
        assert "Welcome, Alice" in account.text
