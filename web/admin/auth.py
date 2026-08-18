import secrets
import time

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from config.settings import settings
from storage.admin_repository import Administrator, get_administrator_by_id, get_administrator_by_username
from web.shared.passwords import verify_password
from web.state import get_db


ADMIN_SESSION_KEY = "administrator_id"
ADMIN_SESSION_STARTED_KEY = "administrator_session_started"
CSRF_SESSION_KEY = "csrf_token"


def clear_admin_session(request: Request) -> None:
    request.session.pop(ADMIN_SESSION_KEY, None)
    request.session.pop(ADMIN_SESSION_STARTED_KEY, None)
    request.session.pop(CSRF_SESSION_KEY, None)


async def get_current_administrator(request: Request) -> Administrator | None:
    administrator_id = request.session.get(ADMIN_SESSION_KEY)

    if administrator_id is None:
        request.state.administrator = None
        return None

    session_started = request.session.get(ADMIN_SESSION_STARTED_KEY)

    if not isinstance(session_started, (int, float)):
        clear_admin_session(request)
        request.state.administrator = None
        return None

    if time.time() - session_started > settings.ADMIN_SESSION_MAX_AGE_SECONDS:
        clear_admin_session(request)
        request.state.administrator = None
        return None

    db = get_db()

    if db is None:
        request.state.administrator = None
        return None

    administrator = await get_administrator_by_id(db, int(administrator_id))

    if administrator is None or not administrator.is_enabled:
        clear_admin_session(request)
        request.state.administrator = None
        return None

    request.state.administrator = administrator
    return administrator


async def is_admin_authenticated(request: Request) -> bool:
    return await get_current_administrator(request) is not None


async def authenticate_administrator(request: Request, username: str, password: str) -> Administrator | None:
    db = get_db()

    if db is None:
        return None

    username = username.strip().lower()
    administrator = await get_administrator_by_username(db, username)

    if administrator is None or not administrator.is_enabled:
        return None

    if not verify_password(administrator.password_hash, password):
        return None

    clear_admin_session(request)
    request.session[ADMIN_SESSION_KEY] = administrator.id
    request.session[ADMIN_SESSION_STARTED_KEY] = time.time()
    request.session[CSRF_SESSION_KEY] = secrets.token_urlsafe(32)

    return administrator


def logout_admin(request: Request) -> None:
    clear_admin_session(request)


def get_csrf_token(request: Request) -> str:
    csrf_token = request.session.get(CSRF_SESSION_KEY)

    if csrf_token:
        return csrf_token

    csrf_token = secrets.token_urlsafe(32)
    request.session[CSRF_SESSION_KEY] = csrf_token
    return csrf_token


def validate_csrf_token(request: Request, submitted_token: str) -> None:
    session_token = request.session.get(CSRF_SESSION_KEY)

    if not session_token:
        raise HTTPException(status_code=403, detail="Missing CSRF session token.")

    if not secrets.compare_digest(session_token, submitted_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token.")


async def require_admin(request: Request) -> RedirectResponse | None:
    if await is_admin_authenticated(request):
        return None

    return RedirectResponse(url="/admin/login", status_code=303)


async def require_owner(request: Request) -> RedirectResponse | None:
    administrator = await get_current_administrator(request)

    if administrator is None:
        return RedirectResponse(url="/admin/login", status_code=303)

    if administrator.role != "owner":
        return RedirectResponse(url="/admin", status_code=303)

    return None
