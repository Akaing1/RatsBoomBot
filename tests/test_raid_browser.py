import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

from web.channel.auth import CHANNEL_USER_ID_KEY
from web.channel.routers import dashboard


relationship_lookup = dashboard.raid_browser_relationships
dev_lookup = dashboard.raid_browser_dev_streams
collection_lookup = dashboard.raid_browser_collection_visibility


@pytest.fixture(autouse=True)
def isolate_relationship_lookup(monkeypatch):
    monkeypatch.setattr(dashboard, "raid_browser_relationships", AsyncMock(return_value={}))
    monkeypatch.setattr(dashboard, "raid_browser_dev_streams", AsyncMock(return_value=[]))
    monkeypatch.setattr(dashboard, "raid_browser_collection_visibility", AsyncMock(return_value={}))


def request(user="1"):
    return Request({"type": "http", "session": {CHANNEL_USER_ID_KEY: user} if user else {}})


def runtime(monkeypatch, pages, profiles=None):
    monkeypatch.setattr(dashboard, "raid_browser_channel_sizes", AsyncMock(return_value={}))
    remaining = iter(pages)
    async def respond(route):
        if route.path == "users":
            if isinstance(profiles, Exception):
                raise profiles
            return {"data": profiles or []}
        response = next(remaining)
        if isinstance(response, Exception):
            raise response
        return response
    api = AsyncMock(side_effect=respond)
    bot = SimpleNamespace(services=SimpleNamespace(broadcasters=SimpleNamespace(
        get_broadcasters=lambda: {"1": SimpleNamespace(id="1")})),
        _http=SimpleNamespace(request_json=api))
    monkeypatch.setattr(dashboard, "get_bot", lambda: bot)
    return api


def stream(user="2", viewers=42):
    return {"user_id": user, "user_login": f"viewer{user}", "user_name": f"Viewer{user}",
            "title": "A live stream", "game_name": "Retro", "viewer_count": viewers,
            "thumbnail_url": "https://static-cdn.jtvnw.net/previews/test-{width}x{height}.jpg"}


@pytest.mark.asyncio
async def test_preview_fetches_only_cached_follower_total_not_follower_identities(monkeypatch):
    api = runtime(monkeypatch, [{'total': 1234, 'data': [{'user_id': 'private-follower'}]}])
    for _ in range(2):
        result = await dashboard.channel_raid_preview(request(), target_id='2')
        assert json.loads(result.body) == {'follower_count': 1234}
    assert api.await_count == 1
    assert api.call_args.args[0].path == 'channels/followers'
    assert api.call_args.args[0].params == {'broadcaster_id': '2', 'first': 1}


@pytest.mark.asyncio
@pytest.mark.parametrize('total, expected', [(0, 0), (None, None), (-1, None), ('12', None), (True, None)])
async def test_preview_follower_count_preserves_zero_and_rejects_invalid_totals(monkeypatch, total, expected):
    runtime(monkeypatch, [{'total': total}])
    result = await dashboard.channel_raid_preview(request(), target_id='2')
    assert json.loads(result.body) == {'follower_count': expected}


@pytest.mark.asyncio
async def test_preview_follower_errors_do_not_break_stream_preview(monkeypatch):
    runtime(monkeypatch, [RuntimeError('Unavailable')])
    result = await dashboard.channel_raid_preview(request(), target_id='2')
    assert result.status_code == 200
    assert json.loads(result.body) == {'follower_count': None}


@pytest.mark.asyncio
async def test_preview_follower_endpoint_requires_auth_and_a_valid_channel(monkeypatch):
    api = runtime(monkeypatch, [])
    assert (await dashboard.channel_raid_preview(request(None), target_id='2')).status_code == 401
    assert (await dashboard.channel_raid_preview(request('unknown'), target_id='2')).status_code == 401
    assert (await dashboard.channel_raid_preview(request(), target_id='bad')).status_code == 400
    assert api.await_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("mode, expected", [("any", ["2", "3"]), ("all", ["2"])])
async def test_tag_matching_modes(monkeypatch, mode, expected):
    runtime(monkeypatch, [{"data": [dict(stream("2"), tags=["VTuber", "Art"]),
        dict(stream("3"), tags=["vtuber"]), dict(stream("4"), tags=["Music"])]}])
    response = await dashboard.channel_raid_browser(request(), tags="vtuber,art", tag_match=mode)
    assert [item["id"] for item in json.loads(response.body)["channels"]] == expected


