import pytest
from fastapi import HTTPException
from starlette.requests import Request

import web.admin.auth as admin_auth
from web.admin.auth import get_csrf_token, logout_admin, require_admin, validate_csrf_token


def create_request() -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "session": {}
    }

    return Request(scope)


def test_csrf_token_is_stable_for_session() -> None:
    request = create_request()

    first_token = get_csrf_token(request)
    second_token = get_csrf_token(request)

    assert first_token == second_token


def test_validate_csrf_token_rejects_missing_token() -> None:
    request = create_request()

    with pytest.raises(HTTPException) as exception:
        validate_csrf_token(request, "anything")

    assert exception.value.status_code == 403


def test_validate_csrf_token_rejects_wrong_token() -> None:
    request = create_request()
    request.session["csrf_token"] = "expected"

    with pytest.raises(HTTPException) as exception:
        validate_csrf_token(request, "wrong")

    assert exception.value.status_code == 403


@pytest.mark.asyncio
async def test_require_admin_allows_authenticated_request(monkeypatch) -> None:
    async def authenticated(_request: Request) -> bool:
        return True

    monkeypatch.setattr(admin_auth, "is_admin_authenticated", authenticated)

    assert await require_admin(create_request()) is None


@pytest.mark.asyncio
async def test_logout_clears_session_and_requires_login(monkeypatch) -> None:
    async def unauthenticated(_request: Request) -> bool:
        return False

    monkeypatch.setattr(admin_auth, "is_admin_authenticated", unauthenticated)

    request = create_request()
    request.session["administrator_id"] = 1
    request.session["csrf_token"] = "token"

    logout_admin(request)
    redirect = await require_admin(request)

    assert request.session == {}
    assert redirect is not None
    assert redirect.status_code == 303
    assert redirect.headers["location"] == "/admin/login"


@pytest.mark.asyncio
async def test_expired_admin_session_preserves_channel_login(monkeypatch) -> None:
    request = create_request()
    request.session.update({
        "administrator_id": 1,
        "administrator_session_started": 100.0,
        "csrf_token": "token",
        "channel_user_id": "123",
        "channel_user_login": "streamer"
    })

    monkeypatch.setattr(admin_auth.time, "time", lambda: 100.0 + 60 * 60 * 9)

    assert await admin_auth.get_current_administrator(request) is None
    assert "administrator_id" not in request.session
    assert "administrator_session_started" not in request.session
    assert request.session["channel_user_id"] == "123"
    assert request.session["channel_user_login"] == "streamer"
