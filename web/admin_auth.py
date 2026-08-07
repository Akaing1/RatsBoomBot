import secrets

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from config.settings import settings

ADMIN_SESSION_KEY = "admin_authenticated"
CSRF_SESSION_KEY = "csrf_token"


def is_admin_authenticated(request: Request) -> bool:
    return request.session.get(ADMIN_SESSION_KEY) is True


def authenticate_admin(request: Request, submitted_secret: str) -> bool:
    if not secrets.compare_digest(submitted_secret, settings.ADMIN_SECRET):
        return False

    request.session.clear()
    request.session[ADMIN_SESSION_KEY] = True
    request.session[CSRF_SESSION_KEY] = secrets.token_urlsafe(32)

    return True


def logout_admin(request: Request) -> None:
    request.session.clear()


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


def require_admin(request: Request) -> RedirectResponse | None:
    if is_admin_authenticated(request):
        return None

    return RedirectResponse(url="/login", status_code=303)
