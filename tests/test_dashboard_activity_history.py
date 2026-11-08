from datetime import UTC, datetime
from types import SimpleNamespace

import asqlite
import pytest
from unittest.mock import Mock

from bot.services.channels.live_chat import LiveChatService, UnifiedChatMessage
from storage.migration_runner import run_migrations


@pytest.mark.asyncio
async def test_commands_and_moderation_restore_without_busy_chat_or_cross_channel_leaks(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'activity.db')) as db:
        await run_migrations(db)
        service = LiveChatService(db)
        await service.setup()
        command = UnifiedChatMessage(id='command', platform='twitch', kind='command', username='viewer',
                                     display_name='Viewer', message='!points', timestamp=datetime.now(UTC).isoformat())
        service.publish('1', command)
        for index in range(300):
            service.publish('1', UnifiedChatMessage(id=str(index), platform='twitch', kind='chat', username='viewer',
                display_name='Viewer', message='hello', timestamp=command.timestamp))
        service.record_mod_action(SimpleNamespace(broadcaster=SimpleNamespace(id='1'), action='clear', moderator=None))
        await service.activity_history.flush()
        assert service.history('1', 'commands')[0]['message'] == '!points'
        restored = LiveChatService(db)
        await restored.setup()
        assert restored.history('1', 'commands') == service.history('1', 'commands')
        assert restored.publish('1', command) is False
        assert restored.get_moderation_activity('1')['mod_actions'] == service.get_moderation_activity('1')['mod_actions']
        assert restored.history('2', 'commands') == []
        assert restored.get_moderation_activity('2')['mod_actions'] == []
        await restored.remove_message('1', 'command')
        await restored.activity_history.flush()
        changed = restored.activity_history.changed = Mock(wraps=restored.activity_history.changed)
        await restored.remove_message('1', 'ordinary-chat')
        restored.clear_chat('1')
        changed.assert_not_called()
        again = LiveChatService(db)
        await again.setup()
        assert again.history('1', 'commands') == []


@pytest.mark.asyncio
async def test_activity_history_is_bounded_and_explicit_clear_is_persisted(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'bounded.db')) as db:
        await run_migrations(db)
        service = LiveChatService(db)
        await service.setup()
        for index in range(110):
            service.publish('1', UnifiedChatMessage(id=str(index), platform='twitch', kind='command', username='viewer',
                display_name='Viewer', message='!points', timestamp=datetime.now(UTC).isoformat()))
        assert len(service.history('1', 'commands')) == 100
        assert service.history('1', 'commands')[0]['id'] == '10'
        service.clear_chat('1')
        await service.activity_history.flush()
        restored = LiveChatService(db)
        await restored.setup()
        assert restored.history('1', 'commands') == []
