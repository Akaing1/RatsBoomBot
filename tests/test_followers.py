import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import asqlite
import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from storage.migration_runner import run_migrations
from storage.followers import follower_metrics
from web.channel.routers import followers


@pytest.fixture
async def directory(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / 'followers.db')) as db:
        await run_migrations(db)
        session = {'channel_user_id': '1', 'csrf_token': 'secret'}
        calls = []
        people = [dict(user_id=str(i), user_login=f'user{i:03}', user_name=f'User{i:03}',
            followed_at=f'2026-10-{1 + i % 20:02}T00:00:00Z') for i in range(1, 129)]
        async def twitch(route):
            calls.append(route)
            if route.path == 'channels/followers':
                after = route.params.get('after')
                return {'data': people[100:] if after else people[:100], 'total': 128,
                    'pagination': {} if after else {'cursor': 'next'}}
            entries = {'channels/followed': [{'broadcaster_id': '2'}, {'broadcaster_id': '3'}], 'moderation/moderators': [{'user_id': '1'}, {'user_id': '2'}],
                'channels/vips': [{'user_id': '3'}], 'subscriptions': [{'user_id': '2', 'tier': '2000'}]}
            return {'data': entries[route.path], 'pagination': {}}
        history = [dict(platform='twitch', user_id='1', badges=[{'name': 'lead_moderator'}])]
        bot = SimpleNamespace(_http=SimpleNamespace(request_json=AsyncMock(side_effect=twitch)),
            services=SimpleNamespace(broadcasters=SimpleNamespace(get_broadcasters=lambda: {'1': SimpleNamespace(name='Alice'), 'other': SimpleNamespace(name='Other')}),
                live_chat=SimpleNamespace(history=lambda channel: history if channel == '1' else [])))
        monkeypatch.setattr(followers, 'get_bot', lambda: bot)
        monkeypatch.setattr(followers, 'get_db', lambda: db)
        async with db.acquire() as connection:
            await connection.execute("INSERT INTO viewers VALUES ('1','2','user002',500,0)")
            await connection.execute("INSERT INTO viewers VALUES ('other','2','user002',99999,0)")
            await connection.execute("INSERT INTO viewers VALUES ('1','999','not-a-follower',999999,0)")
            await connection.execute("INSERT INTO chatter_channel_stats VALUES ('1','2',42,800,CURRENT_TIMESTAMP)")
        app = FastAPI()
        app.mount('/static', StaticFiles(directory='web/static'), name='static')
        app.mount('/assets', StaticFiles(directory='assets'), name='assets')
        @app.middleware('http')
        async def add_session(request, call_next):
            request.scope['session'] = session.copy()
            return await call_next(request)
        app.include_router(followers.router)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            yield client, session, db, bot, calls
        for snapshot in getattr(bot, '_followers_directory_cache', {}).values():
            if snapshot.get('task'):
                await snapshot['task']


async def ready(client, bot):
    initial = await client.get('/channel/api/followers')
    assert initial.status_code == 200
    await bot._followers_directory_cache['1']['task']


@pytest.mark.asyncio
async def test_only_followers_channel_points_global_sort_and_no_redundant_twitch_calls(directory):
    client, session, db, bot, calls = directory
    await ready(client, bot)
    response = await client.get('/channel/api/followers?sort=points&page_size=25')
    data = response.json()
    assert response.headers['cache-control'] == 'no-store'
    assert data['total'] == data['count'] == 128 and data['pages'] == 6
    assert data['rows'][0]['user_id'] == '2' and data['rows'][0]['points'] == 500
    assert data['rows'][0]['messages'] == 42 and data['rows'][0]['lifetime_points'] == 800
    assert data['rows'][0]['role_labels'] == ['Mod', 'Sub tier 2', 'Mutual']
    assert all(row['user_id'] != '999' for row in data['rows'])
    assert len(calls) == 6
    for size in [10, 25, 50, 100]:
        result = (await client.get(f'/channel/api/followers?sort=name&direction=asc&page_size={size}')).json()
        assert len(result['rows']) == size and result['rows'][0]['name'] == 'User001'
    final = (await client.get('/channel/api/followers?page=999')).json()
    assert final['page'] == final['pages'] == 6 and len(final['rows']) == 3
    assert len(calls) == 6
    assert all(call.token_for == '1' and call.params.get('user_id' if call.path == 'channels/followed' else 'broadcaster_id') == '1' for call in calls)


