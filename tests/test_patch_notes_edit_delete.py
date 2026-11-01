import importlib
from unittest.mock import AsyncMock

import asqlite
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from storage.migrations.core.v021_patch_notes import migrate
from storage.patch_notes_repository import create_note, get_note, update_note, delete_note, publish_note

routes = importlib.import_module('web.admin.routers.patch_notes')


@pytest.mark.asyncio
async def test_edit_preserves_publication_metadata_and_duplicate_create_does_not_overwrite():
    async with asqlite.create_pool(':memory:') as db:
        async with db.acquire() as connection:
            await migrate(connection)
            await connection.commit()
        assert await create_note(db, 'original', 'Original', 'Summary', 'Body')
        await publish_note(db, 'original', '17.0.0')
        before = dict(await get_note(db, 'original'))
        assert await update_note(db, 'original', 'Renamed', 'New summary', 'New body')
        after = dict(await get_note(db, 'original'))
        for field in ['slug', 'version', 'published_at', 'discord_announced_at', 'created_at']:
            assert after[field] == before[field]
        assert after['title'] == 'Renamed'
        assert not await create_note(db, 'original', 'Overwrite', 'bad', 'bad')
        assert (await get_note(db, 'original'))['title'] == 'Renamed'
        assert await delete_note(db, 'original')
        assert await get_note(db, 'original') is None
        assert not await delete_note(db, 'original')
        assert not await update_note(db, 'original', 'a', 'b', 'c')


def request():
    return Request({'type': 'http', 'headers': [], 'session': {'csrf_token': 'expected'}})


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['edit', 'delete'])
async def test_mutations_require_authentication_and_csrf(monkeypatch, action):
    handler = routes.edit_note if action == 'edit' else routes.remove_note
    values = dict(title='Title', synopsis='Summary', body='Body') if action == 'edit' else {}
    redirect = object()
    monkeypatch.setattr(routes, 'require_admin', AsyncMock(return_value=redirect))
    monkeypatch.setattr(routes, 'database', lambda: pytest.fail('unauthorized storage access'))
    assert await handler(request(), 'slug', csrf_token='bad', **values) is redirect
    monkeypatch.setattr(routes, 'require_admin', AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as error:
        await handler(request(), 'slug', csrf_token='bad', **values)
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_edit_does_not_publish_or_announce(monkeypatch):
    monkeypatch.setattr(routes, 'require_admin', AsyncMock(return_value=None))
    monkeypatch.setattr(routes, 'database', lambda: object())
    update = AsyncMock(return_value=True)
    monkeypatch.setattr(routes, 'update_note', update)
    monkeypatch.setattr(routes, 'publish_note', AsyncMock(side_effect=AssertionError('republished')))
    monkeypatch.setattr(routes.httpx, 'AsyncClient', lambda: pytest.fail('announcement attempted'))
    result = await routes.edit_note(request(), 'stable-slug', 'expected', ' New title ', ' Summary ', ' Body ')
    assert result.status_code == 303
    assert update.call_args.args[1:] == ('stable-slug', 'New title', 'Summary', 'Body')
