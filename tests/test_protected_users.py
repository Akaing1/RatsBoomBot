import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

import web.channel.routers.dashboard as dashboard_router
from bot.profiles import ChannelProfile, activate_profile, clear_profiles
from bot.services.support.moderation import ModerationService
from web.channel.auth import CHANNEL_USER_ID_KEY


@pytest.fixture(autouse=True)
def reset_profiles():
    clear_profiles()
    yield
    clear_profiles()


def channel_request(method: str = "GET") -> Request:
    return Request({
        "type": "http",
        "method": method,
        "path": "/channel/protected-users/search",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "session": {CHANNEL_USER_ID_KEY: "channel-1"}
    })


@pytest.mark.asyncio
async def test_protected_user_search_resolves_twitch_identity(monkeypatch) -> None:
    twitch_user = SimpleNamespace(id="123", name="viewer", display_name="Viewer", profile_image=SimpleNamespace(url="https://example.com/viewer.png"))
    runtime_bot = SimpleNamespace(
        bot_id="bot-id",
        services=SimpleNamespace(),
        fetch_user=AsyncMock(return_value=twitch_user)
    )
    activate_profile("channel-1", ChannelProfile(channel_name="channel"))
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: runtime_bot)

    response = await dashboard_router.search_channel_protected_user(channel_request(), "@Viewer")
    payload = json.loads(response.body)

    assert response.status_code == 200
    assert payload["users"][0] == {
        "id": "123",
        "login": "viewer",
        "display_name": "Viewer",
        "profile_image_url": "https://example.com/viewer.png",
        "already_protected": False,
        "automatic": False,
        "related": False
    }
    runtime_bot.fetch_user.assert_awaited_once_with(login="viewer")


@pytest.mark.asyncio
async def test_protected_user_search_marks_existing_user(monkeypatch) -> None:
    twitch_user = SimpleNamespace(id="123", name="viewer", display_name="Viewer")
    runtime_bot = SimpleNamespace(
        bot_id="bot-id",
        services=SimpleNamespace(),
        fetch_user=AsyncMock(return_value=twitch_user)
    )
    activate_profile("channel-1", ChannelProfile(channel_name="channel", protected_user_ids=("123",)))
    monkeypatch.setattr(dashboard_router, "get_bot", lambda: runtime_bot)

    response = await dashboard_router.search_channel_protected_user(channel_request(), "viewer")
    payload = json.loads(response.body)

    assert payload["users"][0]["already_protected"] is True


def test_automated_moderation_honors_profile_protected_users() -> None:
    activate_profile("channel-1", ChannelProfile(channel_name="channel", protected_user_ids=("protected",)))
    service = ModerationService(SimpleNamespace(bot_id="bot-id"), db=None)

    assert service.is_protected_user("channel-1", "protected") is True
    assert service.is_protected_user("channel-1", "viewer") is False


@pytest.mark.asyncio
async def test_protected_user_rows_include_avatars_in_one_lookup():
    from web.shared.protected_users import get_protected_user_rows
    bot = SimpleNamespace(
        services=SimpleNamespace(profile_settings=SimpleNamespace(
            get_default_protected_user_ids=lambda channel: ('1',),
            get_added_protected_users=lambda channel: (SimpleNamespace(user_id='2', login='viewer', display_name='Viewer'),),
        )),
        fetch_users=AsyncMock(return_value=[
            SimpleNamespace(id='1', name='owner', display_name='Owner', profile_image=SimpleNamespace(url='https://example.com/owner.png')),
            SimpleNamespace(id='2', profile_image=SimpleNamespace(url='https://example.com/viewer.png')),
        ]),
    )
    rows = await get_protected_user_rows(bot, '1')
    bot.fetch_users.assert_awaited_once_with(ids=['1', '2'])
    assert [row['profile_image_url'] for row in rows] == ['https://example.com/owner.png', 'https://example.com/viewer.png']
    bot.fetch_users.side_effect = RuntimeError('Unavailable')
    rows = await get_protected_user_rows(bot, '1')
    viewer = next(row for row in rows if row['user_id'] == '2')
    assert viewer['display_name'] == 'Viewer'
    assert viewer['profile_image_url'] == ''


@pytest.mark.asyncio
async def test_protected_search_ranks_deduplicates_and_limits_fuzzy_matches():
    from web.shared.protected_users import search_protected_users
    queries = []
    def search(query, **kwargs):
        queries.append(query)
        async def results():
            names = ['viewer', 'viewer123', 'viewr', 'viewing', 'viewed', 'viewers', 'viewx']
            for index, name in enumerate(names):
                yield SimpleNamespace(broadcaster=SimpleNamespace(id=str(index + 1), name=name, display_name=name), thumbnail=SimpleNamespace(url='avatar.png'))
        return results()
    bot = SimpleNamespace(bot_id='999', fetch_user=AsyncMock(return_value=SimpleNamespace(id='3', name='viewr', display_name='Viewr')), search_channels=search)
    users = await search_protected_users(bot, '10', 'viewr')
    assert len(users) == 5
    assert users[0]['login'] == 'viewr'
    assert len({user['id'] for user in users}) == 5
    assert queries == ['viewr']
    async def empty_exact(login):
        return None
    bot.fetch_user = empty_exact
    def broad_search(query, **kwargs):
        queries.append(query)
        async def results():
            if query == 'vi':
                yield SimpleNamespace(broadcaster=SimpleNamespace(id='1', name='viewer', display_name='Viewer'), thumbnail=SimpleNamespace(url='avatar.png'))
        return results()
    bot.search_channels = broad_search
    queries.clear()
    users = await search_protected_users(bot, '10', 'viewr')
    assert queries == ['viewr', 'vi']
    assert users[0]['login'] == 'viewer'


