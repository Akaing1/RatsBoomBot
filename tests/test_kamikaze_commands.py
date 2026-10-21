from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.shared.commands.utility.kamikaze import KamikazeCommands


def create_commands() -> KamikazeCommands:
    return KamikazeCommands(SimpleNamespace())


@pytest.mark.asyncio
@pytest.mark.parametrize('protected,roll,timed_out,expected', [(True,1,True,1),(False,100,True,1),(False,1,True,0),(False,100,False,0),(True,100,False,0)])
async def test_kamikaze_achievement_counts_only_confirmed_target_hits(monkeypatch, protected, roll, timed_out, expected):
    bot = FakeKamikazeBot()
    command = KamikazeCommands(bot)
    context = FakeContext('caller')
    target = SimpleNamespace(id='target', name='target')
    monkeypatch.setattr(command, 'is_protected_target', lambda user, channel: protected and user == 'caller')
    monkeypatch.setattr(command, 'timeout_with_moderator_restore', AsyncMock(return_value=timed_out))
    monkeypatch.setattr('bot.shared.commands.utility.kamikaze.random.randint', lambda *_: roll)
    await command.kamikaze.callback(command, context, target)
    recorder = bot.services.achievements.record_kamikaze_success
    assert recorder.await_count == expected
    if expected:
        recorder.assert_awaited_once_with('channel-1', 'command-message', 'caller', 'target')


@pytest.mark.asyncio
async def test_kamikaze_pet_adds_five_percentage_points_to_hit_chance(monkeypatch):
    bot = FakeKamikazeBot()
    bot.services.pets = SimpleNamespace(bonus_bps=AsyncMock(return_value=500))
    command = KamikazeCommands(bot)
    context = FakeContext('caller')
    target = SimpleNamespace(id='target', name='target')
    monkeypatch.setattr(command, 'is_protected_target', lambda *_: False)
    monkeypatch.setattr(command, 'timeout_with_moderator_restore', AsyncMock(return_value=True))
    monkeypatch.setattr('bot.shared.commands.utility.kamikaze.random.randint', lambda *_: command.KAMIKAZE_SUCCESS_THRESHOLD - 4)

    await command.kamikaze.callback(command, context, target)

    bot.services.pets.bonus_bps.assert_awaited_once_with('caller', 'kamikaze_odds')
    bot.services.achievements.record_kamikaze_success.assert_awaited_once_with('channel-1', 'command-message', 'caller', 'target')


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
        self.services = SimpleNamespace(features=FakeFeatures(), achievements=SimpleNamespace(record_kamikaze_success=AsyncMock(), record_kamikaze_failure=AsyncMock()))
        self.channel = SimpleNamespace()

    def create_partialuser(self, broadcaster_id: str):
        return self.channel


class FakeContext:

    def __init__(self, caller_id: str = "protected-user"):
        self.broadcaster = SimpleNamespace(id="channel-1")
        self.payload = SimpleNamespace(id="command-message")
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
    command = KamikazeCommands(bot)
    context = FakeContext()
    target = SimpleNamespace(id="target-user", name="target")
    timeout_requests = []

    monkeypatch.setattr(command, "is_protected_target", lambda user_id, broadcaster_id: user_id == "protected-user")

    async def timeout_target(channel, broadcaster_id, user_id, username):
        timeout_requests.append((broadcaster_id, user_id, username))
        return True

    monkeypatch.setattr(command, "timeout_with_moderator_restore", timeout_target)
    monkeypatch.setattr("bot.shared.commands.utility.kamikaze.random.randint", lambda start, end: pytest.fail("Protected user rolled randomly."))

    await command.kamikaze.callback(command, context, target)

    assert timeout_requests == [("channel-1", "target-user", "target")]
    assert command.get_kamikaze_cooldown_remaining("channel-1", "protected-user") > 0
    assert context.messages == ["protected's protected kamikaze guaranteed a hit! target has been timed out for 10 seconds."]


@pytest.mark.asyncio
async def test_protected_kamikaze_user_cannot_target_themselves(monkeypatch) -> None:
    command = KamikazeCommands(FakeKamikazeBot())
    context = FakeContext()

    monkeypatch.setattr(command, "is_protected_target", lambda user_id, broadcaster_id: user_id == "protected-user")

    await command.kamikaze.callback(command, context, None)

    assert command.get_kamikaze_cooldown_remaining("channel-1", "protected-user") == 0
    assert context.replies == ["Protected users must choose someone else to bomb."]


@pytest.mark.asyncio
async def test_protected_kamikaze_users_cannot_target_each_other(monkeypatch) -> None:
    command = KamikazeCommands(FakeKamikazeBot())
    context = FakeContext()
    target = SimpleNamespace(id="protected-target", name="protected_target")

    monkeypatch.setattr(command, "is_protected_target", lambda user_id, broadcaster_id: user_id.startswith("protected"))

    async def unexpected_timeout(*args):
        pytest.fail("A protected-to-protected kamikaze attempt caused a timeout.")

    monkeypatch.setattr(command, "timeout_with_moderator_restore", unexpected_timeout)

    await command.kamikaze.callback(command, context, target)

    assert command.get_kamikaze_cooldown_remaining("channel-1", "protected-user") == 0
    assert context.replies == ["Protected users cannot use !kamikaze on each other."]


def test_kamikaze_is_registered_once_as_utility():
    from bot.command_registry import BASE_COMMAND_GROUPS, CommandSlowmode
    from bot.component_loader import GLOBAL_COMPONENTS
    from bot.profiles import GlobalCommandName

    entries = [(group.name, command) for group in BASE_COMMAND_GROUPS
               for command in group.commands if command.name == 'kamikaze']
    assert len(entries) == 1
    category, definition = entries[0]
    assert category == 'Utility'
    assert definition.global_command == GlobalCommandName.KAMIKAZE
    assert definition.slowmode == CommandSlowmode.EXEMPT
    assert GLOBAL_COMPONENTS.count(KamikazeCommands) == 1
    assert all(group.name != 'Moderation' for group in BASE_COMMAND_GROUPS)


@pytest.mark.asyncio
async def test_kamikaze_respects_individual_command_toggle(monkeypatch):
    bot = FakeKamikazeBot()
    command = KamikazeCommands(bot)
    monkeypatch.setattr(bot.services.features, 'is_global_command_enabled', lambda *_: False)
    timeout = AsyncMock()
    monkeypatch.setattr(command, 'timeout_with_moderator_restore', timeout)
    await command.kamikaze.callback(command, FakeContext(), None)
    timeout.assert_not_awaited()
    bot.services.achievements.record_kamikaze_success.assert_not_awaited()