@pytest.mark.asyncio
@pytest.mark.parametrize('rank,ids', [('mod', {'1', '2'}), ('vip', {'3'}), ('subscriber', {'2'}), ('tier2', {'2'}), ('tier1', set()), ('tier3', set()), (['mod', 'vip'], {'1', '2', '3'})])
async def test_rank_filters(directory, rank, ids):
    client, _, _, bot, _ = directory
    await ready(client, bot)
    data = (await client.get('/channel/api/followers', params={'rank': rank})).json()
    assert {row['user_id'] for row in data['rows']} == ids


@pytest.mark.asyncio
async def test_mutual_followers_paginate_following_cache_and_combine_roles(directory, monkeypatch):
    client, _, _, bot, calls = directory
    await ready(client, bot)
    original = bot._http.request_json.side_effect
    async def with_following(route):
        if route.path == 'channels/followed':
            calls.append(route)
            assert route.token_for == '1' and route.params['user_id'] == '1'
            after = route.params.get('after')
            return {'data': [{'broadcaster_id': '3'}] if after else [{'broadcaster_id': '2'}, {'broadcaster_id': '999'}],
                'pagination': {} if after else {'cursor': 'following-next'}}
        return await original(route)
    bot._http.request_json.side_effect = with_following
    parsed_lookup = AsyncMock(wraps=followers.followed_channel_ids)
    monkeypatch.setattr(followers, 'followed_channel_ids', parsed_lookup)
    data = (await client.get('/channel/api/followers?mutual=true')).json()
    assert data['count'] == 2
    assert {row['user_id'] for row in data['rows']} == {'2', '3'}
    assert all('Mutual' in row['role_labels'] for row in data['rows'])
    filtered = (await client.get('/channel/api/followers?mutual=true&rank=vip')).json()
    assert {row['user_id'] for row in filtered['rows']} == {'3'}
    assert len([route for route in calls if route.path == 'channels/followed']) == 2
    assert (await client.get('/channel/api/followers')).json()['count'] == 128
    assert parsed_lookup.await_count == 1


@pytest.mark.asyncio
async def test_mutual_followers_failure_is_not_an_empty_result(directory):
    client, _, _, bot, _ = directory
    await ready(client, bot)
    original = bot._http.request_json.side_effect
    attempts = 0
    async def fail_following(route):
        nonlocal attempts
        if route.path == 'channels/followed':
            attempts += 1
            raise PermissionError('denied')
        return await original(route)
    bot._http.request_json.side_effect = fail_following
    response = await client.get('/channel/api/followers?mutual=true')
    assert response.status_code == 503
    assert 'Mutual followers' in response.json()['detail']
    assert (await client.get('/channel/api/followers')).status_code == 200
    assert attempts == 1, 'Repeated requests back off instead of repeating a failed Twitch lookup'


@pytest.mark.asyncio
async def test_followers_publish_before_remaining_pages_and_slow_roles(directory):
    client, _, _, bot, _ = directory
    original = bot._http.request_json.side_effect
    first_page_ready, remaining_pages, subscriptions = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def slow_twitch(route):
        if route.path == 'channels/followers' and route.params.get('after'):
            first_page_ready.set()
            await remaining_pages.wait()
        if route.path == 'subscriptions':
            await subscriptions.wait()
        return await original(route)
    bot._http.request_json.side_effect = slow_twitch
    try:
        await client.get('/channel/api/followers')
        await asyncio.wait_for(first_page_ready.wait(), 2)
        snapshot = bot._followers_directory_cache['1']
        early = (await client.get('/channel/api/followers')).json()
        assert early['loading'] is True and early['loaded'] == 100 and early['count'] == 100
        assert early['total'] == 128 and early['rows']
        assert (await client.get('/channel/api/followers/profiles?ids=999')).status_code == 403
        remaining_pages.set()
        for _ in range(100):
            if len(snapshot['followers']) == 128:
                break
            await asyncio.sleep(0)
        partial = (await client.get('/channel/api/followers')).json()
        assert partial['count'] == 128 and partial['loading'] is True
        subscriptions.set()
        await snapshot['task']
        final = (await client.get('/channel/api/followers?search=user002')).json()
        assert final['loading'] is False and 'Sub tier 2' in final['rows'][0]['role_labels']
    finally:
        remaining_pages.set(); subscriptions.set()


