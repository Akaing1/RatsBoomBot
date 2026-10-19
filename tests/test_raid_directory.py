import json
from types import SimpleNamespace

import httpx
import pytest

from web.shared import raid_directory as directory


@pytest.mark.asyncio
@pytest.mark.parametrize("sort,category,expected", [("viewers_asc", "", "VIEWER_COUNT_ASC"), ("uptime_asc", "509658", "RECENT")])
async def test_source_sorted_directory_passes_filters_and_cursor_without_credentials(monkeypatch, sort, category, expected):
    requests = []
    def respond(request):
        requests.append(request)
        connection = {"edges": [{"cursor": "next", "node": {"broadcaster": {"id": "2"}}}], "pageInfo": {"hasNextPage": True}}
        return httpx.Response(200, json={"data": {"game": {"streams": connection}} if category else {"streams": connection}})
    real_client = httpx.AsyncClient
    monkeypatch.setattr(directory.httpx, "AsyncClient", lambda **kwargs:
        real_client(transport=httpx.MockTransport(respond), **kwargs))
    bot = SimpleNamespace()
    result = await directory.get_sorted_directory(bot, sort=sort, after="previous", category_id=category, language="en", tags=["VTuber"])
    assert result == {"ids": ["2"], "cursor": "next"}
    request = requests[0]
    assert "authorization" not in request.headers and "cookie" not in request.headers
    variables = json.loads(request.content)["variables"]
    assert variables["first"] == 30
    assert variables["after"] == "previous"
    assert variables["options"]["sort"] == expected
    assert variables["options"]["freeformTags"] == ["VTuber"]
    assert variables["options"]["languages"] == ["en" if category else "EN"]
    await directory.get_sorted_directory(bot, sort=sort, after="previous", category_id=category, language="en", tags=["VTuber"])
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_all_mode_pushes_every_selected_tag_into_twitch_first_page(monkeypatch):
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"data": {"streams": {"edges": [], "pageInfo": {"hasNextPage": False}}}})
    real_client = httpx.AsyncClient
    monkeypatch.setattr(directory.httpx, "AsyncClient", lambda **kwargs:
        real_client(transport=httpx.MockTransport(respond), **kwargs))
    await directory.get_sorted_directory(SimpleNamespace(), sort="viewers_desc", tags=["VTuber", "Artist"], tag_match="all")
    variables = json.loads(requests[0].content)["variables"]
    assert variables["first"] == 30
    assert variables["after"] is None
    assert variables["options"]["freeformTags"] == ["VTuber", "Artist"]


@pytest.mark.asyncio
async def test_directory_error_does_not_cache_a_fake_empty_success(monkeypatch):
    real_client = httpx.AsyncClient
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"errors": [{"message": "Unavailable"}]})
    monkeypatch.setattr(directory.httpx, "AsyncClient", lambda **kwargs:
        real_client(transport=httpx.MockTransport(respond), **kwargs))
    bot = SimpleNamespace()
    for _ in range(2):
        with pytest.raises(ValueError):
            await directory.get_sorted_directory(bot, sort="viewers_asc")
    assert len(calls) == 2
