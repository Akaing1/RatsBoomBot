from types import SimpleNamespace

from fastapi.testclient import TestClient

from web.app import app


class FakeChatterStats:

    async def resolve_identity(self, value: str):
        return {"login": "alice", "display_name": "Alice"} if value.lower() == "alice" else None

    async def get_global_profile(self, value: str):
        if value.lower() != "alice":
            return None

        return {
            "identity": {"user_id": "user-1", "login": "alice", "display_name": "Alice"},
            "messages_sent": 1200,
            "lifetime_points_earned": 4500,
            "channels_interacted": 1,
            "daily_check_ins": 20,
            "favorite_channel": {"display_name": "TestChannel"},
            "damage_dealt": 9000,
            "highest_contribution": 3000,
            "bosses_attacked": 4,
            "bosses_defeated": 3,
            "final_hits": 1,
            "raid_reward_points": 2000,
            "top_contributor_finishes": 2,
            "recent_raids": [{"boss_name": "Test Boss", "channel": {"display_name": "TestChannel"}, "date": "2026-09-01", "damage": 3000, "reward_points": 2000, "status": "defeated", "top_contributor": True}],
            "channels": [{"id": "channel-1", "login": "testchannel", "display_name": "TestChannel", "profile_image_url": None, "messages_sent": 1200, "raid_damage": 9000}]
        }

    async def get_channel_profile(self, chatter_value: str, channel_value: str):
        if chatter_value.lower() != "alice" or channel_value.lower() != "testchannel":
            return None

        return {
            "identity": {"user_id": "user-1", "login": "alice", "display_name": "Alice"},
            "channel": {"id": "channel-1", "login": "testchannel", "display_name": "TestChannel", "profile_image_url": None},
            "messages_sent": 1200,
            "current_points": 500,
            "lifetime_points_earned": 4500,
            "currency_name": "cheese",
            "daily_check_ins": 20,
            "firsts": 3,
            "damage_dealt": 9000,
            "highest_contribution": 3000,
            "raid_reward_points": 2000,
            "bosses_attacked": 4,
            "bosses_defeated": 3,
            "final_hits": 1,
            "raids_rewarded": 3,
            "top_contributor_finishes": 2,
            "recent_raids": [{"boss_name": "Test Boss", "channel": {"display_name": "TestChannel"}, "date": "2026-09-01", "damage": 3000, "reward_points": 2000, "status": "defeated", "top_contributor": True}],
            "inventory": [{"item_id": "sword", "quantity": 1, "durability": 12, "equipped": 1}]
        }


def test_public_global_chatter_profile_renders(monkeypatch) -> None:
    monkeypatch.setattr("web.public.routers.get_bot", lambda: SimpleNamespace(services=SimpleNamespace(chatter_stats=FakeChatterStats())))

    with TestClient(app) as client:
        response = client.get("/chatters/alice")

    assert response.status_code == 200
    assert "Alice" in response.text
    assert "1,200" in response.text
    assert "TestChannel" in response.text
    assert "Total daily check-ins" in response.text
    assert "Recent raid history" in response.text
    assert 'data-chatter-tab="overview"' in response.text
    assert 'data-chatter-tab="raids"' in response.text
    assert 'data-chatter-panel="raids" hidden' in response.text
    assert "/chatters/alice/channels/testchannel" in response.text


def test_public_channel_chatter_profile_renders(monkeypatch) -> None:
    monkeypatch.setattr("web.public.routers.get_bot", lambda: SimpleNamespace(services=SimpleNamespace(chatter_stats=FakeChatterStats())))

    with TestClient(app) as client:
        response = client.get("/chatters/alice/channels/testchannel")

    assert response.status_code == 200
    assert "Current cheese" in response.text
    assert "Daily check-ins" in response.text
    assert "Sword" in response.text
    assert "Equipped" in response.text
    assert "Top Contributor finishes" in response.text
    assert "Recent raid history" in response.text
    assert 'data-chatter-tab="overview"' in response.text
    assert 'data-chatter-tab="raids"' in response.text
    assert 'data-chatter-panel="raids" hidden' in response.text


def test_public_chatter_search_redirects_to_canonical_profile(monkeypatch) -> None:
    monkeypatch.setattr("web.public.routers.get_bot", lambda: SimpleNamespace(services=SimpleNamespace(chatter_stats=FakeChatterStats())))

    with TestClient(app) as client:
        response = client.get("/chatters?q=Alice", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/chatters/alice"
