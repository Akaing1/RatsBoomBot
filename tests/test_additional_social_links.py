import asqlite
import pytest
from bot.services.channels.broadcaster_settings import BroadcasterSettingsService


@pytest.mark.asyncio
async def test_extra_socials_persist_and_stay_channel_scoped(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'socials.db')) as db:
        service = BroadcasterSettingsService(db)
        await service.setup()
        for platform in ('tiktok', 'x', 'kofi', 'vgen'):
            await service.set_social_url('1', platform, f'https://example.com/{platform}')
            assert getattr(await service.get_settings('1'), f'{platform}_url') == f'https://example.com/{platform}'
            assert getattr(await service.get_settings('2'), f'{platform}_url') is None
        await service.setup()
        assert (await service.get_settings('1')).x_url == 'https://example.com/x'
        await service.set_social_url('1', 'x', '')
        assert (await service.get_settings('1')).x_url is None
        with pytest.raises(ValueError):
            await service.set_social_url('1', 'x', 'javascript:alert(1)')
        with pytest.raises(ValueError):
            await service.set_social_url('1', 'unknown', 'https://example.com')
