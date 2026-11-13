from datetime import UTC, datetime
from types import SimpleNamespace

import asqlite
import pytest

from bot.services.support.moderation_shadow import ModerationShadow
from storage.migrations.core.v083_moderation_shadow import migrate


def message(user, text, timestamp, ident):
    return SimpleNamespace(broadcaster=SimpleNamespace(id='c'),
        chatter=SimpleNamespace(id=user, name=user), text=text,
        timestamp=datetime.fromtimestamp(timestamp, UTC), id=ident)


@pytest.mark.asyncio
async def test_bans_survive_without_chat_and_correlate_only_preban_in_grace(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr('bot.services.support.moderation_shadow.time.time', lambda: clock[0])
    async with asqlite.create_pool(str(tmp_path/'shadow.db')) as db:
        async with db.acquire() as c:
            await migrate(c)
        shadow = ModerationShadow(db)
        ban = dict(broadcaster_id='c', user_id='u', username='u', moderator_id='s',
            moderator_name='sery', reason='Spam', source='serybot', banned_at=datetime.fromtimestamp(1000, UTC))
        assert await shadow.ban(**ban)
        assert not await shadow.ban(**ban)
        assert (await shadow.dashboard())['bans'][0]['matches'] == 0
        clock[0] = 1005
        await shadow.message(message('u', 'hello', 999, 'a'), 'hello', False, False)
        await shadow.message(message('u', 'after ban', 1001, 'b'), 'after', False, False)
        await shadow.message(message('other', 'wrong user', 999, 'c'), 'other', False, False)
        clock[0] = 1011
        await shadow.message(message('u', 'too late', 998, 'd'), 'late', False, False)
        data = await shadow.dashboard()
        assert data['bans'][0]['matches'] == 1
        assert data['bans'][0]['outcome'] == 'Detection gap'
        assert data['patterns'][0]['example'] == 'hello'
        # Evidence remains after service restart and transient chat expiration.
        shadow = ModerationShadow(db)
        clock[0] = 1400
        await shadow.message(message('new', 'normal', 1400, 'e'), 'normal', False, False)
        assert (await shadow.dashboard())['bans'][0]['messages'] == 'hello'


@pytest.mark.asyncio
async def test_multiple_candidates_agreement_and_bounded_history(tmp_path, monkeypatch):
    monkeypatch.setattr('bot.services.support.moderation_shadow.time.time', lambda: 1000.0)
    async with asqlite.create_pool(str(tmp_path/'shadow.db')) as db:
        async with db.acquire() as c:
            await migrate(c)
        shadow = ModerationShadow(db)
        for i in range(15):
            await shadow.message(message('u', str(i), 990+i/10, str(i)), str(i), False, False)
        async with db.acquire() as c:
            assert (await c.fetchone('SELECT COUNT(*) AS n FROM moderation_shadow_messages'))['n'] == 10
        await shadow.message(message('u', 'flag', 999, 'flag'), 'flag', True, False)
        assert len((await shadow.dashboard())['flags']) == 1
        await shadow.ban(broadcaster_id='c', user_id='u', username='u', moderator_id='s',
            moderator_name='sery', reason=None, source='serybot', banned_at=datetime.fromtimestamp(1000, UTC))
        monkeypatch.setattr('bot.services.support.moderation_shadow.time.time', lambda: 1011.0)
        data = await shadow.dashboard()
        assert data['bans'][0]['match_status'] == 'Multiple candidates'
        assert data['bans'][0]['outcome'] == 'Agreement'
        assert data['flags'] == []


@pytest.mark.asyncio
async def test_confirmed_campaign_is_silent_and_hello_ban_creates_no_campaign(tmp_path):
    from bot.services.support.moderation import ModerationService
    async with asqlite.create_pool(str(tmp_path/'service.db')) as db:
        async with db.acquire() as c:
            await migrate(c)
        service = ModerationService(SimpleNamespace(bot_id='bot'), db)
        await service.setup()
        payload = message('u', 'hello', 1000, 'hello')
        fingerprint = service.create_fingerprint('hello')
        await service.upsert_campaign(fingerprint, 'hello', 'hello', 'serybot', 'Legacy')
        await service.confirm_campaign(fingerprint)
        result = await service.evaluate_message(payload)
        assert result.should_allow
        assert not result.should_ban
        assert len((await service.shadow.dashboard())['flags']) == 1
        await service.observe_external_ban(broadcaster_id='c', user_id='other', username='other',
            moderator_id='s', moderator_name='sery', reason=None, source='serybot')
        async with db.acquire() as c:
            assert (await c.fetchone('SELECT COUNT(*) AS n FROM moderation_campaigns'))['n'] == 1


@pytest.mark.asyncio
async def test_dashboard_requires_admin(monkeypatch):
    from unittest.mock import AsyncMock
    from web.admin.routers import bot_detection as module
    from fastapi.responses import RedirectResponse
    redirect = RedirectResponse('/admin/login')
    monkeypatch.setattr(module, 'require_admin', AsyncMock(return_value=redirect))
    monkeypatch.setattr(module, 'get_db', lambda: (_ for _ in ()).throw(AssertionError('must not read data')))
    assert await module.bot_detection(SimpleNamespace()) is redirect
