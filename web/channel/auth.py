import secrets

from fastapi import Request


CHANNEL_OAUTH_STATE_KEY = "channel_oauth_state"
CHANNEL_USER_ID_KEY = "channel_user_id"
CHANNEL_USER_LOGIN_KEY = "channel_user_login"
CHANNEL_USER_DISPLAY_NAME_KEY = "channel_user_display_name"


def create_channel_oauth_state(request: Request) -> str:
    state = secrets.token_urlsafe(32)
    request.session[CHANNEL_OAUTH_STATE_KEY] = state
    return state


def validate_channel_oauth_state(request: Request, submitted_state: str | None) -> bool:
    expected_state = request.session.pop(CHANNEL_OAUTH_STATE_KEY, None)

    if not expected_state or not submitted_state:
        return False

    return secrets.compare_digest(expected_state, submitted_state)


def login_channel_user(request: Request, user_id: str, login: str, display_name: str) -> None:
    request.session[CHANNEL_USER_ID_KEY] = user_id
    request.session[CHANNEL_USER_LOGIN_KEY] = login
    request.session[CHANNEL_USER_DISPLAY_NAME_KEY] = display_name


def logout_channel_user(request: Request) -> None:
    request.session.pop(CHANNEL_USER_ID_KEY, None)
    request.session.pop(CHANNEL_USER_LOGIN_KEY, None)
    request.session.pop(CHANNEL_USER_DISPLAY_NAME_KEY, None)
