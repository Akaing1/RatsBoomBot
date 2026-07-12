import pytest
from fastapi import HTTPException

from config.settings import settings
from web.admin_auth import (
    authenticate_admin,
    get_csrf_token,
    is_admin_authenticated,
    logout_admin,
    require_admin,
    validate_csrf_token
)


class FakeRequest:
    def __init__(self) -> None:
        self.session: dict[str, object] = {}


def test_authenticate_admin_accepts_correct_secret(monkeypatch) -> None:
    monkeypatch.setattr(settings,"ADMIN_SECRET","correct-secret")

    request = FakeRequest()
    authenticated = authenticate_admin(request, "correct-secret")

    assert authenticated is True
    assert is_admin_authenticated(request) is True
    assert request.session["csrf_token"]


def test_authenticate_admin_rejects_wrong_secret(monkeypatch) -> None:
    monkeypatch.setattr(settings,"ADMIN_SECRET","correct-secret")

    request = FakeRequest()

    authenticated = authenticate_admin(request,"wrong-secret")

    assert authenticated is False
    assert request.session == {}


def test_csrf_token_is_stable_for_session() -> None:
    request = FakeRequest()

    first_token = get_csrf_token(request)
    second_token = get_csrf_token(request)
    assert first_token == second_token


def test_validate_csrf_token_rejects_missing_token() -> None:
    request = FakeRequest()

    with pytest.raises( HTTPException) as exception:
        validate_csrf_token(request,"anything")

    assert exception.value.status_code == 403


def test_validate_csrf_token_rejects_wrong_token() -> None:
    request = FakeRequest()
    request.session["csrf_token"] = "expected"

    with pytest.raises(HTTPException) as exception:
        validate_csrf_token(request,"wrong")

    assert exception.value.status_code == 403


def test_logout_clears_session_and_requires_login() -> None:
    request = FakeRequest()

    request.session["admin_authenticated"] = True
    request.session["csrf_token"] = "token"

    assert require_admin(request) is None

    logout_admin(request)

    redirect = require_admin(request)

    assert request.session == {}
    assert redirect is not None
    assert redirect.status_code == 303
    assert redirect.headers["location"] == "/login"