@pytest.mark.asyncio
@pytest.mark.parametrize('uptime', [10.0, 1234.0, 1_000_000.0])
async def test_pages_reuse_sorted_rows_until_statistics_change(directory, monkeypatch, uptime):
    client, _, db, bot, _ = directory
    # Freeze the clock before creating cache timestamps, regardless of host uptime.
    monkeypatch.setattr(followers, 'time', SimpleNamespace(monotonic=lambda: uptime))
    await ready(client, bot)
    builder = Mock(wraps=followers.build_table_rows)
    monkeypatch.setattr(followers, 'build_table_rows', builder)
    initial = await client.get('/channel/api/followers?sort=points')
    assert initial.json()['rows'][0]['points'] == 500
    await client.get('/channel/api/followers?sort=points&page=2')
    await client.get('/channel/api/followers?sort=points&page_size=10')
    assert builder.call_count == 1
    async with db.acquire() as connection:
        await connection.execute("UPDATE viewers SET points=600 WHERE broadcaster_id='1' AND user_id='2'")
    bot._followers_directory_cache['1']['metrics_at'] = 0
    assert (await follower_metrics(db, '1', ['2']))['2']['points'] == 600
    response = await client.get('/channel/api/followers?sort=points')
    assert response.json()['rows'][0]['points'] == 600
    assert builder.call_count == 2
    for search in ('user1', 'user2', 'user3', 'user4', 'user5'):
        await client.get('/channel/api/followers', params={'search': search})
    assert len(bot._followers_directory_cache['1']['table_results']) <= 4


@pytest.mark.asyncio
async def test_raid_favorites_filter_and_sort_only_verified_followers(directory):
    client, _, _, bot, _ = directory
    await ready(client, bot)
    data = (await client.get('/channel/api/followers?favorites=2,999&raid_favorites=true')).json()
    assert data['count'] == 1 and data['rows'][0]['user_id'] == '2'
    assert data['rows'][0]['raid_favorite'] is True
    data = (await client.get('/channel/api/followers?favorites=3&sort=raid_favorite')).json()
    assert data['rows'][0]['user_id'] == '3'
    assert (await client.get('/channel/api/followers?raid_favorites=true')).json()['count'] == 0
    assert (await client.get('/channel/api/followers?favorites=bad')).status_code == 400
    assert (await client.get('/channel/api/followers', params={'favorites': ','.join(str(i) for i in range(101))})).status_code == 400


def test_role_sort_prioritizes_count_then_role_hierarchy():
    expected = ['multi', 'submod', 'vipmutual', 'vip3', 'moderator', 'vip', 'mutual', 'tier3', 'tier2', 'tier1', 'none']
    people = [dict(user_id=name, user_login=name, user_name=name) for name in reversed(expected)]
    roles = {'mod': {name: {} for name in ('multi', 'submod', 'moderator')},
        'vip': {name: {} for name in ('multi', 'vipmutual', 'vip3', 'vip')},
        'subscriber': {name: {'tier': tier} for name, tier in [('submod', '1000'), ('vip3', '3000'), ('tier3', '3000'), ('tier2', '2000'), ('tier1', '1000')]}}
    for direction, order in [('desc', expected), ('asc', list(reversed(expected)))]:
        rows = followers.build_table_rows(people, {}, roles, {'vipmutual', 'mutual'}, set(), set(), False, False, '', 'roles', direction)
        assert [row['user_id'] for row in rows] == order
        assert len(next(row for row in rows if row['user_id'] == 'tier3')['role_labels']) == 1


