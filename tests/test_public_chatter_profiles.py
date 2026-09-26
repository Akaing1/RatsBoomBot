from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
import pytest

from web.app import app


@pytest.fixture(autouse=True)
def mock_viewer_session_store(monkeypatch):
    async def create(db, user_id):
        return "test-server-session"

    async def revoke(db, token):
        pass

    monkeypatch.setattr("web.viewer.routers.get_db", lambda: object())
    monkeypatch.setattr("web.viewer.routers.create_viewer_session", create)
    monkeypatch.setattr("web.viewer.routers.revoke_viewer_session", revoke)


class FakeChatterStats:

    async def resolve_identity(self, value: str):
        return {"login": "alice", "display_name": "Alice"} if value.lower() == "alice" else None

    async def get_global_profile(self, value: str):
        if value.lower() != "alice":
            return None

        return {
            "identity": {"user_id": "user-1", "login": "alice", "display_name": "Alice", "profile_image_url": "https://example.com/alice.png"},
            "level": {"level": 3, "total_xp": 2750, "achievement_xp": 2500, "raid_xp": 250, "current_xp": 750, "xp_required": 2500, "percent": 30},
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
            "recent_raids": [{"boss_name": "Test Boss", "channel": {"display_name": "TestChannel"}, "date": "2026-09-01", "damage": 3000, "reward_points": 2000, "status": "defeated", "placement": 2, "participant_count": 12, "top_contributor": False}],
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
            "recent_raids": [{"boss_name": "Test Boss", "channel": {"display_name": "TestChannel"}, "date": "2026-09-01", "damage": 3000, "reward_points": 2000, "status": "defeated", "placement": 2, "participant_count": 12, "top_contributor": False}],
            "inventory": [
                {"item_id": "sword", "display_name": "Sword", "quantity": 1, "durability": 12, "equipped": 1},
                {"item_id": "basic_bow", "display_name": "Basic Bow", "quantity": 2, "durability": 15, "equipped": 0}
            ],
            "consumables": [
                {"item_id": "power_potion", "display_name": "Power Potion", "quantity": 2},
                {"item_id": "second_wind", "display_name": "Second Wind", "quantity": 1}
            ]
        }


class FakePets:

    async def get_equipped_pet(self, user_id: str):
        assert user_id == "user-1"
        return SimpleNamespace(
            display_name="Dungeon Bat",
            level=1,
            passive_percent_label="10",
            sprite_path="/assets/bat.png",
            frame_count=4
        )


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
    assert "#2 of 12" in response.text
    assert 'data-chatter-tab="overview"' in response.text
    assert 'data-chatter-tab="raids"' in response.text
    assert 'data-chatter-panel="raids" hidden' in response.text
    assert "/chatters/alice/channels/testchannel" in response.text
    assert "/me/connect?next=/chatters/alice" in response.text
    assert "Level 3" in response.text
    assert "750 / 2,500 XP" in response.text
    assert 'src="https://example.com/alice.png"' in response.text
    assert "View on Twitch" not in response.text


def test_public_global_chatter_profile_renders_equipped_pet(monkeypatch) -> None:
    services = SimpleNamespace(chatter_stats=FakeChatterStats(), pets=FakePets())
    monkeypatch.setattr("web.public.routers.get_bot", lambda: SimpleNamespace(services=services))

    with TestClient(app) as client:
        response = client.get("/chatters/alice")

    assert response.status_code == 200
    assert "Dungeon Bat" in response.text
    assert "+10% loyalty points" in response.text
    assert "/assets/bat.png" in response.text
    assert "--pet-frames: 4" in response.text


