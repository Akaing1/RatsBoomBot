import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from web.admin.auth import CSRF_SESSION_KEY
from web.channel.auth import CHANNEL_USER_ID_KEY
from web.channel.routers import engagement


def request(user="1"):
    return Request({"type": "http", "session": {CHANNEL_USER_ID_KEY: user, CSRF_SESSION_KEY: "csrf"} if user else {}})


@pytest.fixture
def api(monkeypatch):
    call = AsyncMock(return_value={"data": [{"id": "new"}]})
    bot = SimpleNamespace(_http=SimpleNamespace(request_json=call), services=SimpleNamespace(
        broadcasters=SimpleNamespace(get_broadcasters=lambda: {"1": {}})))
    monkeypatch.setattr(engagement, "get_bot", lambda: bot)
    return call


@pytest.mark.asyncio
@pytest.mark.parametrize("kind, field, window", [("polls", "choices", "duration"), ("predictions", "outcomes", "prediction_window")])
async def test_create_sends_channel_scoped_twitch_payload(api, kind, field, window):
    result = await engagement.create_engagement(request(), kind, " Test? ", '[" Yes ", "No"]', 120, "csrf")
    assert result.status_code == 201
    route = api.call_args.args[0]
    assert route.path == kind and route.token_for == "1" and route.method == "POST"
    expected = {"broadcaster_id": "1", "title": "Test?", field: [{"title": "Yes"}, {"title": "No"}], window: 120}
    if kind == "polls":
        expected["channel_points_voting_enabled"] = False
    assert route.json == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("cost", [1, 250, 1_000_000])
async def test_polls_allow_additional_votes_at_the_selected_cost(api, cost):
    result = await engagement.create_engagement(request(), "polls", "Question?", '["A","B"]', 120, "csrf",
        channel_points_voting_enabled=True, channel_points_per_vote=cost)
    assert result.status_code == 201
    assert api.call_args.args[0].json["channel_points_voting_enabled"] is True
    assert api.call_args.args[0].json["channel_points_per_vote"] == cost


@pytest.mark.asyncio
@pytest.mark.parametrize("cost", [None, 0, -1, 1_000_001, True])
async def test_additional_votes_require_valid_cost_before_calling_twitch(api, cost):
    result = await engagement.create_engagement(request(), "polls", "Question?", '["A","B"]', 120, "csrf",
        channel_points_voting_enabled=True, channel_points_per_vote=cost)
    assert result.status_code == 400
    api.assert_not_awaited()


@pytest.mark.asyncio
async def test_disabled_additional_votes_never_send_a_cost_and_predictions_reject_them(api):
    result = await engagement.create_engagement(request(), "polls", "Question?", '["A","B"]', 120, "csrf",
        channel_points_voting_enabled=False, channel_points_per_vote=250)
    assert result.status_code == 201
    assert api.call_args.args[0].json["channel_points_voting_enabled"] is False
    assert "channel_points_per_vote" not in api.call_args.args[0].json
    api.reset_mock()
    result = await engagement.create_engagement(request(), "predictions", "Question?", '["A","B"]', 120, "csrf",
        channel_points_voting_enabled=True, channel_points_per_vote=250)
    assert result.status_code == 400
    api.assert_not_awaited()


@pytest.mark.asyncio
async def test_recent_polls_preserve_additional_vote_settings(api):
    api.return_value = {"data": [{"id": "old", "title": "Question?", "choices": [{"title": "A"}, {"title": "B"}],
        "duration": 120, "channel_points_voting_enabled": True, "channel_points_per_vote": 250}]}
    item = json.loads((await engagement.recent_engagement(request(), "polls")).body)["items"][0]
    assert item["channel_points_voting_enabled"] is True
    assert item["channel_points_per_vote"] == 250


