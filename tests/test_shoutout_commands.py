from types import SimpleNamespace

import pytest

from bot.shared.commands.converters import LocalizedUser
from bot.shared.commands.shoutout import ShoutoutCommands


class FakeShoutouts:

    def __init__(self):
        self.queued = []
        self.messages = []

    def enqueue(self, **values):
        self.queued.append(values)
        return True, "Queued.", 1

    async def send_chat_message(self, broadcaster_id: str, username: str) -> bool:
        self.messages.append((broadcaster_id, username))
        return True


class FakeChatters:

    def __init__(self, target):
        self.target = target
        self.arguments = []

    async def resolve(self, broadcaster_id: str, argument: str):
        self.arguments.append((broadcaster_id, argument))
        return self.target


class FakeFeatures:

    @staticmethod
    def is_global_group_enabled(broadcaster_id, group) -> bool:
        return True


class FakeBot:

    def __init__(self, target):
        self.shoutouts = FakeShoutouts()
        self.chatters = FakeChatters(target)
        self.services = SimpleNamespace(features=FakeFeatures(), shoutouts=self.shoutouts, chatters=self.chatters)


class FakeContext:

    def __init__(self, bot):
        self.bot = bot
        self.broadcaster = SimpleNamespace(id="channel-1", name="channel")
        self.chatter = SimpleNamespace(id="mod-1", name="moderator", moderator=True)
        self.replies = []

    async def reply(self, message: str) -> None:
        self.replies.append(message)


@pytest.mark.asyncio
async def test_shoutout_resolves_localized_display_name_through_chatter_identity() -> None:
    target = SimpleNamespace(id="23556464", name="ascii_login", display_name="日本語の名前")
    bot = FakeBot(target)
    context = FakeContext(bot)
    resolved_target = await LocalizedUser().convert(context, "@日本語の名前")
    command = ShoutoutCommands(bot)

    await command.shoutout.callback(command, context, resolved_target)

    assert bot.chatters.arguments == [("channel-1", "@日本語の名前")]
    assert bot.shoutouts.queued == [{
        "broadcaster_id": "channel-1",
        "user_id": "23556464",
        "username": "ascii_login",
        "requested_by": "moderator"
    }]
    assert bot.shoutouts.messages == [("channel-1", "ascii_login")]
    assert context.replies == []


@pytest.mark.asyncio
async def test_shoutout_rejects_broadcaster_by_resolved_user_id() -> None:
    target = SimpleNamespace(id="channel-1", name="channel", display_name="チャンネル")
    bot = FakeBot(target)
    context = FakeContext(bot)
    command = ShoutoutCommands(bot)

    await command.shoutout.callback(command, context, target)

    assert bot.shoutouts.queued == []
    assert context.replies == ["You cannot shoutout the broadcaster."]
