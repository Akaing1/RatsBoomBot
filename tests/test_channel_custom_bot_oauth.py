from types import SimpleNamespace

from web.channel.auth import (
    CHANNEL_OAUTH_STATE_KEY,
    CUSTOM_BOT_BROADCASTER_KEY,
    CUSTOM_BOT_OAUTH_STATE_KEY,
    consume_custom_bot_oauth_state,
    create_channel_oauth_state,
    create_custom_bot_oauth_state,
    has_custom_bot_oauth_state
)


def test_custom_bot_oauth_state_is_bound_to_broadcaster_and_single_use() -> None:
    request = SimpleNamespace(session={})
    state = create_custom_bot_oauth_state(request, "channel-1")

    assert has_custom_bot_oauth_state(request) is True
    assert consume_custom_bot_oauth_state(request, state) == "channel-1"
    assert consume_custom_bot_oauth_state(request, state) is None
    assert has_custom_bot_oauth_state(request) is False


def test_custom_bot_oauth_rejects_wrong_state_and_clears_session() -> None:
    request = SimpleNamespace(session={})
    create_custom_bot_oauth_state(request, "channel-1")

    assert consume_custom_bot_oauth_state(request, "wrong-state") is None
    assert CUSTOM_BOT_OAUTH_STATE_KEY not in request.session
    assert CUSTOM_BOT_BROADCASTER_KEY not in request.session


def test_channel_and_custom_bot_oauth_states_do_not_overlap() -> None:
    request = SimpleNamespace(session={})
    create_channel_oauth_state(request)
    create_custom_bot_oauth_state(request, "channel-1")

    assert CHANNEL_OAUTH_STATE_KEY not in request.session

    create_channel_oauth_state(request)

    assert CUSTOM_BOT_OAUTH_STATE_KEY not in request.session
    assert CUSTOM_BOT_BROADCASTER_KEY not in request.session
