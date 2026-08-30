from types import SimpleNamespace

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


def test_database_integration_details_do_not_grant_capability() -> None:
    base_profile = ChannelProfile(channel_name="generic")
    effective_profile = ChannelProfile(channel_name="generic", overwatch=OverwatchConfig(player_id="Player#123"))
    profile_settings = SimpleNamespace(base_profiles={"channel-1": base_profile})
    activate_profile("channel-1", effective_profile)
    service = FeatureToggleService(db=None, profile_settings=profile_settings)

    assert service.get_profile_feature_state("channel-1", ProfileFeatureName.OVERWATCH).available is False


@pytest.mark.asyncio
async def test_admin_can_grant_and_revoke_profile_feature_availability(tmp_path) -> None:
    database_path = tmp_path / "features.db"
    activate_profile("channel-1", ChannelProfile(channel_name="plain"))

    async with asqlite.create_pool(str(database_path)) as database:
        service = FeatureToggleService(database)
        await service.setup()

        granted = await service.set_profile_feature_available("channel-1", ProfileFeatureName.LEAGUE, True, "admin")
        assert granted.available is True
        assert set(service.get_profile_features("channel-1")) == {ProfileFeatureName.LEAGUE}

        enabled = await service.set_profile_feature_enabled("channel-1", ProfileFeatureName.LEAGUE, True, "streamer")
        assert enabled.effective_enabled is True

        revoked = await service.set_profile_feature_available("channel-1", ProfileFeatureName.LEAGUE, False, "admin")
        assert revoked.available is False
        assert revoked.effective_enabled is False
        assert service.get_profile_features("channel-1") == {}


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
        with pytest.raises(ValueError, match="not been granted"):
            await reloaded.set_profile_feature_enabled("channel-1", ProfileFeatureName.OVERWATCH, True, "test")

        assert reloaded.get_profile_features("channel-1") == {}
