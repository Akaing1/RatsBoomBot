from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.shared.commands.settings import SettingsCommands
from config.settings import settings


class FakeFeatures:

    def is_global_group_enabled(self, broadcaster_id, group):
        return True


class FakeBroadcaster:

    def __init__(self):
        self.updates = []

    async def modify_channel(self, **values):
        self.updates.append(values)


class FakeBot:

    def __init__(self, game=None):
        self.game = game
        self.broadcaster = FakeBroadcaster()
        self.services = SimpleNamespace(features=FakeFeatures())

    async def fetch_game(self, *, name):
        return self.game

    def create_partialuser(self, broadcaster_id):
        return self.broadcaster


class FakeContext:

    def __init__(self, *, user_id="mod-1", moderator=True):
        self.broadcaster = SimpleNamespace(id="channel-1")
        self.chatter = SimpleNamespace(id=user_id, name="alice", moderator=moderator)
        self.replies = []

    async def reply(self, message):
        self.replies.append(message)


def test_channel_authorization_includes_broadcast_management_scope() -> None:
    assert "channel:manage:broadcast" in settings.CHANNEL_SCOPES.split()


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["discord", "youtube"])
async def test_set_social_subcommand_updates_channel_and_rejects_viewers(name):
    bot = FakeBot()
    setter = AsyncMock()
    bot.services.broadcaster_settings = SimpleNamespace(**{f"set_{name}_url": setter})
    component = SettingsCommands(bot)
    command = component.set_channel.get_command(name)
    assert command is not None
    context = FakeContext()
    url = "https://discord.gg/test" if name == "discord" else "https://youtube.com/@test"
    await command.callback(component, context, url=url)
    setter.assert_awaited_once_with(broadcaster_id="channel-1", **{f"{name}_url": url})
    setter.reset_mock()
    await command.callback(component, FakeContext(moderator=False), url=url)
    setter.assert_not_awaited()
    await command.callback(component, context)
    assert f"!set {name}" in context.replies[-1]


@pytest.mark.asyncio
async def test_moderator_can_set_stream_game() -> None:
    game = SimpleNamespace(id="509658", name="Just Chatting")
    bot = FakeBot(game=game)
    component = SettingsCommands(bot)
    context = FakeContext()

    await component.set_game.callback(component, context, game_name="Just Chatting")

    assert bot.broadcaster.updates == [{"game_id": "509658"}]
    assert context.replies == ['Stream game updated to "Just Chatting".']


@pytest.mark.asyncio
async def test_broadcaster_can_set_stream_title() -> None:
    bot = FakeBot()
    component = SettingsCommands(bot)
    context = FakeContext(user_id="channel-1", moderator=False)

    await component.set_title.callback(component, context, title="A brand new stream title")

    assert bot.broadcaster.updates == [{"title": "A brand new stream title"}]
    assert context.replies == ['Stream title updated to "A brand new stream title".']


@pytest.mark.asyncio
async def test_set_game_rejects_unknown_twitch_category() -> None:
    bot = FakeBot(game=None)
    component = SettingsCommands(bot)
    context = FakeContext()

    await component.set_game.callback(component, context, game_name="Definitely Not A Game")

    assert bot.broadcaster.updates == []
    assert context.replies == ['I could not find a Twitch category named "Definitely Not A Game".']


@pytest.mark.asyncio
async def test_viewer_cannot_change_stream_information() -> None:
    bot = FakeBot(game=SimpleNamespace(id="509658", name="Just Chatting"))
    component = SettingsCommands(bot)
    context = FakeContext(user_id="viewer-1", moderator=False)

    await component.set_title.callback(component, context, title="Unauthorized title")

    assert bot.broadcaster.updates == []
    assert context.replies == ["Only the broadcaster or mods can change the stream title."]