@pytest.mark.asyncio
async def test_protected_search_reads_only_existing_channel_relationship_caches():
    import time
    from web.shared.protected_users import search_protected_users
    now = time.monotonic()
    bot = SimpleNamespace(
        bot_id='999', fetch_user=AsyncMock(return_value=None),
        _followers_directory_cache={'10': {'followers': [
            {'user_id': str(index), 'user_login': f'viewer{index}', 'user_name': f'Viewer{index}'} for index in range(1, 5)
        ]}},
        _raid_browser_cache={
            ('10', 'channels/followed', (('user_id', '10'),)): (now, {'data': [{'broadcaster_id': '5', 'broadcaster_login': 'viewer5', 'broadcaster_name': 'Viewer5'}]}),
            ('20', 'channels/followed', (('user_id', '20'),)): (now, {'data': [{'broadcaster_id': '6', 'broadcaster_login': 'viewer6', 'broadcaster_name': 'Viewer6'}]}),
            ('10', 'channels/followed', (('user_id', '10'), ('after', 'old'))): (now - 86401, {'data': [{'broadcaster_id': '7', 'broadcaster_login': 'viewer7', 'broadcaster_name': 'Viewer7'}]}),
        },
        _raid_browser_profile_cache={('10', '1'): (now, {'profile_image_url': 'cached.png'})},
        search_channels=lambda *args, **kwargs: pytest.fail('Cached-only matching must not request Twitch search'),
    )
    bootstrap = await search_protected_users(bot, '10', '', cached_only=True)
    assert len(bootstrap) == 5
    first_character = await search_protected_users(bot, '10', 'v', cached_only=True)
    assert len(first_character) == 5
    users = await search_protected_users(bot, '10', 'viewer', cached_only=True)
    assert {user['id'] for user in users} == {'1', '2', '3', '4', '5'}
    assert next(user for user in users if user['id'] == '1')['profile_image_url'] == 'cached.png'
    assert len(bot._followers_directory_cache) == 1
    assert len(bot._raid_browser_cache) == 3
    bot.fetch_user.assert_not_awaited()
    async def empty_search():
        if False:
            yield
    bot.search_channels = lambda *args, **kwargs: empty_search()
    combined = await search_protected_users(bot, '10', 'viewer')
    assert {user['id'] for user in combined} == {'1', '2', '3', '4', '5'}
    bot.fetch_user.assert_awaited_once_with(login='viewer')


@pytest.mark.asyncio
async def test_queue_blacklist_rows_include_profiles_and_reuse_daily_lookup():
    bot = SimpleNamespace(services=SimpleNamespace(viewer_queue=SimpleNamespace(list_blacklist=lambda channel: ['viewer'])),
        _http=SimpleNamespace(request_json=AsyncMock(return_value={'data': [
            {'id': '123', 'login': 'viewer', 'display_name': 'Display Name', 'profile_image_url': 'avatar.png'},
        ]})))
    first = await dashboard_router.get_queue_blacklist_rows(bot, '1')
    assert first == [{'username': 'viewer', 'display_name': 'Display Name', 'user_id': '123', 'profile_image_url': 'avatar.png'}]
    assert await dashboard_router.get_queue_blacklist_rows(bot, '1') == first
    bot._http.request_json.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('known_count,strong', [(5, False), (3, False), (5, True)])
async def test_user_search_prioritizes_exact_matches_then_relationships(known_count, strong):
    from web.shared.protected_users import search_protected_users
    async def search_results():
        names = [('remote1', 'viewername_other'), ('remote2', 'viewername_extra')]
        if strong:
            names.append(('near', 'viewernamf'))
        for id_, name in names:
            yield SimpleNamespace(broadcaster=SimpleNamespace(id=id_, name=name, display_name=name), thumbnail=SimpleNamespace(url='avatar.png'))
    bot = SimpleNamespace(bot_id='999', _follower_names_cache={'10': {'users': {
        str(index): {'user_id': str(index), 'user_login': f'viewername_friend{index}', 'user_name': f'Viewername_friend{index}'} for index in range(known_count)
    }}}, fetch_user=AsyncMock(return_value=SimpleNamespace(id='exact', name='viewername', display_name='Viewername') if strong else None),
        search_channels=lambda *args, **kwargs: search_results())
    users = await search_protected_users(bot, '10', 'viewername')
    assert len(users) == known_count + (4 if strong else 2)
    assert all(user['related'] for user in users[:known_count])
    assert all(not user['related'] for user in users[known_count:])
    ids = [user['id'] for user in users]
    if strong:
        assert ids[known_count] == 'exact'
        assert set(ids[known_count:]) == {'exact', 'near', 'remote1', 'remote2'}
    else:
        assert set(ids[known_count:]) == {'remote1', 'remote2'}


@pytest.mark.asyncio
async def test_profile_image_lookup_is_batched_and_cached_for_a_day():
    from web.shared.protected_users import user_profile_images
    bot = SimpleNamespace(_http=SimpleNamespace(request_json=AsyncMock(return_value={'data': [
        {'id': '123', 'login': 'viewer', 'display_name': 'Viewer', 'profile_image_url': 'avatar.png'},
    ]})))
    first = await user_profile_images(bot, '1', '123,123', dashboard_router.raid_browser_profiles)
    assert first == {'profiles': [{'id': '123', 'profile_image_url': 'avatar.png'}]}
    assert await user_profile_images(bot, '1', '123', dashboard_router.raid_browser_profiles) == first
    bot._http.request_json.assert_awaited_once()
    from web.shared.protected_users import ProtectedUserError
    with pytest.raises(ProtectedUserError):
        await user_profile_images(bot, '1', 'invalid', dashboard_router.raid_browser_profiles)