@pytest.mark.asyncio
async def test_predictions_accept_all_ten_choices(api):
    choices = [f"Choice {index}" for index in range(10)]
    result = await engagement.create_engagement(request(), "predictions", "Question?", json.dumps(choices), 120, "csrf")
    assert result.status_code == 201
    assert [option["title"] for option in api.call_args.args[0].json["outcomes"]] == choices


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,title,choices,duration", [
    ("invalid", "Question", '["Yes","No"]', 120),
    ("predictions", "x" * 46, '["Yes","No"]', 120),
    ("polls", "x" * 61, '["Yes","No"]', 120),
    ("polls", "Question", json.dumps([str(i) for i in range(6)]), 120),
    ("predictions", "Question", json.dumps([str(i) for i in range(11)]), 120),
    ("polls", "Question", '["Yes"]', 120),
    ("polls", "Question", '["Yes", "yes"]', 120),
    ("polls", "Question", '["", "No"]', 120),
    ("polls", "Question", '[1, "No"]', 120),
    ("polls", "Question", '{}', 120),
    ("polls", "Question", 'invalid', 120),
    ("polls", "Question", '["Yes","No"]', 14),
    ("predictions", "Question", '["Yes","No"]', 29),
    ("predictions", "Question", '["Yes","No"]', 1801),
])
async def test_invalid_drafts_never_reach_twitch(api, kind, title, choices, duration):
    assert (await engagement.create_engagement(request(), kind, title, choices, duration, "csrf")).status_code == 400
    api.assert_not_awaited()


@pytest.mark.asyncio
async def test_auth_channel_and_csrf_checks(api):
    assert (await engagement.recent_engagement(request(None), "polls")).status_code == 401
    assert (await engagement.recent_engagement(request("other"), "polls")).status_code == 404
    assert (await engagement.create_engagement(request(None), "polls", "Test", '["A","B"]', 120, "csrf")).status_code == 401
    with pytest.raises(HTTPException):
        await engagement.create_engagement(request(), "polls", "Test", '["A","B"]', 120, "bad")
    api.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,field,window", [("polls", "choices", "duration"), ("predictions", "outcomes", "prediction_window")])
async def test_recent_returns_reusable_templates_without_viewer_data(api, kind, field, window):
    api.return_value = {"data": [{"id": "old", "title": "Question?", field: [{"title": "A", "top_predictors": ["private"]}, {"title": "B"}], window: 60, "status": "COMPLETED"}]}
    result = json.loads((await engagement.recent_engagement(request(), kind)).body)
    assert result["items"][0]["choices"] == ["A", "B"]
    assert result["items"][0]["duration"] == 60
    assert "private" not in json.dumps(result)
    assert api.call_args.args[0].params == {"broadcaster_id": "1", "first": 20}


@pytest.mark.asyncio
async def test_twitch_failures_do_not_leak_details_or_retry_creation(api):
    error = RuntimeError("secret token")
    error.status = 403
    api.side_effect = error
    response = await engagement.create_engagement(request(), "predictions", "Question?", '["A","B"]', 120, "csrf")
    assert response.status_code == 403
    assert "Reconnect Twitch" in json.loads(response.body)["detail"]
    assert "secret" not in response.body.decode()
    assert api.await_count == 1


def running_item(kind, status="ACTIVE"):
    field = "choices" if kind == "polls" else "outcomes"
    return {"id": "item-1", "title": "Question?", "status": status,
        "duration" if kind == "polls" else "prediction_window": 120,
        field: [{"id": "a", "title": "Yes", "votes": 3, "users": 2, "channel_points": 200, "top_predictors": [{"user_name": "private"}]},
                {"id": "b", "title": "No", "votes": 1, "users": 1, "channel_points": 50}]}


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["polls", "predictions"])
async def test_summary_is_channel_scoped_and_only_exposes_aggregate_results(api, kind):
    api.return_value = {"data": [running_item(kind)]}
    response = await engagement.get_engagement(request(), kind, "item-1")
    item = json.loads(response.body)["item"]
    assert item["options"][0]["votes"] == (3 if kind == "polls" else 2)
    assert item["options"][0]["points"] == 200
    assert "private" not in response.body.decode()
    assert api.call_args.args[0].params == {"broadcaster_id": "1", "id": "item-1"}


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["polls", "predictions"])
async def test_latest_summary_prefers_current_then_most_recent(api, kind):
    newest = {**running_item(kind, "COMPLETED" if kind == "polls" else "RESOLVED"),
        "id": "newest", "created_at": "2026-10-27T12:00:00Z"}
    older = {**newest, "id": "older", "created_at": "2026-10-26T12:00:00Z"}
    current = {**older, "id": "current", "status": "ACTIVE"}
    api.return_value = {"data": [older, newest, current]}
    response = await engagement.get_engagement(request(), kind, "latest")
    assert json.loads(response.body)["item"]["id"] == "current"
    assert api.call_args.args[0].params == {"broadcaster_id": "1", "first": 20}
    if kind == "predictions":
        current["status"] = "LOCKED"
        response = await engagement.get_engagement(request(), kind, "latest")
        assert json.loads(response.body)["item"]["id"] == "current"
    api.return_value = {"data": [older, newest]}
    response = await engagement.get_engagement(request(), kind, "latest")
    assert json.loads(response.body)["item"]["id"] == "newest"
    api.return_value = {"data": []}
    assert (await engagement.get_engagement(request(), kind, "latest")).status_code == 404


