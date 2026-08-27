import asqlite
import pytest

from bot.profiles import ChannelProfile, LeagueConfig, OverwatchConfig, ProfileFeatureName, activate_profile, clear_profiles
from bot.services.channels.feature_toggle import FeatureToggleService


@pytest.fixture(autouse=True)
def reset_active_profiles():
    clear_profiles()
    yield
    clear_profiles()


def test_unique_features_only_include_configured_profile_integrations() -> None:
    league_profile = ChannelProfile(channel_name="league", league=LeagueConfig(enabled=True))
    overwatch_profile = ChannelProfile(channel_name="overwatch", overwatch=OverwatchConfig(player_id="Player#123"))
    plain_profile = ChannelProfile(channel_name="plain")
    service = FeatureToggleService(db=None)

    activate_profile("league-channel", league_profile)
    activate_profile("overwatch-channel", overwatch_profile)
    activate_profile("plain-channel", plain_profile)

    assert set(service.get_profile_features("league-channel")) == {ProfileFeatureName.LEAGUE}
    assert set(service.get_profile_features("overwatch-channel")) == {ProfileFeatureName.OVERWATCH}
    assert service.get_profile_features("plain-channel") == {}


@pytest.mark.asyncio
async def test_profile_feature_override_persists_and_cannot_enable_unconfigured_integration(tmp_path) -> None:
    database_path = tmp_path / "features.db"
    profile = ChannelProfile(channel_name="league", league=LeagueConfig(enabled=True))
    activate_profile("channel-1", profile)

    async with asqlite.create_pool(str(database_path)) as database:
        service = FeatureToggleService(database)
        await service.setup()
        disabled = await service.set_profile_feature_enabled("channel-1", ProfileFeatureName.LEAGUE, False, "test")

        assert disabled.effective_enabled is False

    async with asqlite.create_pool(str(database_path)) as database:
        reloaded = FeatureToggleService(database)
        await reloaded.setup()

        assert reloaded.is_profile_feature_enabled("channel-1", ProfileFeatureName.LEAGUE) is False

        clear_profiles()
        activate_profile("channel-1", ChannelProfile(channel_name="plain"))
        unavailable = await reloaded.set_profile_feature_enabled("channel-1", ProfileFeatureName.OVERWATCH, True, "test")

        assert unavailable.effective_enabled is False
        assert reloaded.get_profile_features("channel-1") == {}
