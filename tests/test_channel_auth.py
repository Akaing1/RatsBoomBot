from starlette.requests import Request

from web.channel.auth import (
    CHANNEL_USER_DISPLAY_NAME_KEY,
    CHANNEL_USER_ID_KEY,
    CHANNEL_USER_LOGIN_KEY,
    login_channel_user,
    logout_channel_user
)


def create_request() -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "session": {}
    })


def test_channel_login_is_saved_until_explicit_logout() -> None:
    request = create_request()

    login_channel_user(request, "123", "streamer", "Streamer")

    assert request.session[CHANNEL_USER_ID_KEY] == "123"
    assert request.session[CHANNEL_USER_LOGIN_KEY] == "streamer"
    assert request.session[CHANNEL_USER_DISPLAY_NAME_KEY] == "Streamer"

    logout_channel_user(request)

    assert CHANNEL_USER_ID_KEY not in request.session
    assert CHANNEL_USER_LOGIN_KEY not in request.session
    assert CHANNEL_USER_DISPLAY_NAME_KEY not in request.session
