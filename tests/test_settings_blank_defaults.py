from types import SimpleNamespace
import asqlite
import pytest
from unittest.mock import AsyncMock
from starlette.requests import Request
from bot.profiles import ChannelProfile, CommunityMessages, FeatureName, activate_profile, clear_profiles, get_active_profile
from bot.services.channels.profile_settings import ProfileSettingsService
from bot.services.channels.feature_toggle import FeatureToggleService
from web.channel.routers import dashboard


@pytest.mark.asyncio
async def test_blank_restores_channel_default_and_disabling_keeps_text(tmp_path, monkeypatch):
    profile = ChannelProfile(channel_name='example', community_messages=CommunityMessages(follow='Channel default'))
    activate_profile('1', profile)
    try:
        async with asqlite.create_pool(str(tmp_path / 'settings.db')) as db:
            service = ProfileSettingsService(db)
            await service.setup()
            service.apply_overrides('1', profile)
            features = FeatureToggleService(db)
            await features.setup()
            monkeypatch.setattr(dashboard, 'get_bot', lambda: SimpleNamespace(services=SimpleNamespace(profile_settings=service, features=features, broadcaster_settings=SimpleNamespace(set_timers_enabled=AsyncMock()))))
            request = Request({'type':'http','headers':[],'path':'/channel/customization','session':{'channel_user_id':'1','csrf_token':'test'}})
            await dashboard.update_channel_customization(request, 'community_messages.follow', 'Custom hello', 'save', 'test')
            assert get_active_profile('1').community_messages.follow == 'Custom hello'
            await features.set_enabled('1', FeatureName.FOLLOW_RESPONSES, False, 'test')
            assert service.get_setting_state('1', 'community_messages.follow').override_value == 'Custom hello'
            await features.set_enabled('1', FeatureName.FOLLOW_RESPONSES, True, 'test')
            assert get_active_profile('1').community_messages.follow == 'Custom hello'
            result = await dashboard.update_channel_customization(request, 'community_messages.follow', '  ', 'save', 'test')
            assert 'setting_result=success' in result.headers['location']
            assert get_active_profile('1').community_messages.follow == 'Channel default'
            assert service.get_setting_state('1', 'community_messages.follow').override_value is None
            await dashboard.update_channel_customization(request, 'timer_messages', '', 'save', 'test')
            assert service.get_setting_state('1', 'timer_messages').override_value == ''
            # Empty boss names also restore defaults rather than failing validation.
            await service.set_override('1', 'raid_bosses.names.melee', 'Custom Boss', 'test')
            await dashboard.update_channel_customization(request, 'raid_bosses.names.melee', '', 'save', 'test')
            assert service.get_setting_state('1', 'raid_bosses.names.melee').override_value is None
    finally:
        clear_profiles()
