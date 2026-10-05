from types import SimpleNamespace
from unittest.mock import AsyncMock
import time

import pytest

from web.shared import category_relevance
from web.channel.routers import dashboard


class Response:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def raise_for_status(self):
        pass

    async def json(self):
        return [
            {"id": 100, "game_status": {"status": "Delisted"}},
            {"id": 200, "game_status": {"status": "Released"}, "first_release_date": int(time.time()) - 86400,
             "cover": 123, "rating_count": 1, "aggregated_rating_count": 1},
            {"id": 300},
        ]


class Session(Response):
    def post(self, url, **kwargs):
        if url.endswith("/popularity_primitives"):
            return PopularityResponse()
        assert url == "https://api.igdb.com/v4/games"
        assert "game_status.status" in kwargs["data"]
        return Response()


class PopularityResponse(Response):
    async def json(self):
        return [{"game_id": 200, "popularity_type": type_, "value": 1, "calculated_at": int(time.time())}
                for type_ in (2, 3, 4)]


@pytest.mark.asyncio
async def test_only_confirmed_delisted_games_are_grouped_and_results_are_cached(monkeypatch):
    monkeypatch.setattr(category_relevance.aiohttp, "ClientSession", lambda **kwargs: Session())
    bot = SimpleNamespace(
        _http=SimpleNamespace(_client_id="client", _app_token="token"),
        fetch_games=AsyncMock(return_value=[
            SimpleNamespace(id="old-peak", igdb_id="100"),
            SimpleNamespace(id="new-peak", igdb_id="200"),
            SimpleNamespace(id="unknown", igdb_id="300"),
            SimpleNamespace(id="no-mapping", igdb_id=""),
        ])
    )
    games = [{"id": id_, "name": "Peak"} for id_ in ["old-peak", "new-peak", "unknown", "no-mapping"]]
    assert await category_relevance.low_relevance_category_ids(bot, games, "channel") == {"old-peak", "unknown"}
    assert await category_relevance.low_relevance_category_ids(bot, games, "channel") == {"old-peak", "unknown"}
    bot.fetch_games.assert_awaited_once()


@pytest.mark.asyncio
async def test_lookup_failure_or_missing_credentials_keeps_every_game_visible():
    games = [{"id": "123", "name": "New game"}]
    bot = SimpleNamespace(_http=SimpleNamespace(_client_id="client", _app_token="token"),
                          fetch_games=AsyncMock(side_effect=RuntimeError("Unavailable")))
    assert await category_relevance.low_relevance_category_ids(bot, games, "channel") == set()
    assert await category_relevance.low_relevance_category_ids(bot, games, "channel") == set()
    bot.fetch_games.assert_awaited_once()
    assert await category_relevance.low_relevance_category_ids(SimpleNamespace(), games, "channel") == set()


@pytest.mark.asyncio
@pytest.mark.parametrize("environment,ttl", [("local", 3600), ("uat", 86400), ("production", 86400)])
@pytest.mark.parametrize("failed", [False, True])
async def test_lookup_cache_duration_by_environment(monkeypatch, environment, ttl, failed):
    monkeypatch.setattr(category_relevance.settings, "ENVIRONMENT", environment)
    clock = [1000.0]
    monkeypatch.setattr(category_relevance.time, "monotonic", lambda: clock[0])
    bot = SimpleNamespace(
        _http=SimpleNamespace(_client_id="client", _app_token="token"),
        fetch_games=AsyncMock(return_value=[], side_effect=RuntimeError("Unavailable") if failed else None),
    )
    games = [{"id": "123"}]
    expected_ttl = 60 if failed and environment == "local" else ttl
    await category_relevance.low_relevance_category_ids(bot, games, "channel")
    clock[0] += expected_ttl - 1
    await category_relevance.low_relevance_category_ids(bot, games, "channel")
    bot.fetch_games.assert_awaited_once()
    clock[0] += 1
    await category_relevance.low_relevance_category_ids(bot, games, "channel")
    assert bot.fetch_games.await_count == 2


