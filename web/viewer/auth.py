import secrets
import re

from fastapi import Request


VIEWER_OAUTH_STATE_KEY = "viewer_oauth_state"
VIEWER_OAUTH_NEXT_KEY = "viewer_oauth_next"
VIEWER_USER_ID_KEY = "viewer_user_id"
VIEWER_USER_LOGIN_KEY = "viewer_user_login"
VIEWER_USER_DISPLAY_NAME_KEY = "viewer_user_display_name"


PROFILE_PATH = re.compile(r"/chatters/[a-zA-Z0-9_]+(?:/channels/[a-zA-Z0-9_]+)?\Z")


def start_viewer_oauth(request: Request, next_path: str = "") -> str:
    state = secrets.token_urlsafe(32)
    request.session[VIEWER_OAUTH_STATE_KEY] = state
    request.session[VIEWER_OAUTH_NEXT_KEY] = next_path if PROFILE_PATH.fullmatch(next_path) else "/me"
    return state


def consume_viewer_oauth_state(request: Request, submitted_state: str | None) -> bool:
    expected = request.session.pop(VIEWER_OAUTH_STATE_KEY, None)
    return bool(expected and submitted_state and secrets.compare_digest(expected, submitted_state))


def viewer_user_id(request: Request) -> str | None:
    value = request.session.get(VIEWER_USER_ID_KEY)
    return value if isinstance(value, str) and value else None


def logout_viewer(request: Request) -> None:
    for key in (VIEWER_USER_ID_KEY, VIEWER_USER_LOGIN_KEY, VIEWER_USER_DISPLAY_NAME_KEY, VIEWER_OAUTH_STATE_KEY, VIEWER_OAUTH_NEXT_KEY):
        request.session.pop(key, None)
