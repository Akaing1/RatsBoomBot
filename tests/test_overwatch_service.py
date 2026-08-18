from types import SimpleNamespace

import asqlite
import pytest

from bot.profiles import OverwatchConfig
from bot.services.engagement.overwatch import OverwatchNotConfiguredError, OverwatchService, OverwatchSession


class FakePartialUser:

    def __init__(self, stream):
        self.stream = stream

    async def fetch_stream(self):
        return self.stream


class FakeBot:

    def __init__(self, stream):
        self.stream = stream

    def create_partialuser(self, broadcaster_id: str):
        return FakePartialUser(self.stream)


@pytest.mark.asyncio
async def test_overwatch_commands_are_gated_by_current_twitch_game(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "overwatch.db")) as database:
        config = OverwatchConfig()
        service = OverwatchService(FakeBot(SimpleNamespace(game_name="Overwatch 2")), database)
        assert await service.is_allowed_game("channel-1", config) is True

        service.bot.stream = SimpleNamespace(game_name="Just Chatting")
        assert await service.is_allowed_game("channel-1", config) is False

        service.bot.stream = None
        assert await service.is_allowed_game("channel-1", config) is False


@pytest.mark.asyncio
async def test_overwatch_session_records_and_resets_results(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "overwatch.db")) as database:
        service = OverwatchService(FakeBot(None), database)
        await service.setup()

        assert await service.get_session("channel-1") == OverwatchSession()
        assert await service.record_result("channel-1", "win") == OverwatchSession(wins=1)
        assert await service.record_result("channel-1", "loss") == OverwatchSession(wins=1, losses=1)

        await service.reset_session("channel-1")
        assert await service.get_session("channel-1") == OverwatchSession()


@pytest.mark.asyncio
async def test_overwatch_rank_lookup_requires_configured_player(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "overwatch.db")) as database:
        service = OverwatchService(FakeBot(None), database)

        with pytest.raises(OverwatchNotConfiguredError):
            await service.fetch_ranks(OverwatchConfig())


def test_overwatch_rank_formatting() -> None:
    assert OverwatchService.format_rank({"division": "diamond", "tier": 3}) == "Diamond 3"
    assert OverwatchService.format_rank(None) is None