@pytest.mark.asyncio
async def test_picker_groups_by_id_not_name_and_preserves_ranking(monkeypatch):
    monkeypatch.setattr(dashboard, "low_relevance_category_ids", AsyncMock(return_value={"old-peak"}))
    new_game = {"id": "new-peak", "name": "Peak"}
    old_game = {"id": "old-peak", "name": "Peak"}
    unknown_game = {"id": "unknown", "name": "New indie game"}
    assert await dashboard.category_picker_results(SimpleNamespace(), "channel", [new_game, old_game, unknown_game]) == {
        "games": [new_game, unknown_game], "more_games": [old_game]
    }


@pytest.mark.parametrize("override,interest,expected", [
    ({}, {2: 0, 3: 0, 4: 0}, True),
    ({}, {2: 0, 3: 0, 4: 0.000001}, True),
    ({}, {2: 0.00001, 3: 0.00001, 4: 0.00001}, True),
    ({}, {2: 0, 3: 0, 4: 0.00002}, False),
    ({}, {2: 0, 3: 0}, False),
    ({}, {}, False),
    ({"cover": None, "artworks": []}, {2: 1, 3: 1, 4: 1}, True),
    ({"rating_count": 0, "aggregated_rating_count": 0}, {2: 1, 3: 1, 4: 1}, True),
    ({"rating_count": None}, {2: 1, 3: 1, 4: 1}, False),
    ({"first_release_date": None, "release_dates": []}, {2: 1, 3: 1, 4: 1}, True),
    ({"game_status": {"status": "Delisted"}}, {2: 1, 3: 1, 4: 1}, True),
    ({"game_status": {"status": "Released"}}, {2: 1, 3: 1, 4: 1}, False),
])
def test_any_low_relevance_signal_can_group_older_games(override, interest, expected):
    game = {"rating_count": 10, "aggregated_rating_count": 10, "first_release_date": 123,
            "release_dates": [{"date": 123}], "cover": 123, "artworks": [123]}
    game.update(override)
    assert category_relevance.is_low_relevance(game, interest) is expected


def test_successfully_fetched_sparse_solitaire_entry_has_no_recorded_metadata():
    game = {"id": 87084, "name": "i3Peaks - Tri Peaks Solitaire"}
    assert category_relevance.is_low_relevance(game, {2: 0, 3: 0, 4: 0}) is True
    assert category_relevance.is_low_relevance(game, {}) is True
    assert category_relevance.is_low_relevance(None, {2: 0, 3: 0, 4: 0}) is False


@pytest.mark.asyncio
async def test_failed_popularity_lookup_does_not_override_other_or_signals(monkeypatch):
    class UnavailablePopularity(Session):
        def post(self, url, **kwargs):
            if url.endswith("/popularity_primitives"):
                raise RuntimeError("Popularity unavailable")
            return super().post(url, **kwargs)

    monkeypatch.setattr(category_relevance.aiohttp, "ClientSession", lambda **kwargs: UnavailablePopularity())
    bot = SimpleNamespace(_http=SimpleNamespace(_client_id="client", _app_token="token"),
                          fetch_games=AsyncMock(return_value=[SimpleNamespace(id="sparse-game", igdb_id="300")]))
    assert await category_relevance.low_relevance_category_ids(bot, [{"id": "sparse-game"}], "channel") == {"sparse-game"}


@pytest.mark.parametrize("days", [0, 364, 365, 366])
def test_release_age_does_not_override_filter_signals(monkeypatch, days):
    now = 1800000000
    monkeypatch.setattr(category_relevance.time, "time", lambda: now)
    game = {"game_status": {"status": "Delisted"}, "first_release_date": now - days * 86400}
    assert category_relevance.is_low_relevance(game, {2: 0, 3: 0, 4: 0}) is True


def test_recent_platform_release_does_not_override_other_signals():
    game = {"first_release_date": 123, "release_dates": [{"date": time.time() - 86400}]}
    assert category_relevance.is_low_relevance(game, {2: 0, 3: 0, 4: 0}) is True