@pytest.mark.asyncio
async def test_auth_input_validation_and_search(directory):
    client, session, _, bot, _ = directory
    session.clear()
    assert (await client.get('/channel/api/followers')).status_code == 401
    assert (await client.get('/channel/followers')).status_code == 303
    session['channel_user_id'] = '1'
    await ready(client, bot)
    for query in ['page_size=11', 'sort=drop%20table', 'direction=bad', 'rank=owner']:
        assert (await client.get('/channel/api/followers?' + query)).status_code == 400
    assert (await client.get('/channel/api/followers?page=0')).status_code == 422
    result = (await client.get('/channel/api/followers?search=USER002')).json()
    assert result['count'] == 1 and result['rows'][0]['user_id'] == '2'
    session['channel_user_id'] = 'missing'
    assert (await client.get('/channel/api/followers')).status_code == 404


@pytest.mark.asyncio
async def test_followers_page_has_navigation_and_assets(directory):
    client, *_ = directory
    response = await client.get('/channel/followers')
    assert response.status_code == 200
    assert '<h2>Followers</h2>' in response.text
    assert 'href="/channel/followers"' in response.text
    assert 'channel-followers.css' in response.text and 'channel-followers.js' in response.text


@pytest.mark.asyncio
async def test_client_cannot_override_signed_in_channel(directory):
    client, session, _, bot, calls = directory
    await ready(client, bot)
    result = (await client.get('/channel/api/followers?sort=points&broadcaster_id=other')).json()
    assert result['rows'][0]['points'] == 500
    session['channel_user_id'] = 'other'
    await client.get('/channel/api/followers')
    await bot._followers_directory_cache['other']['task']
    other = (await client.get('/channel/api/followers?sort=points&broadcaster_id=1')).json()
    assert other['rows'][0]['points'] == 99999
    assert bot._followers_directory_cache['1'] is not bot._followers_directory_cache['other']


@pytest.mark.asyncio
async def test_role_failures_are_not_silently_filtered_as_empty(directory):
    client, _, _, bot, _ = directory
    original = bot._http.request_json.side_effect
    async def fail_subscriptions(route):
        if route.path == 'subscriptions':
            raise PermissionError('denied')
        return await original(route)
    bot._http.request_json.side_effect = fail_subscriptions
    await ready(client, bot)
    data = (await client.get('/channel/api/followers')).json()
    assert data['count'] == 128 and data['warnings']
    assert (await client.get('/channel/api/followers?rank=subscriber')).status_code == 503


@pytest.mark.asyncio
async def test_profile_images_are_followers_only_batched_and_cached(directory):
    client, session, _, bot, calls = directory
    assert (await client.get('/channel/api/followers/profiles?ids=1')).status_code == 403
    await ready(client, bot)
    original = bot._http.request_json.side_effect
    async def with_profiles(route):
        if route.path == 'users':
            calls.append(route)
            return {'data': [{'id': user_id, 'profile_image_url': f'https://static-cdn.jtvnw.net/{user_id}.png'} for user_id in route.params['id'] if user_id != '3']}
        return await original(route)
    bot._http.request_json.side_effect = with_profiles
    for _ in range(2):
        response = await client.get('/channel/api/followers/profiles?ids=1,2,3')
        assert response.status_code == 200
        assert response.json()['profiles'][0]['profile_image_url'].endswith('/1.png')
        assert response.json()['profiles'][2]['profile_image_url'] == ''
    assert len([route for route in calls if route.path == 'users']) == 1
    assert (await client.get('/channel/api/followers/profiles?ids=999')).status_code == 403
    assert (await client.get('/channel/api/followers/profiles?ids=bad')).status_code == 400
    assert (await client.get('/channel/api/followers/profiles?ids=' + ','.join(str(i) for i in range(101)))).status_code == 400
    session['channel_user_id'] = 'other'
    assert (await client.get('/channel/api/followers/profiles?ids=1')).status_code == 403
    session.clear()
    assert (await client.get('/channel/api/followers/profiles?ids=1')).status_code == 401


