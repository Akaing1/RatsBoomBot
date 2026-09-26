import re
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import asqlite
import httpx
import pytest

from bot.profiles import ChannelProfile, FeatureDefaults, FeatureName, RaidBossConfig, activate_profile, clear_profiles
from bot.services.engagement.raid_boss import RaidBossService
from bot.services.engagement.points import PointsService
from storage.migration_runner import run_migrations
from storage.viewer_sessions import claim_viewer_action, create_viewer_session, revoke_viewer_session, valid_viewer_session
from web.app import app
from web.shared.oauth import TwitchTokenResponse, TwitchUser


@pytest.mark.asyncio
async def test_shop_reuses_raid_transactions_and_revokes_on_signout(tmp_path, monkeypatch):
    now = [1_000_000]
    monkeypatch.setattr("storage.viewer_sessions.time.time", lambda: now[0])
    activate_profile("channel-1", ChannelProfile(
        channel_name="TestChannel",
        features=FeatureDefaults(raid_bosses=True),
        raid_bosses=RaidBossConfig(enabled=True, weapon_cost=100, refined_crafting_cost=25),
    ))
    activate_profile("channel-2", ChannelProfile(
        channel_name="OtherChannel",
        features=FeatureDefaults(raid_bosses=True),
        raid_bosses=RaidBossConfig(enabled=True, weapon_cost=300),
    ))

    async with asqlite.create_pool(str(tmp_path / "shop.db")) as db:
        await run_migrations(db)
        async with db.acquire() as connection:
            await connection.execute("INSERT INTO viewers (broadcaster_id,user_id,username,points,messages) VALUES ('channel-1','user-1','alice',1000,0)")
            await connection.execute("INSERT INTO viewers (broadcaster_id,user_id,username,points,messages) VALUES ('channel-2','user-1','alice',500,0)")

        class Stats:
            async def get_channel_profile(self, user_id, channel_name):
                if user_id not in ("user-1", "alice") or channel_name not in ("testchannel", "otherchannel"):
                    return None
                user_id = "user-1"
                broadcaster_id = "channel-1" if channel_name == "testchannel" else "channel-2"
                async with db.acquire() as connection:
                    balance = await connection.fetchone("SELECT points FROM viewers WHERE broadcaster_id=? AND user_id=?", (broadcaster_id, user_id))
                    items = await connection.fetchall("SELECT item_id,quantity FROM raid_boss_inventory WHERE broadcaster_id=? AND user_id=? AND quantity>0", (broadcaster_id, user_id))
                profile = {"identity": {"user_id": user_id, "login": "alice", "display_name": "Alice"}, "channel": {"id": broadcaster_id, "login": channel_name, "display_name": "TestChannel" if broadcaster_id == "channel-1" else "OtherChannel", "profile_image_url": None}, "current_points": balance["points"], "currency_name": "Points" if broadcaster_id == "channel-1" else "Crumbs", "inventory": [{"item_id": row["item_id"], "quantity": row["quantity"], "display_name": row["item_id"], "durability": 10, "equipped": False} for row in items], "consumables": [], "recent_raids": [], "achievements": []}
                profile.update({key: 0 for key in ("messages_sent", "lifetime_points_earned", "daily_check_ins", "firsts", "damage_dealt", "highest_contribution", "raid_reward_points", "top_contributor_finishes", "bosses_attacked", "bosses_defeated", "final_hits", "raids_rewarded")})
                return profile

        async def exchange(*, code, redirect_uri):
            return TwitchTokenResponse("user-token", "refresh-token", 3600, [], "bearer")

        async def fetch(token):
            return TwitchUser("user-1", "alice", "Alice")

        points = PointsService(None, db)
        await points.setup()
        services = SimpleNamespace(chatter_stats=Stats(), features=SimpleNamespace(is_enabled=lambda *args: True), raid_bosses=RaidBossService(None, db), points=points)
        monkeypatch.setattr("web.viewer.routers.get_bot", lambda: SimpleNamespace(services=services))
        monkeypatch.setattr("web.viewer.routers.get_db", lambda: db)
        monkeypatch.setattr("web.public.routers.get_bot", lambda: SimpleNamespace(services=services))
        monkeypatch.setattr("web.public.routers.get_db", lambda: db)
        monkeypatch.setattr("web.viewer.routers.exchange_code_for_token", exchange)
        monkeypatch.setattr("web.viewer.routers.fetch_twitch_user", fetch)

        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                shop_url = "/me/channels/testchannel/shop"
                assert (await client.get(shop_url, follow_redirects=False)).headers["location"].startswith("/me/connect")
                start = await client.get("/me/connect?next=/me/channels/testchannel/shop", follow_redirects=False)
                state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
                assert (await client.get(f"/oauth/viewer/connect?code=ok&state={state}", follow_redirects=False)).headers["location"] == shop_url

                page = await client.get(shop_url, follow_redirects=True)
                assert page.status_code == 200
                assert page.url.path == "/chatters/alice/channels/testchannel"
                assert 'data-chatter-panel="shop"' in page.text
                assert 'data-chatter-tab="shop"' in page.text
                assert "1,000 Points" in page.text
                csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
                action = f"{shop_url}/buy"
                assert (await client.post(action, data={"csrf_token": "invalid", "item_id": "basic_sword"})).status_code == 403
                assert (await client.post(action, data={"csrf_token": csrf, "item_id": "blessing"})).status_code == 400

                first = await client.post(action, data={"csrf_token": csrf, "item_id": "basic_sword"}, follow_redirects=False)
                assert first.headers["location"].startswith("/chatters/alice/channels/testchannel?tab=shop")
                assert first.headers["location"].endswith("result=bought")
                assert (await client.post(action, data={"csrf_token": csrf, "item_id": "basic_sword"})).status_code == 429
                now[0] += 3
                assert (await client.post(action, data={"csrf_token": csrf, "item_id": "basic_sword"}, follow_redirects=False)).status_code == 303
                now[0] += 3
                crafted = await client.post(f"{shop_url}/craft", data={"csrf_token": csrf, "item_id": "refined_sword"}, follow_redirects=False)
                assert crafted.headers["location"].endswith("result=crafted")
                now[0] += 3
                sold = await client.post(f"{shop_url}/sell", data={"csrf_token": csrf, "item_id": "refined_sword"}, follow_redirects=False)
                assert sold.headers["location"].endswith("result=sold")

                async with db.acquire() as connection:
                    balance = await connection.fetchone("SELECT points FROM viewers WHERE broadcaster_id='channel-1' AND user_id='user-1'")
                    inventory = await connection.fetchone("SELECT quantity FROM raid_boss_inventory WHERE broadcaster_id='channel-1' AND user_id='user-1' AND item_id='refined_sword'")
                    rewards = await connection.fetchone("SELECT COALESCE(SUM(points), 0) AS points FROM channel_achievement_rewards WHERE broadcaster_id='channel-1' AND user_id='user-1'")
                assert balance["points"] == 1000 - 200 - 25 + 112 + rewards["points"]
                assert rewards["points"] > 0  # Buying and crafting can unlock channel achievements.
                assert inventory["quantity"] == 0

                other_shop = "/chatters/alice/channels/otherchannel?tab=shop"
                other_page = await client.get(other_shop)
                assert "500 Crumbs" in other_page.text
                assert 'data-chatter-tab="shop"' in other_page.text
                now[0] += 3
                other_purchase = await client.post("/me/channels/otherchannel/shop/buy", data={"csrf_token": csrf, "item_id": "basic_bow"}, follow_redirects=False)
                assert other_purchase.headers["location"].startswith(other_shop)
                async with db.acquire() as connection:
                    other_balance = await connection.fetchone("SELECT points FROM viewers WHERE broadcaster_id='channel-2' AND user_id='user-1'")
                    other_rewards = await connection.fetchone("SELECT COALESCE(SUM(points),0) AS points FROM channel_achievement_rewards WHERE broadcaster_id='channel-2' AND user_id='user-1'")
                    original_balance = await connection.fetchone("SELECT points FROM viewers WHERE broadcaster_id='channel-1' AND user_id='user-1'")
                assert other_balance["points"] == 500 - 300 + other_rewards["points"]
                assert original_balance["points"] == balance["points"]

                gamble_url = "/me/channels/otherchannel/gamble"
                gamble_page = await client.get(gamble_url, follow_redirects=True)
                assert gamble_page.url.path == "/chatters/alice/channels/otherchannel"
                assert 'data-chatter-tab="gamble"' in gamble_page.text
                assert "Crumbs" in gamble_page.text
                assert (await client.post(gamble_url, data={"csrf_token": "invalid", "amount": "50"})).status_code == 403
                assert (await client.post(gamble_url, data={"csrf_token": csrf, "amount": "5oops"})).status_code == 400
                now[0] += 6
                monkeypatch.setattr("web.viewer.routers.random.random", lambda: 0.0)
                win = await client.post(gamble_url, data={"csrf_token": csrf, "amount": "50"}, follow_redirects=False)
                assert win.headers["location"] == "/chatters/alice/channels/otherchannel?tab=gamble"
                assert (await client.post(gamble_url, data={"csrf_token": csrf, "amount": "50"})).status_code == 429
                result = await client.get(win.headers["location"])
                assert "You won 50 Crumbs" in result.text
                assert "You won 50 Crumbs" not in (await client.get(win.headers["location"])).text
                now[0] += 6
                monkeypatch.setattr("web.viewer.routers.random.random", lambda: 1.0)
                loss = await client.post(gamble_url, data={"csrf_token": csrf, "amount": "all"}, follow_redirects=False)
                assert "You lost" in (await client.get(loss.headers["location"])).text
                assert await points.get_points("channel-2", "user-1") == 0
                assert await points.get_points("channel-1", "user-1") == original_balance["points"]
                async with db.acquire() as connection:
                    streak = await connection.fetchone("SELECT outcome,length,channel_name FROM gamble_streaks WHERE broadcaster_id='channel-2' AND user_id='user-1'")
                    other_totals = await connection.fetchone("SELECT winnings,losses FROM viewer_gambling_totals WHERE broadcaster_id='channel-2' AND user_id='user-1'")
                    original_totals = await connection.fetchone("SELECT 1 FROM viewer_gambling_totals WHERE broadcaster_id='channel-1' AND user_id='user-1'")
                assert (streak["outcome"], streak["length"], streak["channel_name"]) == ("loss", 1, "otherchannel")
                assert other_totals["winnings"] == 50
                assert other_totals["losses"] > 0
                assert original_totals is None
                now[0] += 6
                empty_bet = await client.post(gamble_url, data={"csrf_token": csrf, "amount": "all"}, follow_redirects=True)
                assert "You have no points to gamble" in empty_bet.text
                assert await points.get_points("channel-2", "user-1") == 0

                monkeypatch.setattr(services.features, "is_enabled", lambda broadcaster, feature: feature == FeatureName.POINTS if broadcaster == "channel-2" else True)
                points_only = await client.get("/chatters/alice/channels/otherchannel")
                assert 'data-chatter-tab="gamble"' in points_only.text
                assert 'data-chatter-tab="shop"' not in points_only.text

                assert (await client.post("/me/logout", data={"csrf_token": csrf}, follow_redirects=False)).status_code == 303
                assert (await client.get(shop_url, follow_redirects=False)).headers["location"].startswith("/me/connect")
        finally:
            clear_profiles()


@pytest.mark.asyncio
async def test_server_session_rejects_other_users_and_expired_tokens(tmp_path, monkeypatch):
    now = [1_000_000]
    monkeypatch.setattr("storage.viewer_sessions.time.time", lambda: now[0])
    async with asqlite.create_pool(str(tmp_path / "sessions.db")) as db:
        await run_migrations(db)
        token = await create_viewer_session(db, "user-1")
        assert await valid_viewer_session(db, "user-1", token)
        assert not await valid_viewer_session(db, "user-2", token)
        assert not await claim_viewer_action(db, "user-2", token)
        assert await claim_viewer_action(db, "user-1", token)
        assert not await claim_viewer_action(db, "user-1", token)
        now[0] += 3
        assert await claim_viewer_action(db, "user-1", token)
        await revoke_viewer_session(db, token)
        assert not await valid_viewer_session(db, "user-1", token)
        assert not await claim_viewer_action(db, "user-1", token)
        other = await create_viewer_session(db, "user-1")
        now[0] += 60 * 60 * 24 * 31
        assert not await valid_viewer_session(db, "user-1", other)
        assert not await claim_viewer_action(db, "user-1", other)