@pytest.mark.asyncio
async def test_default_tag_matching_requires_all_tags(monkeypatch):
    runtime(monkeypatch, [{"data": [dict(stream("2"), tags=["VTuber", "Art"]),
        dict(stream("3"), tags=["VTuber"])]}])
    response = await dashboard.channel_raid_browser(request(), tags="VTuber,Art")
    assert [item["id"] for item in json.loads(response.body)["channels"]] == ["2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("location", ["games", "more_games", "missing"])
async def test_raid_categories_prioritize_current_and_remove_duplicates(monkeypatch, location):
    runtime(monkeypatch, [{"data": [{"game_id": "123", "game_name": "Current category"}]}])
    art = AsyncMock(return_value="https://static-cdn.jtvnw.net/current.jpg")
    monkeypatch.setattr(dashboard, "get_category_artwork", art)
    current = {"id": "123", "name": "Current category", "box_art_url": "existing.jpg"}
    payload = {"games": [{"id": "456", "name": "Other"}], "more_games": [{"id": "789", "name": "More"}]}
    if location != "missing": payload[location].append(current)
    result = await dashboard.prioritize_raid_current_category(dashboard.get_bot(), "1", payload)
    assert [game["id"] for game in result["games"]] == ["123", "456"]
    assert [game["id"] for game in result["more_games"]] == ["789"]
    if location == "missing": art.assert_awaited_once()
    else:
        art.assert_not_awaited()
        assert result["games"][0]["box_art_url"] == "existing.jpg"


@pytest.mark.asyncio
async def test_current_category_lookup_failure_preserves_category_choices(monkeypatch):
    runtime(monkeypatch, [RuntimeError("unavailable")])
    payload = {"games": [{"id": "456", "name": "Other"}], "more_games": []}
    assert await dashboard.prioritize_raid_current_category(dashboard.get_bot(), "1", payload) == payload


@pytest.mark.asyncio
async def test_current_category_updates_immediately_despite_warm_channel_cache(monkeypatch):
    api = runtime(monkeypatch, [
        {"data": [{"game_id": "123", "game_name": "Old category"}]},
        {"data": [{"game_id": "456", "game_name": "New category"}]},
    ])
    bot = dashboard.get_bot()
    payload = {"games": [{"id": "123", "name": "Old category"}, {"id": "456", "name": "New category"}], "more_games": []}
    first = await dashboard.prioritize_raid_current_category(bot, "1", payload)
    assert first["games"][0]["id"] == "123"
    second = await dashboard.prioritize_raid_current_category(bot, "1", payload)
    assert second["games"][0]["id"] == "456"
    assert api.await_count == 2
    cached = await dashboard.raid_browser_cached_request(bot, "1", "channels", {"broadcaster_id": "1"})
    assert cached["data"][0]["game_id"] == "456"
    assert api.await_count == 2


@pytest.mark.asyncio
async def test_invalid_tag_matching_mode(monkeypatch):
    runtime(monkeypatch, [])
    assert (await dashboard.channel_raid_browser(request(), tag_match="invalid")).status_code == 400


@pytest.mark.asyncio
async def test_null_stream_tags_are_returned_as_empty_list(monkeypatch):
    runtime(monkeypatch, [{"data": [dict(stream("2"), tags=None)]}])
    response = await dashboard.channel_raid_browser(request())
    assert response.status_code == 200
    assert json.loads(response.body)["channels"][0]["tags"] == []


@pytest.mark.asyncio
async def test_sparse_for_you_page_with_null_tags_does_not_break_pagination(monkeypatch):
    monkeypatch.setattr(dashboard, "get_suggested_streamers", AsyncMock(return_value=([], "cached")))
    monkeypatch.setattr(dashboard, "raid_browser_followed_streams", AsyncMock(return_value=[]))
    monkeypatch.setattr(dashboard, "raid_browser_team_streams", AsyncMock(return_value=([], {})))
    api = runtime(monkeypatch, [
        {"data": [{"game_id": "123", "tags": None, "broadcaster_language": "en"}]},
        {"data": [dict(stream("2"), tags=None), dict(stream("3"), tags=["VTuber", "Artist"])],
         "pagination": {"cursor": "next"}},
    ])
    response = await dashboard.channel_raid_browser(request(), sort="for_you", tags="vtuber,artist",
        tag_match="all", after="fy-discovery:official:3:previous")
    assert response.status_code == 200
    payload = json.loads(response.body)
    assert [item["id"] for item in payload["channels"]] == ["3"]
    assert payload["channel_tags"] == []
    assert payload["cursor"] == "fy-discovery:official:4:next"
    assert any(call.args[0].params == {"first": 100, "after": "previous"} for call in api.await_args_list)


@pytest.mark.asyncio
async def test_for_you_selected_all_tags_gets_tag_specific_first_page_without_implicit_language(monkeypatch):
    monkeypatch.setattr(dashboard, "get_suggested_streamers", AsyncMock(return_value=([], "cached")))
    monkeypatch.setattr(dashboard, "raid_browser_followed_streams", AsyncMock(return_value=[]))
    monkeypatch.setattr(dashboard, "raid_browser_team_streams", AsyncMock(return_value=([], {})))
    source = AsyncMock(return_value={"ids": ["2"], "cursor": "private-next"})
    monkeypatch.setattr(dashboard, "get_sorted_directory", source)
    runtime(monkeypatch, [
        {"data": [{"game_id": "123", "tags": ["VTuber"], "broadcaster_language": "en"}]},
        {"data": [dict(stream("2"), tags=["VTuber", "Artist"], language="ja")]},
    ])
    response = await dashboard.channel_raid_browser(request(), sort="for_you", tags="VTuber,Artist", tag_match="all")
    assert response.status_code == 200
    payload = json.loads(response.body)
    assert [item["id"] for item in payload["channels"]] == ["2"]
    assert payload["cursor"] == "fy-discovery:official-start"
    assert source.await_args.kwargs == {"sort": "viewers_desc", "tags": ["VTuber", "Artist"],
        "tag_match": "all", "category_id": "", "language": ""}


@pytest.mark.asyncio
async def test_any_tags_merge_distinct_single_tag_first_pages(monkeypatch):
    source = AsyncMock(side_effect=[{"ids": ["2", "3"], "cursor": "more"}, {"ids": ["3", "4"], "cursor": ""}])
    monkeypatch.setattr(dashboard, "get_sorted_directory", source)
    api = runtime(monkeypatch, [{"data": [stream("2"), stream("3"), stream("4")]}])
    result = await dashboard.raid_browser_tag_directory(dashboard.get_bot(), "1", tags=["VTuber", "Artist"], tag_match="any")
    assert [call.kwargs["tags"] for call in source.await_args_list] == [["VTuber"], ["Artist"]]
    assert all(call.kwargs["tag_match"] == "all" for call in source.await_args_list)
    assert api.await_args.args[0].params["user_id"] == ["2", "3", "4"]
    assert result["has_more"] is True


@pytest.mark.asyncio
async def test_tag_first_page_failure_uses_official_source(monkeypatch):
    monkeypatch.setattr(dashboard, "get_suggested_streamers", AsyncMock(return_value=([], "cached")))
    monkeypatch.setattr(dashboard, "raid_browser_followed_streams", AsyncMock(return_value=[]))
    monkeypatch.setattr(dashboard, "raid_browser_team_streams", AsyncMock(return_value=([], {})))
    monkeypatch.setattr(dashboard, "get_sorted_directory", AsyncMock(side_effect=ValueError("Unavailable")))
    api = runtime(monkeypatch, [{"data": [{"game_id": "123", "tags": None}]},
        {"data": [dict(stream("2"), tags=["VTuber", "Artist"])], "pagination": {"cursor": "more"}}])
    response = await dashboard.channel_raid_browser(request(), sort="for_you", tags="VTuber,Artist", tag_match="all")
    payload = json.loads(response.body)
    assert [item["id"] for item in payload["channels"]] == ["2"]
    assert payload["cursor"] == "fy-discovery:official:1:more"
    assert api.await_args_list[1].args[0].params == {"first": 100}


@pytest.mark.asyncio
async def test_match_all_without_selected_tags_does_not_filter(monkeypatch):
    runtime(monkeypatch, [{"data": [stream("2")]}])
    response = await dashboard.channel_raid_browser(request(), tag_match="all")
    assert len(json.loads(response.body)["channels"]) == 1


@pytest.mark.asyncio
async def test_channel_results_include_profile_picture_from_twitch_users(monkeypatch):
    url = "https://static-cdn.jtvnw.net/jtv_user_pictures/viewer.png"
    runtime(monkeypatch, [{"data": [stream("2")]}], profiles=[{"id": "2", "profile_image_url": url, "description": "Channel bio"}])
    payload = json.loads((await dashboard.channel_raid_browser(request())).body)
    assert payload["channels"][0]["profile_image_url"] == url
    assert payload["channels"][0]["description"] == "Channel bio"


@pytest.mark.asyncio
async def test_collection_visibility_uses_full_live_lists_and_ignores_blacklisted_channels(monkeypatch):
    monkeypatch.setattr(dashboard, "raid_browser_cached_request", AsyncMock(return_value={"data": [stream("2")]}))
    teams = AsyncMock(return_value=([stream("3")], {"3": ["Our team"]}))
    monkeypatch.setattr(dashboard, "raid_browser_team_streams", teams)
    assert await collection_lookup(object(), "1", ["2"], set()) == {"favorites_live": True, "team_live": True, "live_favorite_ids": ["2"]}
    assert await collection_lookup(object(), "1", ["2"], {"2", "3"}) == {"favorites_live": False, "team_live": False, "live_favorite_ids": []}
    monkeypatch.setattr(dashboard, "raid_browser_team_streams", AsyncMock(return_value=([], {})))
    assert await collection_lookup(object(), "1", [], set()) == {"favorites_live": False, "team_live": False, "live_favorite_ids": []}


@pytest.mark.asyncio
async def test_collection_lookup_failure_does_not_claim_a_collection_is_empty(monkeypatch):
    monkeypatch.setattr(dashboard, "raid_browser_cached_request", AsyncMock(side_effect=RuntimeError("unavailable")))
    monkeypatch.setattr(dashboard, "raid_browser_team_streams", AsyncMock(side_effect=RuntimeError("unavailable")))
    assert await collection_lookup(object(), "1", ["2"], set()) == {}


@pytest.mark.asyncio
async def test_developer_tab_returns_only_live_developers_and_has_no_cursor(monkeypatch):
    monkeypatch.setattr(dashboard, "raid_browser_dev_streams", AsyncMock(return_value=[
        dict(stream("2"), user_login="minamichimaa")]))
    api = runtime(monkeypatch, [{"data": [stream("3")]}])
    payload = json.loads((await dashboard.channel_raid_browser(request(), developer_only=True, favorites="3")).body)
    assert payload["developers_live"] is True
    assert [item["login"] for item in payload["channels"]] == ["minamichimaa"]
    assert payload["cursor"] == ""


@pytest.mark.asyncio
async def test_developer_tab_hidden_when_neither_account_is_live(monkeypatch):
    runtime(monkeypatch, [])
    payload = json.loads((await dashboard.channel_raid_browser(request(), developer_only=True)).body)
    assert payload["developers_live"] is False
    assert payload["channels"] == []


@pytest.mark.asyncio
async def test_dev_channels_are_live_candidates_below_favorites_even_in_production(monkeypatch):
    monkeypatch.setattr(dashboard.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(dashboard, "raid_browser_dev_streams", AsyncMock(return_value=[
        dict(stream("1", 1), user_login="minamichimaa"), dict(stream("2", 2), user_login="ninjakaing")]))
    runtime(monkeypatch, [{"data": [stream("3", 1000), stream("4", 10)]}, {"data": [stream("4", 10)]}])
    payload = json.loads((await dashboard.channel_raid_browser(request(), favorites="4")).body)
    assert [item["id"] for item in payload["channels"]] == ["4", "2", "1", "3"]
    assert payload["channels"][2]["is_self"] is True
    assert payload["channels"][2]["dev_priority"] is True


@pytest.mark.asyncio
async def test_dev_candidates_still_respect_blacklist_and_filters(monkeypatch):
    monkeypatch.setattr(dashboard, "raid_browser_dev_streams", AsyncMock(return_value=[
        dict(stream("2"), user_login="minamichimaa", language="en"),
        dict(stream("3"), user_login="ninjakaing", language="ja")]))
    runtime(monkeypatch, [{"data": []}])
    payload = json.loads((await dashboard.channel_raid_browser(request(), blocked="2", language="en")).body)
    assert payload["channels"] == []


@pytest.mark.asyncio
async def test_dev_lookup_only_requests_live_streams_of_the_named_accounts(monkeypatch):
    fetch = AsyncMock(side_effect=[{"data": [{"id": "2", "login": "minamichimaa"}, {"id": "3", "login": "ninjakaing"}]},
        {"data": [dict(stream("2"), user_login="minamichimaa")]}])
    monkeypatch.setattr(dashboard, "raid_browser_cached_request", fetch)
    assert len(await dev_lookup(object(), "1")) == 1
    assert fetch.await_args_list[0].args[3] == {"login": ["minamichimaa", "ninjakaing"]}
    assert fetch.await_args_list[1].args[3]["user_id"] == ["2", "3"]


@pytest.mark.asyncio
async def test_event_filter_uses_drops_directory_and_keeps_other_filters(monkeypatch):
    source = AsyncMock(return_value={"ids": ["2", "3", "4"], "cursor": "next"})
    monkeypatch.setattr(dashboard, "get_sorted_directory", source)
    runtime(monkeypatch, [{"data": [dict(stream("2"), tags=["DropsEnabled", "Art"]),
        dict(stream("3"), tags=["DropsEnabled"]), dict(stream("4"), tags=["Art"])]}])
    response = await dashboard.channel_raid_browser(request(), event="drops_enabled", tags="Art")
    payload = json.loads(response.body)
    assert [channel["id"] for channel in payload["channels"]] == ["2"]
    assert source.await_args.kwargs["tags"] == ["DropsEnabled"]
    assert payload["cursor"] == "next"


@pytest.mark.asyncio
async def test_unknown_event_rejected_before_twitch_lookup(monkeypatch):
    api = runtime(monkeypatch, [])
    assert (await dashboard.channel_raid_browser(request(), event="made_up")).status_code == 400
    api.assert_not_awaited()


@pytest.mark.asyncio
async def test_drops_event_uses_specific_twitch_tag_not_generic_drops_text(monkeypatch):
    runtime(monkeypatch, [{"data": [dict(stream("2"), tags=["DropsEnabled"]),
        dict(stream("3"), tags=["drops"], title="Streamer-versary"),
        dict(stream("4"), tags=["dropsenabled"])]}])
    payload = json.loads((await dashboard.channel_raid_browser(request())).body)
    events = {channel["id"]: channel["events"] for channel in payload["channels"]}
    assert events == {"2": ["Drops Enabled"], "3": [], "4": ["Drops Enabled"]}


@pytest.mark.asyncio
async def test_follow_badges_verify_mutual_only_for_followed_channels(monkeypatch):
    api = runtime(monkeypatch, [
        {"scopes": ["moderator:read:followers"]}, {"data": [{"user_id": "2"}]}, {"data": []},
    ])
    result = await relationship_lookup(dashboard.get_bot(), "1", [{"id": "2"}, {"id": "3"}, {"id": "4"}], {"2", "3"})
    assert result == {"2": {"followed": True, "mutual": True}, "3": {"followed": True, "mutual": False}, "4": {"followed": False, "mutual": None}}
    assert api.await_count == 3
    again = await relationship_lookup(dashboard.get_bot(), "1", [{"id": "2"}], {"2"})
    assert again["2"]["mutual"] is True
    assert api.await_count == 3


@pytest.mark.asyncio
async def test_follow_badges_preserve_following_when_mutual_permission_is_missing(monkeypatch):
    api = runtime(monkeypatch, [{"scopes": []}])
    result = await relationship_lookup(dashboard.get_bot(), "1", [{"id": "2"}], {"2"})
    assert result["2"] == {"followed": True, "mutual": None}
    assert api.await_count == 1


@pytest.mark.asyncio
async def test_favorites_resolve_follow_relationships_too(monkeypatch):
    runtime(monkeypatch, [{"data": [stream("2")]}, {"scopes": ["moderator:read:followers"]}, {"data": [{"user_id": "2"}]}])
    result = await relationship_lookup(dashboard.get_bot(), "1", [{"id": "2"}])
    assert result["2"] == {"followed": True, "mutual": True}


def test_channel_size_bonuses_are_proportional_symmetric_and_ignore_unknown_counts():
    score = dashboard.raid_relevance_score
    assert score(own_viewers=20, viewers=20) == 180
    assert score(own_viewers=20, viewers=40) == score(own_viewers=40, viewers=20) == 90
    assert score(own_viewers=20, viewers=200) == 18
    assert score(own_followers=1000, followers=1000) == 120
    assert score(own_followers=1000, followers=2000) == 60
    assert score(own_viewers=20, viewers=20, own_followers=1000, followers=1000) < score(followed=True)
    for unknown in (None, 0, -1, True, '20'):
        assert score(own_viewers=unknown, viewers=20, own_followers=1000, followers=unknown) == 0


@pytest.mark.asyncio
async def test_channel_size_lookup_is_cached_and_never_exposes_follower_identities():
    async def respond(route):
        assert route.path == 'channels/followers' and route.token_for == '1'
        assert route.params['first'] == 1
        return {'total': int(route.params['broadcaster_id']) * 100, 'data': [{'user_id': 'private'}]}
    bot = SimpleNamespace(_http=SimpleNamespace(request_json=AsyncMock(side_effect=respond)))
    for _ in range(2):
        assert await dashboard.raid_browser_channel_sizes(bot, '1', ['2', '3']) == {'1': 100, '2': 200, '3': 300}
    assert bot._http.request_json.await_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize('sort, expected', [('for_you', ['3', '2']), ('viewers_desc', ['2', '3'])])
async def test_for_you_prefers_similar_viewers_and_channel_size_without_changing_explicit_sort(monkeypatch, sort, expected):
    monkeypatch.setattr(dashboard, 'get_suggested_streamers', AsyncMock(return_value=([], 'cached')))
    monkeypatch.setattr(dashboard, 'raid_browser_team_streams', AsyncMock(return_value=([], {})))
    monkeypatch.setattr(dashboard, 'raid_browser_relationships', AsyncMock(return_value={}))
    runtime(monkeypatch, [
        {'data': [{'game_id': '123', 'tags': [], 'broadcaster_language': 'en'}]},
        {'data': [stream('2', 1000), stream('3', 20)]},
    ])
    bot = dashboard.get_bot()
    # The runtime fixture supplies lightweight broadcasters; return a persistent one here.
    broadcaster = SimpleNamespace(id='1', viewer_count=20)
    bot.services.broadcasters.get_broadcasters = lambda: {'1': broadcaster}
    monkeypatch.setattr(dashboard, 'raid_browser_channel_sizes', AsyncMock(return_value={'1': 1000, '2': 100000, '3': 1000}))
    response = await dashboard.channel_raid_browser(request(), recommended=True, following=True, sort=sort)
    channels = json.loads(response.body)['channels']
    assert [item['id'] for item in channels] == expected
    if sort == 'for_you':
        assert channels[0]['match_breakdown']['Similar viewer count'] == 180
        assert channels[0]['match_breakdown']['Similar channel size'] == 120
    else:
        dashboard.raid_browser_channel_sizes.assert_not_awaited()
    assert all(item['relevance'] == sum(item['match_breakdown'].values()) for item in channels)


def test_following_is_stronger_than_team_or_vtuber_match_but_not_combined_compatibility():
    score = dashboard.raid_relevance_score
    followed = score(followed=True)
    assert followed < score(followed=True, mutual=True) < score(same_category=True, both_vtubers=True)
    assert score(followed=True, mutual=True) - followed == 80
    assert score(mutual=True) == score()
    assert 0 < score(recent_raid=0.5) < score(recent_raid=1) < followed
    assert score(recent_raid=0) == score(recent_raid=-1)
    assert score(recent_raid=1) == score(recent_raid=2)
    assert followed > score(same_team=True)
    assert score(same_team=True) == 200
    assert score(same_team=True, both_vtubers=True) == 500
    assert followed > score(both_vtubers=True)
    assert followed < score(same_category=True, both_vtubers=True, shared_tags={"vtuber", "art"})
    assert score(same_team=True, both_vtubers=True) > score(same_team=True) + score(both_vtubers=True)
    assert score(shared_tags={"VTuber"}, both_vtubers=True) == score(both_vtubers=True)
    assert score(shared_tags={str(index) for index in range(10)}) == score(shared_tags={str(index) for index in range(5)})


@pytest.mark.asyncio
@pytest.mark.parametrize("sort,expected", [
    ("viewers_asc", ["4", "2", "3"]), ("viewers_desc", ["3", "2", "4"]),
    ("name_asc", ["3", "4", "2"]), ("name_desc", ["2", "4", "3"]),
    ("uptime_asc", ["3", "2", "4"]), ("uptime_desc", ["2", "3", "4"])])
async def test_raid_browser_sort_options(monkeypatch, sort, expected):
    monkeypatch.setattr(dashboard, "get_sorted_directory", AsyncMock(return_value={"ids": ["2", "3", "4"], "cursor": ""}))
    runtime(monkeypatch, [{"data": [
        {**stream("2", 10), "user_name": "Zulu", "started_at": "2026-10-14T01:00:00Z"},
        {**stream("3", 50), "user_name": "alpha", "started_at": "2026-10-14T02:00:00Z"},
        {**stream("4", 0), "user_name": "Middle"}]}])
    result = await dashboard.channel_raid_browser(request(), sort=sort)
    assert [item["id"] for item in json.loads(result.body)["channels"]] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('sort, expected', [('for_you', ['3', '2']), ('viewers_desc', ['2', '3'])])
async def test_verified_mutual_bonus_affects_relevance_but_not_explicit_sorts(monkeypatch, sort, expected):
    monkeypatch.setattr(dashboard, 'get_suggested_streamers', AsyncMock(return_value=([], 'cached')))
    monkeypatch.setattr(dashboard, 'raid_browser_team_streams', AsyncMock(return_value=([], {})))
    monkeypatch.setattr(dashboard, 'raid_browser_relationships', AsyncMock(return_value={
        '2': {'followed': True, 'mutual': None},
        '3': {'followed': True, 'mutual': True},
    }))
    runtime(monkeypatch, [
        {'data': [{'game_id': '123', 'tags': [], 'broadcaster_language': 'en'}]},
        {'data': [stream('2', 100), stream('3', 20)]},
    ])
    payload = json.loads((await dashboard.channel_raid_browser(request(), recommended=True, following=True, sort=sort)).body)
    assert [item['id'] for item in payload['channels']] == expected
    scores = {item['id']: item['relevance'] for item in payload['channels']}
    assert scores['3'] - scores['2'] == 80
    for item in payload['channels']:
        assert item['relevance'] == sum(item['match_breakdown'].values())
        assert item['match_breakdown']['Mutual following'] == (80 if item['id'] == '3' else 0)


@pytest.mark.asyncio
async def test_low_to_high_keeps_curated_pool_and_uses_current_category_tags_and_language(monkeypatch):
    monkeypatch.setattr(dashboard, "get_suggested_streamers", AsyncMock(return_value=([], "cached")))
    monkeypatch.setattr(dashboard, "raid_browser_followed_streams", AsyncMock(return_value=[stream("2", 20)]))
    monkeypatch.setattr(dashboard, "raid_browser_team_streams", AsyncMock(return_value=([stream("3", 50)], {"3": ["Team"]})))
    source = AsyncMock(return_value={"ids": ["4"], "cursor": "next-low"})
    monkeypatch.setattr(dashboard, "get_sorted_directory", source)
    api = runtime(monkeypatch, [{"data": [{"game_id": "123", "tags": ["English", "VTuber"], "broadcaster_language": "en"}]},
        {"data": [stream("4", 0)]}])
    response = await dashboard.channel_raid_browser(request(), recommended=True, sort="viewers_asc")
    source.assert_awaited_once()
    assert source.await_args.kwargs["category_id"] == "123"
    assert source.await_args.kwargs["language"] == "en"
    assert source.await_args.kwargs["tags"] == ["VTuber"]
    data = json.loads(response.body)
    assert [item["id"] for item in data["channels"]] == ["4", "2", "3"]
    assert data["channels"][1]["followed"] is True
    assert data["channels"][2]["teams"] == ["Team"]
    assert api.await_args_list[1].args[0].params["user_id"] == ["4"]


@pytest.mark.asyncio
async def test_low_to_high_uses_source_sorted_ids_and_does_not_inject_favorites(monkeypatch):
    source = AsyncMock(return_value={"ids": ["2", "3"], "cursor": "next-low"})
    monkeypatch.setattr(dashboard, "get_sorted_directory", source)
    api = runtime(monkeypatch, [{"data": [{**stream("2", 0), "game_id": "123", "language": "en", "tags": ["VTuber"]},
        {**stream("3", 1), "game_id": "123", "language": "en", "tags": ["VTuber"]}]}])
    response = await dashboard.channel_raid_browser(request(), sort="viewers_asc", favorites="99", category_id="123", language="en", tags="VTuber", after="previous-low")
    source.assert_awaited_once()
    kwargs = source.await_args.kwargs
    assert kwargs["after"] == "previous-low" and kwargs["category_id"] == "123"
    assert kwargs["tags"] == ["VTuber"]
    route = api.await_args_list[0].args[0]
    assert route.params["user_id"] == ["2", "3"]
    assert "game_id" not in route.params
    assert json.loads(response.body)["cursor"] == "next-low"
    assert [item["id"] for item in json.loads(response.body)["channels"]] == ["2", "3"]


@pytest.mark.asyncio
async def test_sorted_directory_failure_uses_official_fallback_and_discloses_sort_scope(monkeypatch):
    monkeypatch.setattr(dashboard, "get_sorted_directory", AsyncMock(side_effect=ValueError("Unavailable")))
    api = runtime(monkeypatch, [{"data": [stream("2", 50), stream("3", 2)], "pagination": {"cursor": "next"}}])
    response = await dashboard.channel_raid_browser(request(), sort="viewers_asc")
    assert response.status_code == 200
    payload = json.loads(response.body)
    assert payload["sort_scope"] == "fetched"
    assert payload["cursor"] == "official:1:next"
    assert [item["id"] for item in payload["channels"]] == ["3", "2"]
    assert api.await_args_list[0].args[0].params == {"first": 100}


@pytest.mark.asyncio
async def test_recommended_mix_includes_live_suggested_channels_and_deduplicates(monkeypatch):
    monkeypatch.setattr(dashboard, "get_suggested_streamers", AsyncMock(return_value=(
        [{"id": "2", "login": "viewer2"}], "cached")))
    monkeypatch.setattr(dashboard, "raid_browser_team_streams", AsyncMock(return_value=([], {})))
    monkeypatch.setattr(dashboard, "raid_browser_followed_streams", AsyncMock(return_value=[]))
    api = runtime(monkeypatch, [
        {"data": [{"game_id": "123", "tags": [], "broadcaster_language": "en"}]},
        {"data": [stream("2", 5)]},
        {"data": [stream("3", 100), stream("2", 5)]}])
    response = await dashboard.channel_raid_browser(request(), recommended=True)
    data = json.loads(response.body)
    assert [item["id"] for item in data["channels"]] == ["2", "3"]
    assert data["channels"][0]["suggested"] is True
    assert "Suggested streamer" in data["channels"][0]["reasons"]
    assert data["suggested_status"] == "cached"
    assert api.await_args_list[1].args[0].params["user_id"] == ["2"]


@pytest.mark.asyncio
async def test_official_fallback_continuation_never_sends_helix_cursor_to_private_directory(monkeypatch):
    source = AsyncMock(side_effect=AssertionError("Must not call private directory"))
    monkeypatch.setattr(dashboard, "get_sorted_directory", source)
    api = runtime(monkeypatch, [{"data": [dict(stream("2"), game_id="123", language="en", tags=["VTuber", "Art"]),
        dict(stream("3"), game_id="123", language="en", tags=["VTuber"])], "pagination": {"cursor": "next"}}])
    response = await dashboard.channel_raid_browser(request(), sort="viewers_asc", after="official:1:previous",
        category_id="123", language="en", tags="vtuber,art", tag_match="all")
    payload = json.loads(response.body)
    assert [item["id"] for item in payload["channels"]] == ["2"]
    assert payload["cursor"] == "official:2:next"
    assert payload["sort_scope"] == "fetched"
    assert api.await_args_list[0].args[0].params == {"first": 100, "after": "previous", "game_id": "123", "language": "en"}
    source.assert_not_awaited()


@pytest.mark.asyncio
async def test_official_discovery_stops_after_five_pages_even_when_no_tags_match(monkeypatch):
    runtime(monkeypatch, [{"data": [], "pagination": {"cursor": str(index)}} for index in range(5)])
    bot = dashboard.get_bot()
    cursor = ""
    for index in range(5):
        page = await dashboard.raid_browser_official_directory(bot, "1", after=cursor)
        cursor = page["pagination"]["cursor"]
        assert page["search_limited"] is (index == 4)
        assert bool(cursor) is (index < 4)


@pytest.mark.asyncio
@pytest.mark.parametrize("cursor", ["official:5:next", "official:0:next", "official:-1:next", "private:1:next"])
async def test_official_directory_rejects_out_of_budget_or_wrong_source_cursors(monkeypatch, cursor):
    api = runtime(monkeypatch, [])
    with pytest.raises(ValueError):
        await dashboard.raid_browser_official_directory(dashboard.get_bot(), "1", after=cursor)
    api.assert_not_awaited()


@pytest.mark.asyncio
async def test_suggested_filter_only_shows_live_suggestions_and_respects_blacklist(monkeypatch):
    monkeypatch.setattr(dashboard, "get_suggested_streamers", AsyncMock(return_value=(
        [{"id": "2", "login": "viewer2"}, {"id": "4", "login": "offline"}], "fresh")))
    runtime(monkeypatch, [{"data": [stream("2"), stream("3")]}])
    response = await dashboard.channel_raid_browser(request(), suggested=True)
    assert [item["id"] for item in json.loads(response.body)["channels"]] == ["2"]
    response = await dashboard.channel_raid_browser(request(), suggested=True, blocked="2")
    assert json.loads(response.body)["channels"] == []


@pytest.mark.asyncio
async def test_explicit_category_filters_discovery_and_results(monkeypatch):
    matching = {**stream("2"), "game_id": "123"}
    other = {**stream("3"), "game_id": "456"}
    api = runtime(monkeypatch, [{"data": [matching, other]}])
    response = await dashboard.channel_raid_browser(request(), category_id="123")
    assert response.status_code == 200
    assert [item["id"] for item in json.loads(response.body)["channels"]] == ["2"]
    assert api.await_args_list[0].args[0].params["game_id"] == "123"
    response = await dashboard.channel_raid_browser(request(), category_id="invalid")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_browse_requires_authenticated_connected_channel(monkeypatch):
    api = runtime(monkeypatch, [])
    assert (await dashboard.channel_raid_browser(request(None))).status_code == 401
    assert (await dashboard.channel_raid_browser(request("missing"))).status_code == 404
    api.assert_not_awaited()


@pytest.mark.asyncio
async def test_browse_returns_live_channels_sorted_and_excludes_self(monkeypatch):
    api = runtime(monkeypatch, [{"data": [stream("2", 2), stream("1"), stream("3", 100)],
                                "pagination": {"cursor": "next"}}])
    response = await dashboard.channel_raid_browser(request(), after="previous")
    data = json.loads(response.body)
    assert [channel["id"] for channel in data["channels"]] == ["3", "2"]
    assert data["channels"][0]["thumbnail_url"].endswith("320x180.jpg")
    assert data["channels"][0]["thumbnail_url_medium"].endswith("640x360.jpg")
    assert data["channels"][0]["thumbnail_url_large"].endswith("1280x720.jpg")
    assert data["cursor"] == "next"
    route = api.await_args_list[0].args[0]
    assert route.path == "streams"
    assert route.token_for == "1"
    assert route.method == "GET"
    assert route.params["after"] == "previous"


@pytest.mark.asyncio
async def test_search_only_live_channels_then_loads_stream_details(monkeypatch):
    api = runtime(monkeypatch, [{"data": [{"id": "2", "is_live": True},
                                          {"id": "3", "is_live": False},
                                          {"id": "1", "is_live": True}],
                                "pagination": {"cursor": "search-next"}},
                               {"data": [stream()]}])
    response = await dashboard.channel_raid_browser(request(), query=" Retro ")
    assert response.status_code == 200
    search_route, stream_route = [call.args[0] for call in api.await_args_list if call.args[0].path != "users"]
    assert search_route.path == "search/channels"
    assert search_route.params["live_only"] == "true"
    assert search_route.params["query"] == "Retro"
    assert stream_route.params["user_id"] == ["2"]
    assert json.loads(response.body)["cursor"] == "search-next"


@pytest.mark.asyncio
async def test_empty_search_does_not_fetch_unfiltered_streams(monkeypatch):
    api = runtime(monkeypatch, [{"data": [], "pagination": {}}, {"data": [], "pagination": {}}])
    response = await dashboard.channel_raid_browser(request(), query="missing")
    assert json.loads(response.body)["channels"] == []
    assert api.await_count == 2
    assert all(call.args[0].path == "search/channels" and call.args[0].params["query"] for call in api.await_args_list)


def test_channel_fuzzy_matching_prioritizes_exact_names_and_handles_typos():
    score = dashboard.raid_channel_search_score
    assert score('MINA', 'mina') > score('mina', 'minamichimaa') > score('mina', 'theminashow')
    assert score('minamichima', 'minamichimaa') > 0
    assert score('mian', 'mina') > 0
    assert score('mina', 'other', 'Mi_na') == 1000
    assert score('mi', 'rat') == 0
    assert score('minamichimaa', 'completelydifferent', 'Other', 'Retro') == 0


@pytest.mark.asyncio
async def test_fuzzy_fallback_pagination_keeps_original_query_for_matching(monkeypatch):
    api = runtime(monkeypatch, [
        {"data": [], "pagination": {}},
        {"data": [{"id": "2", "is_live": True}], "pagination": {"cursor": "next"}},
        {"data": [dict(stream("2"), user_login="minamichimaa")]},
        {"data": [{"id": "3", "is_live": True}], "pagination": {}},
        {"data": [dict(stream("3"), user_login="minamichima")]},
    ])
    first = json.loads((await dashboard.channel_raid_browser(request(), query="minamichima")).body)
    assert first["cursor"] == "fuzzy-search:next"
    assert [item["id"] for item in first["channels"]] == ["2"]
    second = json.loads((await dashboard.channel_raid_browser(request(), query="minamichima", after=first["cursor"])).body)
    assert second["cursor"] == ""
    assert [item["id"] for item in second["channels"]] == ["3"]
    searches = [call.args[0] for call in api.await_args_list if call.args[0].path == "search/channels"]
    assert searches[-1].params["query"] == "minam"
    assert searches[-1].params["after"] == "next"


@pytest.mark.asyncio
@pytest.mark.parametrize("query,after", [("a" * 101, ""), ("", "a" * 501)])
async def test_search_bounds_checked_before_twitch_call(monkeypatch, query, after):
    api = runtime(monkeypatch, [])
    assert (await dashboard.channel_raid_browser(request(), query=query, after=after)).status_code == 400
    api.assert_not_awaited()


@pytest.mark.asyncio
async def test_upstream_failure_has_safe_error(monkeypatch):
    runtime(monkeypatch, [RuntimeError("private upstream detail")])
    response = await dashboard.channel_raid_browser(request())
    assert response.status_code == 502
    assert "private" not in response.body.decode()


@pytest.mark.asyncio
async def test_unavailable_runtime(monkeypatch):
    monkeypatch.setattr(dashboard, "get_bot", lambda: None)
    assert (await dashboard.channel_raid_browser(request())).status_code == 503


@pytest.mark.asyncio
async def test_category_tag_and_language_filters_combine(monkeypatch):
    selected = dict(stream("2"), game_id="game", language="ja", tags=["English", "VTuber"])
    wrong_language = dict(stream("3"), game_id="game", language="en", tags=["VTuber"])
    wrong_tags = dict(stream("4"), game_id="game", language="ja", tags=["Music"])
    api = runtime(monkeypatch, [{"data": [{"game_id": "game", "tags": ["VTuber"]}]},
                                {"data": [selected, wrong_language, wrong_tags], "pagination": {}}])
    response = await dashboard.channel_raid_browser(request(), same_category=True, same_tags=True,
                                                     tags="vtuber, Art", tag_match="any", language="ja")
    channels = json.loads(response.body)["channels"]
    assert [item["id"] for item in channels] == ["2"]
    assert channels[0]["tags"] == ["VTuber", "English"]
    route = api.await_args_list[1].args[0]
    assert route.params["game_id"] == "game"
    assert route.params["language"] == "ja"


@pytest.mark.asyncio
async def test_following_search_uses_authenticated_accounts_followed_streams(monkeypatch):
    api = runtime(monkeypatch, [{"data": [stream()], "pagination": {"cursor": "next"}}])
    response = await dashboard.channel_raid_browser(request(), following=True, query="retro")
    assert len(json.loads(response.body)["channels"]) == 1
    route = api.await_args_list[0].args[0]
    assert route.path == "streams/followed"
    assert route.params["user_id"] == "1"
    assert route.token_for == "1"
    assert "query" not in route.params


@pytest.mark.asyncio
async def test_not_following_excludes_all_followed_pages_and_keeps_discovery_cursor(monkeypatch):
    api = runtime(monkeypatch, [
        {"data": [stream("2")], "pagination": {"cursor": "follow-page-2"}},
        {"data": [stream("3")], "pagination": {}},
        {"data": [stream("2"), stream("3"), stream("4")], "pagination": {"cursor": "discovery-next"}},
    ])
    response = await dashboard.channel_raid_browser(request(), not_following=True)
    assert response.status_code == 200
    payload = json.loads(response.body)
    assert [item["id"] for item in payload["channels"]] == ["4"]
    assert payload["cursor"] == "discovery-next"
    assert api.await_args_list[0].args[0].path == "streams/followed"
    assert api.await_args_list[1].args[0].params["after"] == "follow-page-2"


@pytest.mark.asyncio
async def test_not_following_excludes_followed_favorites_and_developer_candidates(monkeypatch):
    runtime(monkeypatch, [
        {"data": [stream("2")], "pagination": {}},
        {"data": [stream("3")], "pagination": {}},
        {"data": [stream("2")], "pagination": {}},
    ])
    monkeypatch.setattr(dashboard, "raid_browser_dev_streams", AsyncMock(return_value=[stream("2")]))
    response = await dashboard.channel_raid_browser(request(), not_following=True, favorites="2")
    assert response.status_code == 200
    assert [item["id"] for item in json.loads(response.body)["channels"]] == ["3"]


@pytest.mark.asyncio
@pytest.mark.parametrize("filters", [{"following": True}, {"mutual": True}])
async def test_not_following_rejects_conflicting_follow_filters(monkeypatch, filters):
    api = runtime(monkeypatch, [])
    response = await dashboard.channel_raid_browser(request(), not_following=True, **filters)
    assert response.status_code == 400
    api.assert_not_awaited()


@pytest.mark.asyncio
async def test_not_following_does_not_hide_channels_when_no_live_channels_are_followed(monkeypatch):
    runtime(monkeypatch, [{"data": [], "pagination": {}}, {"data": [stream("4")], "pagination": {}}])
    response = await dashboard.channel_raid_browser(request(), not_following=True)
    assert response.status_code == 200
    assert [item["id"] for item in json.loads(response.body)["channels"]] == ["4"]


@pytest.mark.asyncio
async def test_not_following_also_filters_for_you_recommendations(monkeypatch):
    followed = dict(stream("2"), game_id="game", language="en", tags=[])
    other = dict(stream("3"), game_id="game", language="en", tags=[])
    runtime(monkeypatch, [
        {"data": [{"game_id": "game", "broadcaster_language": "en", "tags": []}]},
        {"data": [followed, other], "pagination": {"cursor": "next"}},
    ])
    monkeypatch.setattr(dashboard, "raid_browser_followed_streams", AsyncMock(return_value=[followed]))
    monkeypatch.setattr(dashboard, "get_suggested_streamers", AsyncMock(return_value=([], None)))
    monkeypatch.setattr(dashboard, "raid_browser_team_streams", AsyncMock(return_value=([], {})))
    response = await dashboard.channel_raid_browser(request(), recommended=True, not_following=True)
    assert response.status_code == 200
    payload = json.loads(response.body)
    assert [item["id"] for item in payload["channels"]] == ["3"]
    assert payload["cursor"] == "next"


@pytest.mark.asyncio
async def test_mutual_filter_checks_whether_followed_streamer_follows_our_channel(monkeypatch):
    api = runtime(monkeypatch, [{"scopes": ["user:read:follows", "moderator:read:followers"]},
                                {"data": [stream("2"), stream("3")], "pagination": {}},
                                {"data": [{"user_id": "2"}]}, {"data": []}])
    response = await dashboard.channel_raid_browser(request(), mutual=True)
    assert [item["id"] for item in json.loads(response.body)["channels"]] == ["2"]
    assert api.await_args_list[0].args[0].use_id is True
    for call in api.await_args_list[2:]:
        route = call.args[0]
        if route.path == "users":
            continue
        assert route.path == "channels/followers"
        assert route.params["broadcaster_id"] == "1"
        assert route.token_for == "1"


@pytest.mark.asyncio
async def test_missing_own_category_does_not_silently_return_unfiltered_results(monkeypatch):
    api = runtime(monkeypatch, [{"data": [{"game_id": "", "tags": []}]}])
    assert (await dashboard.channel_raid_browser(request(), same_category=True)).status_code == 400
    assert api.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("filters", [{"language": "invalid"}, {"tags": "a" * 251}])
async def test_invalid_filters_are_rejected_before_fetching(monkeypatch, filters):
    api = runtime(monkeypatch, [])
    assert (await dashboard.channel_raid_browser(request(), **filters)).status_code == 400
    api.assert_not_awaited()


@pytest.mark.asyncio
async def test_mutual_filter_requires_permission_instead_of_silently_showing_no_matches(monkeypatch):
    api = runtime(monkeypatch, [{"scopes": ["user:read:follows"]}])
    assert (await dashboard.channel_raid_browser(request(), mutual=True)).status_code == 403
    assert api.await_count == 1


@pytest.mark.asyncio
async def test_recommendations_blend_followed_and_similar_channels_without_duplicates(monkeypatch):
    followed = dict(stream("2", 3), game_id="other", language="en", tags=[])
    similar = dict(stream("3", 10), game_id="game", language="ja", tags=["VTuber"])
    less_similar = dict(stream("4", 10000), game_id="game", language="en", tags=[])
    api = runtime(monkeypatch, [
        {"data": [{"game_id": "game", "broadcaster_language": "ja", "tags": ["VTuber"]}]},
        {"data": []},
        {"data": [followed], "pagination": {}},
        {"data": [less_similar, similar, followed], "pagination": {"cursor": "next"}},
    ])
    response = await dashboard.channel_raid_browser(request(), recommended=True)
    channels = json.loads(response.body)["channels"]
    assert [item["id"] for item in channels] == ["3", "4", "2"]
    assert channels[2]["followed"] is True
    assert "Shared tags" in channels[0]["reasons"]
    assert "Both VTubers" in channels[0]["reasons"]
    assert channels[0]["relevance"] > channels[2]["relevance"]
    assert next(call.args[0] for call in api.await_args_list if call.args[0].path == "streams").params["game_id"] == "game"


@pytest.mark.asyncio
async def test_recent_raiders_join_recommendations_and_gain_a_recency_boost(monkeypatch):
    monkeypatch.setattr(dashboard, "get_suggested_streamers", AsyncMock(return_value=([], "cached")))
    monkeypatch.setattr(dashboard, "raid_browser_followed_streams", AsyncMock(return_value=[]))
    monkeypatch.setattr(dashboard, "raid_browser_team_streams", AsyncMock(return_value=([], {})))
    recent = AsyncMock(return_value={"3": 1, "4": 0.5})
    monkeypatch.setattr(dashboard, "recent_incoming_raids", recent)
    api = runtime(monkeypatch, [
        {"data": [{"game_id": "123", "tags": [], "broadcaster_language": "en"}]},
        {"data": [stream("3", 1), stream("4", 200)]},
        {"data": [stream("2", 1000), stream("3", 1)], "pagination": {}},
    ])
    payload = json.loads((await dashboard.channel_raid_browser(request(), sort="for_you")).body)
    assert [item["id"] for item in payload["channels"]] == ["3", "4", "2"]
    assert payload["channels"][0]["recent_raider"] is True
    assert "Raided you recently" in payload["channels"][0]["reasons"]
    recent.assert_awaited_once_with(None, "1")
    assert next(call.args[0] for call in api.await_args_list if call.args[0].path == "streams").params["user_id"] == ["3", "4"]


@pytest.mark.asyncio
async def test_for_you_continues_after_current_category_is_exhausted(monkeypatch):
    monkeypatch.setattr(dashboard, "get_suggested_streamers", AsyncMock(return_value=([], "cached")))
    monkeypatch.setattr(dashboard, "raid_browser_followed_streams", AsyncMock(return_value=[]))
    monkeypatch.setattr(dashboard, "raid_browser_team_streams", AsyncMock(return_value=([], {})))
    source = AsyncMock(side_effect=AssertionError("For You must use official pagination"))
    monkeypatch.setattr(dashboard, "get_sorted_directory", source)
    api = runtime(monkeypatch, [
        {"data": [{"game_id": "123", "tags": ["VTuber"], "broadcaster_language": "en"}]},
        {"data": [stream("2")], "pagination": {}},
        {"data": [stream("3")], "pagination": {"cursor": "more"}}, {"data": [stream("4")]},
    ])
    first = json.loads((await dashboard.channel_raid_browser(request(), sort="for_you")).body)
    assert first["cursor"] == "fy-discovery:"
    second = json.loads((await dashboard.channel_raid_browser(request(), sort="for_you", after=first["cursor"])).body)
    assert second["cursor"] == "fy-discovery:official:1:more"
    assert [item["id"] for item in second["channels"]] == ["3"]
    assert api.await_args_list[-2].args[0].params == {"first": 100, "language": "en"}
    third = json.loads((await dashboard.channel_raid_browser(request(), sort="for_you", after=second["cursor"])).body)
    assert third["cursor"] == ""
    source.assert_not_awaited()
    assert any(call.args[0].params == {"first": 100, "after": "more", "language": "en"} for call in api.await_args_list)
    assert [item["id"] for item in third["channels"]] == ["4"]


@pytest.mark.asyncio
async def test_for_you_does_not_broaden_an_explicit_category_filter(monkeypatch):
    monkeypatch.setattr(dashboard, "get_suggested_streamers", AsyncMock(return_value=([], "cached")))
    monkeypatch.setattr(dashboard, "raid_browser_followed_streams", AsyncMock(return_value=[]))
    monkeypatch.setattr(dashboard, "raid_browser_team_streams", AsyncMock(return_value=([], {})))
    source = AsyncMock()
    monkeypatch.setattr(dashboard, "get_sorted_directory", source)
    runtime(monkeypatch, [
        {"data": [{"game_id": "123", "tags": ["VTuber"], "broadcaster_language": "en"}]},
        {"data": [dict(stream("2"), game_id="123")], "pagination": {}},
    ])
    payload = json.loads((await dashboard.channel_raid_browser(request(), sort="for_you", category_id="123")).body)
    assert payload["cursor"] == ""
    source.assert_not_awaited()


@pytest.mark.asyncio
async def test_recommendations_with_no_channel_context_are_followed_only(monkeypatch):
    api = runtime(monkeypatch, [{"data": [{"game_id": "", "tags": []}]}, {"data": []},
                                {"data": [stream()], "pagination": {}}])
    response = await dashboard.channel_raid_browser(request(), recommended=True)
    assert len(json.loads(response.body)["channels"]) == 1
    assert api.await_count == 4


@pytest.mark.asyncio
async def test_personalized_followed_source_paginates_and_caches(monkeypatch):
    api = runtime(monkeypatch, [{"data": [stream("2")], "pagination": {"cursor": "next"}},
                                {"data": [stream("3")], "pagination": {}}])
    bot = dashboard.get_bot()
    first = await dashboard.raid_browser_followed_streams(bot, "1")
    second = await dashboard.raid_browser_followed_streams(bot, "1")
    assert [item["user_id"] for item in first] == ["2", "3"]
    assert first == second
    assert api.await_count == 2


@pytest.mark.asyncio
async def test_same_team_loads_live_members_of_all_teams_and_deduplicates(monkeypatch):
    api = runtime(monkeypatch, [
        {"data": [{"team_id": "t1"}, {"team_id": "t2"}]},
        {"data": [{"team_display_name": "Team One", "users": [{"user_id": "1"}, {"user_id": "2"}, {"user_id": "3"}]}]},
        {"data": [{"team_display_name": "Team Two", "users": [{"user_id": "2"}]}]},
        {"data": [stream("2")]},
    ])
    response = await dashboard.channel_raid_browser(request(), same_team=True)
    channels = json.loads(response.body)["channels"]
    assert len(channels) == 1
    assert channels[0]["teams"] == ["Team One", "Team Two"]
    assert "Same stream team" in channels[0]["reasons"]
    assert next(call.args[0] for call in api.await_args_list if call.args[0].path == "streams").params["user_id"] == ["2", "3"]


@pytest.mark.asyncio
async def test_recommendations_include_unfollowed_teammate_in_different_category(monkeypatch):
    teammate = dict(stream("2", 2), game_id="different", language="en", tags=[])
    discovery = dict(stream("3", 10000), game_id="game", language="en", tags=[])
    api = runtime(monkeypatch, [
        {"data": [{"game_id": "game", "broadcaster_language": "en", "tags": []}]},
        {"data": [{"team_id": "team"}]},
        {"data": [{"team_display_name": "Our Team", "users": [{"user_id": "2"}]}]},
        {"data": [teammate]},
        {"data": [], "pagination": {}},
        {"data": [discovery], "pagination": {}},
    ])
    response = await dashboard.channel_raid_browser(request(), recommended=True)
    channels = json.loads(response.body)["channels"]
    assert [channel["id"] for channel in channels] == ["3", "2"]
    assert channels[1]["followed"] is False
    assert channels[1]["teams"] == ["Our Team"]


@pytest.mark.asyncio
async def test_team_filter_with_no_memberships_does_not_fetch_global_streams(monkeypatch):
    api = runtime(monkeypatch, [{"data": []}])
    response = await dashboard.channel_raid_browser(request(), same_team=True)
    assert json.loads(response.body)["channels"] == []
    assert api.await_count == 1


@pytest.mark.asyncio
async def test_live_favorites_are_fetched_independently_of_discovery(monkeypatch):
    api = runtime(monkeypatch, [{"data": [], "pagination": {}}, {"data": [stream("2")]}])
    response = await dashboard.channel_raid_browser(request(), favorites="2")
    assert [item["id"] for item in json.loads(response.body)["channels"]] == ["2"]
    assert api.await_args_list[-2].args[0].params["user_id"] == ["2"]


@pytest.mark.asyncio
async def test_favorites_respect_explicit_following_filter(monkeypatch):
    runtime(monkeypatch, [{"data": [stream("3")], "pagination": {}}, {"data": [stream("2")]}])
    response = await dashboard.channel_raid_browser(request(), following=True, favorites="2")
    assert [item["id"] for item in json.loads(response.body)["channels"]] == ["3"]


@pytest.mark.asyncio
async def test_invalid_favorite_ids_are_rejected_before_fetching(monkeypatch):
    api = runtime(monkeypatch, [])
    assert (await dashboard.channel_raid_browser(request(), favorites="not-an-id")).status_code == 400
    api.assert_not_awaited()


@pytest.mark.asyncio
async def test_individual_tags_cannot_exceed_25_characters(monkeypatch):
    api = runtime(monkeypatch, [])
    response = await dashboard.channel_raid_browser(request(), tags="a" * 26)
    assert response.status_code == 400
    assert "25 characters" in json.loads(response.body)["detail"]
    api.assert_not_awaited()


@pytest.mark.asyncio
async def test_multiple_25_character_tags_are_accepted(monkeypatch):
    runtime(monkeypatch, [{"data": [], "pagination": {}}])
    assert (await dashboard.channel_raid_browser(request(), tags="a" * 25 + "," + "b" * 25)).status_code == 200


@pytest.mark.asyncio
async def test_verified_status_comes_from_twitch_partner_type_not_affiliate(monkeypatch):
    api = runtime(monkeypatch, [{"data": [stream("2"), stream("3")], "pagination": {}}], profiles=[
        {"id": "2", "broadcaster_type": "partner"}, {"id": "3", "broadcaster_type": "affiliate"}])
    response = await dashboard.channel_raid_browser(request())
    channels = {channel["id"]: channel for channel in json.loads(response.body)["channels"]}
    assert channels["2"]["verified"] is True
    assert channels["3"]["verified"] is False
    assert api.await_args_list[-1].args[0].path == "users"


@pytest.mark.asyncio
async def test_failed_partner_lookup_keeps_results_without_guessing_verification(monkeypatch):
    runtime(monkeypatch, [{"data": [stream()], "pagination": {}}], profiles=RuntimeError("Unavailable"))
    response = await dashboard.channel_raid_browser(request())
    assert response.status_code == 200
    assert json.loads(response.body)["channels"][0]["verified"] is None


@pytest.mark.asyncio
async def test_favorites_tab_uses_only_saved_ids_without_follow_permissions(monkeypatch):
    api = runtime(monkeypatch, [{"data": [stream("2")]}])
    response = await dashboard.channel_raid_browser(request(), favorites="2", favorites_only=True, recommended=True, sort="viewers_desc")
    assert [item["id"] for item in json.loads(response.body)["channels"]] == ["2"]
    assert all(call.args[0].path in {"streams", "users"} for call in api.await_args_list)


@pytest.mark.asyncio
async def test_favorites_and_browse_share_for_you_order_and_score_breakdowns(monkeypatch):
    runtime(monkeypatch, [])
    bot = dashboard.get_bot()
    own = bot.services.broadcasters.get_broadcasters()["1"]
    own.viewer_count = 42
    bot.services.broadcasters.get_broadcasters = lambda: {"1": own}
    favorites = [dict(stream("2", 500), game_id="other", language="en", tags=[]),
                 dict(stream("3", 42), game_id="game", language="en", tags=["VTuber", "Art"])]
    other = dict(stream("4", 100), game_id="game", language="en", tags=[])

    async def respond(route):
        if route.path == "channels":
            return {"data": [{"game_id": "game", "broadcaster_language": "en", "tags": ["VTuber", "Art"]}]}
        if route.path == "streams":
            ids = route.params.get("user_id")
            return {"data": [item for item in [*favorites, other] if not ids or item["user_id"] in ids],
                    "pagination": {} if ids else {"cursor": "next"}}
        if route.path == "users":
            return {"data": []}
        raise AssertionError(route.path)

    bot._http.request_json = AsyncMock(side_effect=respond)
    monkeypatch.setattr(dashboard, "raid_browser_followed_streams", AsyncMock(return_value=favorites))
    monkeypatch.setattr(dashboard, "get_suggested_streamers", AsyncMock(return_value=([{"id": "3"}], None)))
    monkeypatch.setattr(dashboard, "raid_browser_team_streams", AsyncMock(return_value=([favorites[1]], {"3": ["Team"]})))
    monkeypatch.setattr(dashboard, "recent_incoming_raids", AsyncMock(return_value={"3": .5}))
    monkeypatch.setattr(dashboard, "raid_browser_channel_sizes", AsyncMock(return_value={"1": 1000, "2": 10000, "3": 1000}))
    monkeypatch.setattr(dashboard, "raid_browser_relationships", AsyncMock(return_value={
        "2": {"followed": True, "mutual": False}, "3": {"followed": True, "mutual": True}}))
    browse_response = await dashboard.channel_raid_browser(request(), favorites="2,3", sort="for_you")
    favorites_response = await dashboard.channel_raid_browser(request(), favorites="2,3", favorites_only=True, sort="for_you")
    assert browse_response.status_code == favorites_response.status_code == 200
    browse = [item for item in json.loads(browse_response.body)["channels"] if item["id"] in {"2", "3"}]
    saved = json.loads(favorites_response.body)["channels"]
    assert [item["id"] for item in browse] == [item["id"] for item in saved] == ["3", "2"]
    for first, second in zip(browse, saved):
        assert first["relevance"] == second["relevance"] == sum(second["match_breakdown"].values())
        assert first["match_breakdown"] == second["match_breakdown"]
    assert all(saved[0]["match_breakdown"][label] > 0 for label in (
        "Same category", "Same team", "Both VTubers", "Shared tags", "Following", "Mutual following",
        "Suggested", "Same language", "Recent raid", "Similar viewer count", "Similar channel size"))


@pytest.mark.asyncio
async def test_favorites_for_you_keeps_compatibility_ranking_when_follow_scopes_are_missing(monkeypatch):
    runtime(monkeypatch, [
        {"data": [{"game_id": "game", "broadcaster_language": "en", "tags": []}]},
        {"data": [dict(stream("2", 500), game_id="other"), dict(stream("3", 10), game_id="game")]},
    ])
    monkeypatch.setattr(dashboard, "get_suggested_streamers", AsyncMock(return_value=([], None)))
    monkeypatch.setattr(dashboard, "raid_browser_team_streams", AsyncMock(return_value=([], {})))
    monkeypatch.setattr(dashboard, "raid_browser_followed_streams", AsyncMock(
        side_effect=dashboard.HTTPException("Forbidden", status=403, extra="")))
    response = await dashboard.channel_raid_browser(request(), favorites="2,3", favorites_only=True, sort="for_you")
    assert response.status_code == 200
    channels = json.loads(response.body)["channels"]
    assert [item["id"] for item in channels] == ["3", "2"]
    assert channels[0]["match_breakdown"]["Same category"] == 400


@pytest.mark.asyncio
async def test_blacklisted_channels_are_excluded_from_all_results(monkeypatch):
    runtime(monkeypatch, [{"data": [stream("2"), stream("3")], "pagination": {}}])
    response = await dashboard.channel_raid_browser(request(), blocked="2")
    assert [item["id"] for item in json.loads(response.body)["channels"]] == ["3"]


@pytest.mark.asyncio
async def test_saved_list_manager_resolves_offline_channels_without_stream_lookup(monkeypatch):
    api = runtime(monkeypatch, [], profiles=[{"id": "2", "login": "viewer2", "display_name": "Viewer2"}])
    response = await dashboard.channel_raid_browser_lists(request(), ids="2")
    assert json.loads(response.body)["channels"][0]["login"] == "viewer2"
    assert api.await_args.args[0].path == "users"
    assert api.await_args.args[0].token_for == "1"


@pytest.mark.asyncio
async def test_saved_list_manager_requires_auth_and_valid_ids(monkeypatch):
    api = runtime(monkeypatch, [])
    assert (await dashboard.channel_raid_browser_lists(request(None), ids="2")).status_code == 401
    assert (await dashboard.channel_raid_browser_lists(request(), ids="bad-id")).status_code == 400
    api.assert_not_awaited()
