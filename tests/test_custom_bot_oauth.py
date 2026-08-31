from urllib.parse import parse_qs, urlparse

from starlette.requests import Request

from web.admin.routers.oauth import CUSTOM_BOT_BROADCASTER_KEY, CUSTOM_BOT_OAUTH_STATE_KEY, clear_custom_bot_oauth
from web.shared.oauth import build_bot_oauth_url


def test_custom_bot_oauth_url_carries_session_state() -> None:
    query = parse_qs(urlparse(build_bot_oauth_url(state="secure-state")).query)

    assert query["state"] == ["secure-state"]
    assert "user:write:chat" in query["scope"][0]
    assert "user:bot" in query["scope"][0]
    assert "moderator:manage:announcements" in query["scope"][0]


def test_custom_bot_oauth_session_can_be_cleared() -> None:
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/admin/oauth/bot",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "session": {
            CUSTOM_BOT_OAUTH_STATE_KEY: "secure-state",
            CUSTOM_BOT_BROADCASTER_KEY: "channel-1"
        }
    })

    clear_custom_bot_oauth(request)

    assert CUSTOM_BOT_OAUTH_STATE_KEY not in request.session
    assert CUSTOM_BOT_BROADCASTER_KEY not in request.session