def test_public_channel_chatter_profile_renders(monkeypatch) -> None:
    monkeypatch.setattr("web.public.routers.get_bot", lambda: SimpleNamespace(services=SimpleNamespace(chatter_stats=FakeChatterStats())))

    with TestClient(app) as client:
        response = client.get("/chatters/alice/channels/testchannel")

    assert response.status_code == 200
    assert "Current cheese" in response.text
    assert "Daily check-ins" in response.text
    assert "Sword" in response.text
    assert "Basic Bow" in response.text
    assert "Power Potion" in response.text
    assert "Second Wind" in response.text
    assert "x2" in response.text
    assert "Equipped" in response.text
    assert "#2 of 12" in response.text
    assert "Top Contributor finishes" in response.text
    assert "Recent raid history" in response.text
    assert "/me/connect?next=/chatters/alice/channels/testchannel" in response.text
    assert 'class="public-command-navigation chatter-channel-navigation"' in response.text
    assert 'class="button secondary chatter-channel-back"' in response.text
    assert 'data-chatter-tab="overview"' in response.text
    assert 'data-chatter-tab="raids"' in response.text
    assert 'data-chatter-panel="raids" hidden' in response.text


def test_public_chatter_search_redirects_to_canonical_profile(monkeypatch) -> None:
    monkeypatch.setattr("web.public.routers.get_bot", lambda: SimpleNamespace(services=SimpleNamespace(chatter_stats=FakeChatterStats())))

    with TestClient(app) as client:
        response = client.get("/chatters?q=Alice", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/chatters/alice"


def test_sign_in_from_public_profile_keeps_account_available(monkeypatch) -> None:
    from web.shared.oauth import TwitchTokenResponse, TwitchUser

    async def exchange(*, code, redirect_uri):
        return TwitchTokenResponse("token", "refresh", 3600, [], "bearer")

    async def fetch(token):
        return TwitchUser("user-1", "alice", "Alice")

    monkeypatch.setattr("web.viewer.routers.exchange_code_for_token", exchange)
    monkeypatch.setattr("web.viewer.routers.fetch_twitch_user", fetch)
    monkeypatch.setattr("web.public.routers.get_bot", lambda: SimpleNamespace(services=SimpleNamespace(chatter_stats=FakeChatterStats())))

    with TestClient(app) as client:
        profile = client.get("/chatters/alice")
        assert "/me/connect?next=/chatters/alice" in profile.text
        start = client.get("/me/connect?next=/chatters/alice", follow_redirects=False)
        state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
        callback = client.get(f"/oauth/viewer/connect?code=valid&state={state}", follow_redirects=False)
        assert callback.headers["location"] == "/chatters/alice"
        for path in ("/chatters/alice", "/chatters/alice/channels/testchannel"):
            signed_in = client.get(path)
            assert signed_in.status_code == 200
            if path.endswith("/testchannel"):
                assert "My account" not in signed_in.text
                assert "Back to global profile" in signed_in.text
            else:
                assert "My account" in signed_in.text
            assert "Sign in with Twitch" not in signed_in.text
            assert "Sign out" in signed_in.text
            assert signed_in.headers["cache-control"] == "no-store"
        assert "My chatter profile" in client.get("/chatters/alice").text
        assert "Your activity in" in client.get("/chatters/alice/channels/testchannel").text


def test_another_chatter_profile_stays_public_after_sign_in(monkeypatch) -> None:
    from web.shared.oauth import TwitchTokenResponse, TwitchUser

    async def exchange(*, code, redirect_uri):
        return TwitchTokenResponse("token", "refresh", 3600, [], "bearer")

    async def fetch(token):
        return TwitchUser("someone-else", "bob", "Bob")

    monkeypatch.setattr("web.viewer.routers.exchange_code_for_token", exchange)
    monkeypatch.setattr("web.viewer.routers.fetch_twitch_user", fetch)
    monkeypatch.setattr("web.public.routers.get_bot", lambda: SimpleNamespace(services=SimpleNamespace(chatter_stats=FakeChatterStats())))

    with TestClient(app) as client:
        start = client.get("/me/connect", follow_redirects=False)
        state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
        client.get(f"/oauth/viewer/connect?code=valid&state={state}", follow_redirects=False)

        global_profile = client.get("/chatters/alice")
        channel_profile = client.get("/chatters/alice/channels/testchannel")

    assert "Public chatter profile" in global_profile.text
    assert "My chatter profile" not in global_profile.text
    assert "Sign out" not in global_profile.text
    assert "@alice in" in channel_profile.text
    assert "Your activity in" not in channel_profile.text
    assert "Sign out" not in channel_profile.text
    assert "My account" not in channel_profile.text
