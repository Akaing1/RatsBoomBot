from types import SimpleNamespace
from unittest.mock import AsyncMock

import asqlite
import pytest

from bot import component_loader
from bot.profiles import FeatureName, GlobalCommandGroup, GlobalCommandName, ProfileFeatureName, activate_profile, clear_profiles, create_generic_profile, get_active_profile
from bot.services.channels.feature_toggle import FeatureToggleService
from bot.services.channels.profile_settings import ProfileSettingsService
from bot.shared.commands.points import PointsCommandHandler
from bot.shared.commands.utility import UtilityCommands


@pytest.fixture(autouse=True)
def reset_profiles():
    clear_profiles()
    yield
    clear_profiles()


@pytest.mark.asyncio
async def test_channel_without_code_profile_loads_and_runs_shared_commands(monkeypatch):
    monkeypatch.setattr(component_loader, "register_channel_profiles", lambda: None)
    features = FeatureToggleService(None)
    points = SimpleNamespace(track_message=AsyncMock(), get_points=AsyncMock(return_value=25))
    services = SimpleNamespace(
        features=features, points=points, profile_settings=ProfileSettingsService(None),
        broadcasters=SimpleNamespace(get_broadcasters=lambda: {"123": SimpleNamespace(login="new_streamer")})
    )
    bot = SimpleNamespace(broadcaster_ids=["123"], services=services)
    await component_loader.load_channel_components(bot)
    profile = get_active_profile("123")
    assert profile.channel_name == "new_streamer"
    assert profile.components == ()
    ctx = SimpleNamespace(broadcaster=SimpleNamespace(id="123"), chatter=SimpleNamespace(id="456", name="viewer"), reply=AsyncMock())
    utility = UtilityCommands(bot)
    await utility.hi.callback(utility, ctx)
    ctx.reply.assert_awaited_with("Hallo viewer!")
    await PointsCommandHandler(bot).show_balance(ctx, None, "points")
    ctx.reply.assert_awaited_with("viewer, you have 25 points!")
    assert all(features.is_global_command_enabled("123", command) for command in GlobalCommandName)
    assert all(features.is_global_group_enabled("123", group) for group in GlobalCommandGroup)
    assert not features.is_enabled("123", FeatureName.RAID_BOSSES)
    assert not features.is_enabled("123", FeatureName.REDEEMS)
    assert not features.is_profile_feature_enabled("123", ProfileFeatureName.LEAGUE)
    assert not features.is_profile_feature_enabled("123", ProfileFeatureName.OVERWATCH)


@pytest.mark.asyncio
async def test_generic_profile_preserves_saved_opt_outs_after_reload(tmp_path):
    activate_profile("123", create_generic_profile("new_streamer"))
    async with asqlite.create_pool(str(tmp_path / "features.db")) as db:
        features = FeatureToggleService(db)
        await features.setup()
        await features.set_global_command_enabled("123", GlobalCommandName.HI, False, "streamer:123")
        await features.set_enabled("123", FeatureName.POINTS, False, "streamer:123")
        reloaded = FeatureToggleService(db)
        await reloaded.setup()
        activate_profile("123", create_generic_profile("new_streamer"))
        assert not reloaded.is_global_command_enabled("123", GlobalCommandName.HI)
        assert not reloaded.is_enabled("123", FeatureName.POINTS)
        assert reloaded.is_global_command_enabled("123", GlobalCommandName.LURK)
        await reloaded.set_enabled("123", FeatureName.CHANNEL, False, "streamer:123")
        assert not reloaded.is_global_command_enabled("123", GlobalCommandName.LURK)
