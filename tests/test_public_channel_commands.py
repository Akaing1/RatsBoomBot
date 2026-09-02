from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from bot.profiles import ChannelProfile, FeatureDefaults, GlobalCommandDefaults, RaidBossConfig, activate_profile, clear_profiles
from bot.services.channels.broadcaster import Broadcaster
from bot.services.channels.feature_toggle import FeatureToggleService
from web.app import app


class FakeRaidBossService:

    async def get_dashboard_metrics(self, broadcaster_id: str):
        assert broadcaster_id == "channel-1"
        return {
            "boss_name": "Ahriman",
            "boss_type": "magic",
            "boss_tier": "mini",
            "max_hp": 20000,
            "current_hp": 11609,
            "hp_percent": 58.0,
            "reward_pool": 2000,
            "status": "active",
            "stream_limit": 3,
            "streams_used": 1,
            "total_attacks": 20,
            "unique_attackers": 20,
            "total_damage": 8391
        }

    async def get_contributors(self, broadcaster_id: str):
        assert broadcaster_id == "channel-1"
        return [(f"viewer-{index}", 1300 - (index * 100)) for index in range(1, 13)]


@pytest.fixture(autouse=True)
def reset_active_profiles():
    clear_profiles()
    yield
    clear_profiles()


def test_public_channel_page_only_shows_enabled_commands_and_available_raid(monkeypatch) -> None:
    broadcaster_id = "channel-1"
    profile = ChannelProfile(
        channel_name="MeinyaYozakura",
        features=FeatureDefaults(raid_bosses=True),
        globals=GlobalCommandDefaults(height=False),
        raid_bosses=RaidBossConfig(enabled=True)
    )
    activate_profile(broadcaster_id, profile)
    broadcaster = Broadcaster(id=broadcaster_id, login="meinyayozakura", display_name="MeinyaYozakura")
    broadcasters = SimpleNamespace(get_broadcasters=lambda: {broadcaster_id: broadcaster})
    services = SimpleNamespace(broadcasters=broadcasters, features=FeatureToggleService(db=None), raid_bosses=FakeRaidBossService())
    monkeypatch.setattr("web.public.routers.get_bot", lambda: SimpleNamespace(services=services))

    with TestClient(app) as client:
        response = client.get("/help/MeinyaYozakura")

    assert response.status_code == 200
    assert "!pp [username]" in response.text
    assert "!height [username]" not in response.text
    assert ">Disabled<" not in response.text
    assert "Ahriman" in response.text
    assert "11,609/20,000 HP" in response.text
    assert "viewer-10" in response.text
    assert "viewer-11" in response.text
    assert "Show all 12 contributors" in response.text


def test_public_channel_page_returns_not_found_for_unknown_channel(monkeypatch) -> None:
    services = SimpleNamespace(broadcasters=SimpleNamespace(get_broadcasters=lambda: {}))
    monkeypatch.setattr("web.public.routers.get_bot", lambda: SimpleNamespace(services=services))

    with TestClient(app) as client:
        response = client.get("/help/unknown")

    assert response.status_code == 404
    assert "Channel not found" in response.text



def test_legacy_commands_route_redirects_to_help() -> None:
    with TestClient(app, follow_redirects=False) as client:
        response = client.get("/commands/MeinyaYozakura")

    assert response.status_code == 308
    assert response.headers["location"] == "/help/MeinyaYozakura"
