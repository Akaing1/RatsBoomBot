from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from web.channel.routers import oauth
from web.channel.auth import CHANNEL_OAUTH_STATE_KEY


@pytest.fixture
async def auth_client(monkeypatch):
    session = {CHANNEL_OAUTH_STATE_KEY: "expected", "channel_user_id": "existing"}
    app = FastAPI()
    @app.middleware("http")
    async def session_middleware(request, call_next):
        request.scope["session"] = session
        return await call_next(request)
    root = Path(__file__).resolve().parents[1]
    app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")
    app.mount("/static", StaticFiles(directory=root / "web/static"), name="static")
    app.include_router(oauth.router)
    monkeypatch.setattr(oauth, "get_bot", lambda: None)
    monkeypatch.setattr(oauth, "get_db", lambda: None)
    exchange = AsyncMock(return_value=SimpleNamespace(access_token="secret", refresh_token="refresh"))
    monkeypatch.setattr(oauth, "exchange_code_for_token", exchange)
    monkeypatch.setattr(oauth, "fetch_twitch_user", AsyncMock(return_value=SimpleNamespace(
        user_id="new", login="new", display_name="New")))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, session, exchange


@pytest.mark.asyncio
@pytest.mark.parametrize("query,status", [
    ("state=wrong&code=code", 400),
    ("code=code", 400),
    ("state=expected", 400),
    ("state=expected&code=code", 503),
])
async def test_failed_channel_auth_has_only_public_recovery(auth_client, query, status):
    client, session, _ = auth_client
    response = await client.get("/oauth/channel/connect?" + query)
    assert response.status_code == status
    assert 'href="/connect/twitch"' in response.text
    assert 'href="/"' in response.text
    assert "/admin" not in response.text
    assert 'href="/login"' not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert session["channel_user_id"] == "existing"


@pytest.mark.asyncio
async def test_exchange_failure_does_not_expose_tokens_or_admin(auth_client):
    client, _, exchange = auth_client
    exchange.side_effect = RuntimeError("secret credential")
    response = await client.get("/oauth/channel/connect?state=expected&code=code")
    assert response.status_code == 500
    assert "secret credential" not in response.text
    assert "/admin" not in response.text
    assert 'href="/connect/twitch"' in response.text


@pytest.mark.asyncio
async def test_cancelled_channel_auth_returns_home(auth_client):
    client, session, exchange = auth_client
    response = await client.get("/oauth/channel/connect?state=expected&error=access_denied")
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert session["channel_user_id"] == "existing"
    exchange.assert_not_awaited()


@pytest.mark.asyncio
async def test_success_still_returns_to_channel_dashboard(auth_client, monkeypatch):
    client, session, _ = auth_client
    onboard = AsyncMock()
    monkeypatch.setattr(oauth, "get_bot", lambda: SimpleNamespace(onboard_broadcaster=onboard))
    response = await client.get("/oauth/channel/connect?state=expected&code=code")
    assert response.status_code == 303
    assert response.headers["location"] == "/channel"
    assert session["channel_user_id"] == "new"
    onboard.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalid_state_never_exchanges_code(auth_client):
    client, _, exchange = auth_client
    response = await client.get("/oauth/channel/connect?state=wrong&code=code")
    assert response.status_code == 400
    exchange.assert_not_awaited()

@pytest.mark.asyncio
@pytest.mark.parametrize('cancel', [False, True])
async def test_dock_login_returns_to_originating_dock(auth_client, monkeypatch, cancel):
    client, session, exchange = auth_client
    live = SimpleNamespace(resolve_widget_token=lambda token: 'new' if token == 'valid' else None)
    monkeypatch.setattr(oauth, 'get_bot', lambda: SimpleNamespace(
        onboard_broadcaster=AsyncMock(), services=SimpleNamespace(live_chat=live)))
    response = await client.get('/connect/twitch?dock=valid')
    assert response.status_code == 307
    state = session[CHANNEL_OAUTH_STATE_KEY]
    query = 'error=access_denied' if cancel else 'code=code'
    response = await client.get(f'/oauth/channel/connect?state={state}&{query}')
    assert response.headers['location'] == '/widgets/chat/valid'
    assert oauth.DOCK_RETURN_TOKEN_KEY not in session
    if cancel:
        exchange.assert_not_awaited()
    else:
        assert session['channel_user_id'] == 'new'


@pytest.mark.asyncio
async def test_dock_return_cannot_be_external_stale_or_revoked(auth_client, monkeypatch):
    client, session, _ = auth_client
    valid = [True]
    live = SimpleNamespace(resolve_widget_token=lambda token: 'new' if token == 'valid' and valid[0] else None)
    monkeypatch.setattr(oauth, 'get_bot', lambda: SimpleNamespace(
        onboard_broadcaster=AsyncMock(), services=SimpleNamespace(live_chat=live)))
    session[oauth.DOCK_RETURN_TOKEN_KEY] = 'valid'
    await client.get('/connect/twitch?dock=https://evil.example')
    assert oauth.DOCK_RETURN_TOKEN_KEY not in session
    await client.get('/connect/twitch?dock=valid')
    state = session[CHANNEL_OAUTH_STATE_KEY]
    valid[0] = False
    response = await client.get(f'/oauth/channel/connect?state={state}&code=code')
    assert response.headers['location'] == '/channel'
    assert oauth.DOCK_RETURN_TOKEN_KEY not in session
