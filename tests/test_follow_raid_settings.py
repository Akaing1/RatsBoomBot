import asqlite
import pytest

from bot.services.channels.broadcaster_settings import BroadcasterSettingsService
from storage.migrations.core.v067_follow_raid import migrate


@pytest.mark.asyncio
async def test_follow_raid_migration_preserves_settings_and_can_be_run_twice(tmp_path):
    async with asqlite.create_pool(str(tmp_path / "settings.db")) as db:
        async with db.acquire() as connection:
            await connection.execute("""CREATE TABLE broadcaster_settings (broadcaster_id TEXT PRIMARY KEY,
                discord_url TEXT, youtube_url TEXT, timers_enabled INTEGER NOT NULL DEFAULT 1)""")
            await connection.execute("INSERT INTO broadcaster_settings (broadcaster_id, discord_url) VALUES ('1', 'existing')")
            await migrate(connection)
            await migrate(connection)
        service = BroadcasterSettingsService(db)
        settings = await service.get_settings("1")
        assert settings.follow_raid is True and settings.discord_url == "existing"
        await service.set_follow_raid("1", False)
        assert (await service.get_settings("1")).follow_raid is False
        assert (await service.get_settings("2")).follow_raid is True
        await service.set_follow_raid("2", False)
        assert (await service.get_settings("2")).follow_raid is False
        assert (await service.get_settings("1")).discord_url == "existing"
