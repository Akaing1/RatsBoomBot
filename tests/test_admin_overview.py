import importlib
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asqlite
import pytest
from starlette.requests import Request
from starlette.datastructures import URLPath

from bot.services.channels.broadcaster import Broadcaster
overview = importlib.import_module("web.admin.routers.dashboard")


@pytest.mark.parametrize('present,expected,connections,status', [
    (False, 0, [], 'Unavailable'),
    (True, 0, [], 'Starting'),
    (True, 2, [False, False], 'Disconnected'),
    (True, 2, [True, False], 'Degraded'),
    (True, 2, [True, True], 'Connected'),
])
def test_connection_status_uses_actual_shards(present, expected, connections, status):
    bot = SimpleNamespace(conduit_info=SimpleNamespace(
        shard_count=expected,
        websockets={i: SimpleNamespace(connected=value) for i, value in enumerate(connections)},
    )) if present else None
    assert overview.twitch_connection_status(bot) == (status, sum(connections), expected)


@pytest.mark.asyncio
async def test_database_check_queries_pool_and_handles_failures():
    assert not await overview.database_is_responsive(None)
    async with asqlite.create_pool(':memory:') as pool:
        assert await overview.database_is_responsive(pool)

    class BrokenPool:
        @asynccontextmanager
        async def acquire(self):
            raise RuntimeError('closed')
            yield

    assert not await overview.database_is_responsive(BrokenPool())


@pytest.mark.asyncio
async def test_database_check_bounds_pool_acquisition(monkeypatch):
    import asyncio
    original_timeout = asyncio.timeout
    monkeypatch.setattr(overview.asyncio, 'timeout', lambda _: original_timeout(0.01))

    class BusyPool:
        @asynccontextmanager
        async def acquire(self):
            await asyncio.Event().wait()
            yield

    assert not await overview.database_is_responsive(BusyPool())


def request():
    scope = {'type': 'http', 'method': 'GET', 'path': '/admin', 'headers': [],
             'query_string': b'', 'scheme': 'http', 'server': ('test', 80), 'session': {}}
    result = Request(scope)
    result.scope['router'] = SimpleNamespace(url_path_for=lambda name, path: URLPath('/' + name + path))
    return result


@pytest.mark.asyncio
async def test_overview_renders_cached_channels_live_first_and_escapes_names(monkeypatch):
    refresh = AsyncMock()
    channels = SimpleNamespace(
        get_broadcasters=lambda: {'1': Broadcaster('1', display_name='<script>'),
                                  '2': Broadcaster('2', display_name='Live channel', is_live=True)},
        refresh_live_statuses=refresh,
    )
    bot = SimpleNamespace(services=SimpleNamespace(broadcasters=channels), conduit_info=SimpleNamespace(
        shard_count=1, websockets={0: SimpleNamespace(connected=True)},
    ))
    monkeypatch.setattr(overview, 'require_admin', AsyncMock(return_value=None))
    monkeypatch.setattr(overview, 'get_bot', lambda: bot)
    monkeypatch.setattr(overview, 'get_db', lambda: None)
    response = await overview.dashboard(request())
    html = response.body.decode()
    assert response.context['live_count'] == 1
    assert [c.id for c in response.context['broadcasters']] == ['2', '1']
    assert '&lt;script&gt;' in html
    assert 'Runtime needs attention' in html
    refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_runtime_is_not_shown_as_no_channels(monkeypatch):
    monkeypatch.setattr(overview, 'require_admin', AsyncMock(return_value=None))
    monkeypatch.setattr(overview, 'get_bot', lambda: None)
    monkeypatch.setattr(overview, 'get_db', lambda: None)
    response = await overview.dashboard(request())
    html = response.body.decode()
    assert 'Channel activity unavailable' in html
    assert 'No channels connected' not in html


@pytest.mark.asyncio
async def test_unauthenticated_request_does_not_probe_runtime(monkeypatch):
    redirect = object()
    monkeypatch.setattr(overview, 'require_admin', AsyncMock(return_value=redirect))
    monkeypatch.setattr(overview, 'get_bot', lambda: pytest.fail('read before auth'))
    monkeypatch.setattr(overview, 'get_db', lambda: pytest.fail('read before auth'))
    assert await overview.dashboard(request()) is redirect
