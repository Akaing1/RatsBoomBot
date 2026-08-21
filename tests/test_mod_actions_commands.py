from types import SimpleNamespace

import pytest

from bot.shared.commands.mod_actions import ModActionCommands


def create_commands() -> ModActionCommands:
    return ModActionCommands(SimpleNamespace())


def test_kamikaze_cooldown_notice_is_sent_once_per_window() -> None:
    command = create_commands()
    command.start_kamikaze_cooldown("channel-1", "viewer-1")

    assert command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-1", 599)
    assert not command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-1", 450)
    assert command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-1", 300)
    assert not command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-1", 1)


def test_kamikaze_cooldown_notices_are_separate_by_channel_and_viewer() -> None:
    command = create_commands()

    assert command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-1", 500)
    assert command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-2", 500)
    assert command.should_send_kamikaze_cooldown_notice("channel-2", "viewer-1", 500)


def test_starting_new_kamikaze_cooldown_resets_notice_windows() -> None:
    command = create_commands()

    command.start_kamikaze_cooldown("channel-1", "viewer-1")
    assert command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-1", 500)
    assert not command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-1", 500)

    command.start_kamikaze_cooldown("channel-1", "viewer-1")

    assert command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-1", 500)


class FakeFeatures:

    @staticmethod
    def is_global_command_enabled(broadcaster_id, command) -> bool:
        return True


class FakeKamikazeBot:

    def __init__(self):
        self.services = SimpleNamespace(features=FakeFeatures())
        self.channel = SimpleNamespace()

    def create_partialuser(self, broadcaster_id: str):
        return self.channel


class FakeContext:

    def __init__(self, caller_id: str = "protected-user"):
        self.broadcaster = SimpleNamespace(id="channel-1")
        self.chatter = SimpleNamespace(id=caller_id, name="protected")
        self.messages = []
        self.replies = []

    async def send(self, message: str) -> None:
        self.messages.append(message)

    async def reply(self, message: str) -> None:
        self.replies.append(message)


@pytest.mark.asyncio
async def test_protected_kamikaze_user_guarantees_hit_on_unprotected_target(monkeypatch) -> None:
    bot = FakeKamikazeBot()
    command = ModActionCommands(bot)
    context = FakeContext()
    target = SimpleNamespace(id="target-user", name="target")
    timeout_requests = []

    monkeypatch.setattr(command, "is_protected_target", lambda user_id, broadcaster_id: user_id == "protected-user")

    async def timeout_target(channel, broadcaster_id, user_id, username):
        timeout_requests.append((broadcaster_id, user_id, username))
        return True

    monkeypatch.setattr(command, "timeout_with_moderator_restore", timeout_target)
    monkeypatch.setattr("bot.shared.commands.mod_actions.random.randint", lambda start, end: pytest.fail("Protected user rolled randomly."))

    await command.kamikaze.callback(command, context, target)

    assert timeout_requests == [("channel-1", "target-user", "target")]
    assert command.get_kamikaze_cooldown_remaining("channel-1", "protected-user") > 0
    assert context.messages == ["protected's protected kamikaze guaranteed a hit! target has been timed out for 10 seconds."]


@pytest.mark.asyncio
async def test_protected_kamikaze_user_cannot_target_themselves(monkeypatch) -> None:
    command = ModActionCommands(FakeKamikazeBot())
    context = FakeContext()

    monkeypatch.setattr(command, "is_protected_target", lambda user_id, broadcaster_id: user_id == "protected-user")

    await command.kamikaze.callback(command, context, None)

    assert command.get_kamikaze_cooldown_remaining("channel-1", "protected-user") == 0
    assert context.replies == ["Protected users must choose someone else to bomb."]


@pytest.mark.asyncio
async def test_protected_kamikaze_users_cannot_target_each_other(monkeypatch) -> None:
    command = ModActionCommands(FakeKamikazeBot())
    context = FakeContext()
    target = SimpleNamespace(id="protected-target", name="protected_target")

    monkeypatch.setattr(command, "is_protected_target", lambda user_id, broadcaster_id: user_id.startswith("protected"))

    async def unexpected_timeout(*args):
        pytest.fail("A protected-to-protected kamikaze attempt caused a timeout.")

    monkeypatch.setattr(command, "timeout_with_moderator_restore", unexpected_timeout)

    await command.kamikaze.callback(command, context, target)

    assert command.get_kamikaze_cooldown_remaining("channel-1", "protected-user") == 0
    assert context.replies == ["Protected users cannot use !kamikaze on each other."]