@pytest.mark.asyncio
async def test_metrics_empty_and_chunked_queries_are_channel_scoped(directory):
    _, _, db, _, _ = directory
    assert await follower_metrics(db, '1', []) == {}
    rows = await follower_metrics(db, '1', [str(i) for i in range(1, 502)])
    assert len(rows) == 501 and rows['2']['points'] == 500 and rows['1']['first_seen'] is None


@pytest.mark.asyncio
async def test_extended_stats_include_imports_and_unique_channel_achievements(directory):
    client, _, db, bot, _ = directory
    async with db.acquire() as connection:
        for channel in ('1', 'other'):
            for kind in ('first', 'daily'):
                await connection.execute('INSERT INTO redeem_claims (broadcaster_id,user_id,username,redeem_type,stream_id) VALUES (?,?,?,?,?)',
                    (channel, '2', 'user002', kind, 'test-stream'))
                await connection.execute('INSERT INTO imported_redeem_totals (broadcaster_id,user_id,username,redeem_type,claim_count) VALUES (?,?,?,?,?)',
                    (channel, '2', 'user002', kind, 3 if kind == 'first' else 5))
        for channel, achievement, tier in [('1', 'familiar', 1), ('1', 'familiar', 2), ('other', 'collector', 1), ('', 'explorer', 1)]:
            await connection.execute('INSERT OR IGNORE INTO achievement_unlocks (user_id,broadcaster_id,achievement_id,tier) VALUES (?,?,?,?)',
                ('2', channel, achievement, tier))
        await connection.execute("INSERT INTO community_achievement_progress VALUES ('1','2','watch_time',125)")
    await ready(client, bot)
    response = await client.get('/channel/api/followers?search=user002')
    row = response.json()['rows'][0]
    assert row['first_redeems'] == 4 and row['check_ins'] == 6
    assert row['achievement_count'] == 1  # Multiple tiers count as one achievement; other channels are excluded.
    assert row['lifetime_points'] == 800 and row['points'] == 3000
    assert row['points_spent'] is None and row['watch_minutes'] == 125
    for sort in ('first_redeems', 'check_ins', 'achievement_count', 'lifetime_points', 'watch_minutes', 'points'):
        sorted_rows = (await client.get('/channel/api/followers', params={'sort': sort})).json()['rows']
        assert sorted_rows[0]['user_id'] == '2'
    assert (await client.get('/channel/api/followers?sort=points_spent')).status_code == 200


@pytest.mark.asyncio
async def test_last_watched_uses_latest_channel_sample_and_sorts_missing_dates_last(directory):
    client, _, db, bot, _ = directory
    async with db.acquire() as connection:
        for channel, user, window in [('1', '2', 1700000000), ('1', '2', 1700010000), ('other', '2', 1900000000), ('1', '7', 1800000000)]:
            await connection.execute('INSERT INTO passive_point_payouts (broadcaster_id,stream_id,interval_started_at,user_id,points) VALUES (?,?,?,?,?)',
                (channel, 'stream', window, user, 2))
    await ready(client, bot)
    data = (await client.get('/channel/api/followers?sort=last_watched')).json()
    assert [row['user_id'] for row in data['rows'][:2]] == ['7', '2']
    assert data['rows'][1]['last_watched'] == '2023-11-15 01:00:00'
    assert data['rows'][2]['last_watched'] is None
    ascending = (await client.get('/channel/api/followers?sort=last_watched&direction=asc')).json()
    assert [row['user_id'] for row in ascending['rows'][:2]] == ['2', '7']


@pytest.mark.asyncio
async def test_repeated_twitch_cursor_and_missing_follower_permission(directory):
    _, _, _, bot, _ = directory
    bot._http.request_json.side_effect = None
    bot._http.request_json.return_value = {'data': [], 'total': 10}
    with pytest.raises(ValueError, match='Reconnect Twitch'):
        await followers.collect(bot, '1', 'channels/followers')
    bot._http.request_json.return_value = {'data': [], 'pagination': {'cursor': 'same'}}
    with pytest.raises(ValueError, match='repeated page'):
        await followers.collect(bot, '1', 'channels/vips')
