from types import SimpleNamespace

import pytest

import bot.shared.commands.counters as counter_commands
from bot.channels.barbatos2upusr3x.profile import BARBATOS2UPUSR3X_PROFILE
from bot.channels.developer_ninjakaing.profile import DEVELOPER_NINJAKAING_PROFILE
from bot.channels.lunaaratv.profile import LUNAARATV_PROFILE
from bot.channels.meinya_yozakura.profile import MEINYA_PROFILE
from bot.channels.milky_galaxyvt.profile import MILKY_GALAXYVT_PROFILE
from bot.channels.ninjakaing.profile import NINJAKAING_PROFILE
from bot.channels.okkayay.profile import OKKAYAY_PROFILE
from bot.channels.onedaybread.profile import ONEDAYBREAD_PROFILE
from bot.channels.pikalulz.profile import PIKALULZ_PROFILE
from bot.channels.steohanyy.profile import STEOHANYY_PROFILE
from bot.channels.xxemares.profile import XXEMARES_PROFILE
from bot.profiles import ChannelProfile
from bot.shared.commands.counters import CounterCommands
from web.channel.command_help import BASE_COMMAND_GROUPS


class FakeCounterService:

    def __init__(self) -> None:
        self.incremented_names = []

    async def increment_counter(self, name: str) -> int:
        self.incremented_names.append(name)
        return 7


def build_context() -> SimpleNamespace:
    return SimpleNamespace(
        broadcaster=SimpleNamespace(id="channel-1"),
        chatter=SimpleNamespace(id="any-chatter", name="any_chatter")
    )


@pytest.mark.asyncio
async def test_shared_counter_runs_for_any_chatter_in_enabled_profile(monkeypatch) -> None:
    counter_service = FakeCounterService()
    bot = SimpleNamespace(services=SimpleNamespace(counters=counter_service))
    component = CounterCommands(bot)
    profile = ChannelProfile(channel_name="allowed", shared_counters_enabled=True)
    monkeypatch.setattr(counter_commands, "get_active_profile", lambda broadcaster_id: profile)

    count = await component.increment_counter(build_context(), "explode")

    assert count == 7
    assert counter_service.incremented_names == ["explode"]


@pytest.mark.asyncio
async def test_shared_counter_is_silent_outside_enabled_profiles(monkeypatch) -> None:
    counter_service = FakeCounterService()
    bot = SimpleNamespace(services=SimpleNamespace(counters=counter_service))
    component = CounterCommands(bot)
    profile = ChannelProfile(channel_name="disabled")
    monkeypatch.setattr(counter_commands, "get_active_profile", lambda broadcaster_id: profile)

    count = await component.increment_counter(build_context(), "explode")

    assert count is None
    assert counter_service.incremented_names == []


def test_shared_counters_are_enabled_only_for_selected_profiles() -> None:
    profiles = (
        BARBATOS2UPUSR3X_PROFILE,
        DEVELOPER_NINJAKAING_PROFILE,
        LUNAARATV_PROFILE,
        MEINYA_PROFILE,
        MILKY_GALAXYVT_PROFILE,
        NINJAKAING_PROFILE,
        OKKAYAY_PROFILE,
        ONEDAYBREAD_PROFILE,
        PIKALULZ_PROFILE,
        STEOHANYY_PROFILE,
        XXEMARES_PROFILE
    )
    enabled_channels = {profile.channel_name.lower() for profile in profiles if profile.shared_counters_enabled}

    assert enabled_channels == {"ninjakaing", "developer_ninjakaing", "meinyayozakura"}


def test_shared_counters_are_hidden_from_channel_command_help() -> None:
    assert "Counters" not in {group.name for group in BASE_COMMAND_GROUPS}