@pytest.mark.asyncio
async def test_latest_summary_cannot_be_used_as_a_mutation_target(api):
    response = await engagement.manage_engagement(request(), "polls", "latest", "close", "csrf")
    assert response.status_code == 400
    api.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,action,expected", [
    ("polls", "close", "TERMINATED"), ("polls", "delete", "ARCHIVED"),
    ("predictions", "close", "LOCKED"), ("predictions", "resolve", "RESOLVED"),
    ("predictions", "delete", "CANCELED"),
])
async def test_management_actions_use_correct_twitch_states(api, kind, action, expected):
    api.side_effect = [{"data": [running_item(kind)]}, {"data": [running_item(kind, expected)]}]
    response = await engagement.manage_engagement(request(), kind, "item-1", action, "csrf", winning_outcome_id="a")
    assert response.status_code == 200
    route = api.call_args.args[0]
    assert route.method == "PATCH" and route.token_for == "1"
    assert route.json["status"] == expected
    assert route.json["broadcaster_id"] == "1" and route.json["id"] == "item-1"
    assert ("winning_outcome_id" in route.json) == (action == "resolve")
    assert json.loads(response.body)["dismissed"] == (action == "delete")


@pytest.mark.asyncio
async def test_resolving_rejects_foreign_outcomes_and_completed_predictions(api):
    api.return_value = {"data": [running_item("predictions")]}
    response = await engagement.manage_engagement(request(), "predictions", "item-1", "resolve", "csrf", winning_outcome_id="foreign")
    assert response.status_code == 400 and api.await_count == 1
    api.reset_mock(); api.return_value = {"data": [running_item("predictions", "RESOLVED")]}
    response = await engagement.manage_engagement(request(), "predictions", "item-1", "resolve", "csrf", winning_outcome_id="a")
    assert response.status_code == 409 and api.await_count == 1


@pytest.mark.asyncio
async def test_completed_history_can_only_be_dismissed_locally(api):
    api.return_value = {"data": [running_item("polls", "COMPLETED")]}
    response = await engagement.manage_engagement(request(), "polls", "item-1", "delete", "csrf")
    assert response.status_code == 200
    assert json.loads(response.body)["dismissed"] is True
    assert api.await_count == 1 and api.call_args.args[0].method == "GET"


@pytest.mark.asyncio
async def test_management_authentication_csrf_missing_items_and_invalid_ids(api):
    assert (await engagement.get_engagement(request(None), "polls", "item-1")).status_code == 401
    assert (await engagement.get_engagement(request(), "polls", "../bad")).status_code == 400
    with pytest.raises(HTTPException):
        await engagement.manage_engagement(request(), "polls", "item-1", "delete", "bad")
    api.assert_not_awaited()
    api.return_value = {"data": []}
    assert (await engagement.manage_engagement(request(), "polls", "item-1", "delete", "csrf")).status_code == 404
    assert api.await_count == 1


def test_poll_summary_preserves_settings_for_running_again():
    item = {**running_item('polls'), 'channel_points_voting_enabled': True, 'channel_points_per_vote': 250}
    summary = engagement.engagement_summary(item, 'polls')
    assert summary['channel_points_voting_enabled'] is True
    assert summary['channel_points_per_vote'] == 250
    assert 'channel_points_voting_enabled' not in engagement.engagement_summary(running_item('predictions'), 'predictions')
