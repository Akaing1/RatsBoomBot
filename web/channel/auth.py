import secrets

from fastapi import Request


CHANNEL_OAUTH_STATE_KEY = "channel_oauth_state"
CHANNEL_USER_ID_KEY = "channel_user_id"
CHANNEL_USER_LOGIN_KEY = "channel_user_login"
CHANNEL_USER_DISPLAY_NAME_KEY = "channel_user_display_name"
CUSTOM_BOT_OAUTH_STATE_KEY = "channel_custom_bot_oauth_state"
CUSTOM_BOT_BROADCASTER_KEY = "channel_custom_bot_broadcaster_id"


def create_channel_oauth_state(request: Request) -> str:
    request.session.pop(CUSTOM_BOT_OAUTH_STATE_KEY, None)
    request.session.pop(CUSTOM_BOT_BROADCASTER_KEY, None)
    state = secrets.token_urlsafe(32)
    request.session[CHANNEL_OAUTH_STATE_KEY] = state
    return state


def create_custom_bot_oauth_state(request: Request, broadcaster_id: str) -> str:
    request.session.pop(CHANNEL_OAUTH_STATE_KEY, None)
    state = secrets.token_urlsafe(32)
    request.session[CUSTOM_BOT_OAUTH_STATE_KEY] = state
    request.session[CUSTOM_BOT_BROADCASTER_KEY] = str(broadcaster_id)
    return state


def has_custom_bot_oauth_state(request: Request) -> bool:
    return bool(request.session.get(CUSTOM_BOT_OAUTH_STATE_KEY) or request.session.get(CUSTOM_BOT_BROADCASTER_KEY))


def consume_custom_bot_oauth_state(request: Request, submitted_state: str | None) -> str | None:
    expected_state = request.session.pop(CUSTOM_BOT_OAUTH_STATE_KEY, None)
    broadcaster_id = request.session.pop(CUSTOM_BOT_BROADCASTER_KEY, None)

    if not expected_state or not submitted_state or not broadcaster_id:
        return None

    return str(broadcaster_id) if secrets.compare_digest(expected_state, submitted_state) else None


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
    