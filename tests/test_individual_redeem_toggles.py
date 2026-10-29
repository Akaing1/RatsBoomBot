from types import SimpleNamespace

import asqlite
import pytest
from bot.profiles import ChannelProfile, RedeemConfig, FeatureName, activate_profile, clear_profiles
from bot.services.channels.feature_toggle import FeatureToggleService
from bot.services.engagement.redeems import RedeemService


@pytest.mark.asyncio
async def test_redeems_inherit_legacy_state_and_can_be_changed_independently(tmp_path):
    profile = ChannelProfile(channel_name='example', redeems=RedeemConfig(daily_title='Daily', first_title='First', second_title='Second', vip_title='VIP'))
    activate_profile('1', profile)
    try:
        async with asqlite.create_pool(str(tmp_path / 'redeems.db')) as db:
            features = FeatureToggleService(db)
            await features.setup()
            service = RedeemService(SimpleNamespace(services=SimpleNamespace(features=features)), db, None)
            assert service.get_redeem_config('1').daily_title == 'Daily'
            await features.set_enabled('1', FeatureName.REDEEM_DAILY, False, 'owner')
            config = service.get_redeem_config('1')
            assert config.daily_title == ''
            assert config.first_title == 'First'
            assert profile.redeems.daily_title == 'Daily'
            result = await service.handle_redemption(broadcaster_id='1', user_id='2', username='viewer', reward_title='Daily', stream_id='live')
            assert not result.handled
            await features.set_enabled('1', FeatureName.REDEEMS, False, 'owner')
            assert service.get_redeem_config('1').vip_title == ''
            await features.set_enabled('1', FeatureName.REDEEM_VIP, True, 'owner')
            assert service.get_redeem_config('1').vip_title == 'VIP'
            assert service.get_redeem_config('1').first_title == ''
            await features.load_overrides()
            assert service.get_redeem_config('1').vip_title == 'VIP'
            await features.set_enabled('1', FeatureName.CHANNEL, False, 'owner')
            assert service.get_redeem_config('1') is None
    finally:
        clear_profiles()
