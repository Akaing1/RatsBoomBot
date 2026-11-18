from pathlib import Path
from types import SimpleNamespace

import asqlite
import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from storage.migration_runner import run_migrations
from web.channel.routers import streamer_setup


@pytest.mark.asyncio
async def test_streamer_setup_saves_progress_and_excludes_delegated_moderators(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / "setup.db")) as db:
        await run_migrations(db)

        async def fetch_moderators(*, user_ids, max_results):
            assert user_ids == ["bot-id"]
            yield SimpleNamespace(id="bot-id")

        bot = SimpleNamespace(
            bot_id="bot-id", user=SimpleNamespace(name="RatsBoomBot"),
            create_partialuser=lambda user_id: SimpleNamespace(fetch_moderators=fetch_moderators),
            services=SimpleNamespace(
                broadcasters=SimpleNamespace(get_broadcasters=lambda: {}),
                chat_identity=SimpleNamespace(get_state=lambda _: SimpleNamespace(connected=False)),
                features=SimpleNamespace(is_enabled=lambda *_: False),
            ),
        )
        monkeypatch.setattr(streamer_setup, "get_bot", lambda: bot)
        monkeypatch.setattr(streamer_setup, "get_db", lambda: db)
        session = {"channel_user_id": "owner", "channel_user_login": "owner", "csrf_token": "secret"}
        app = FastAPI()
        root = Path(__file__).resolve().parents[1]
        app.mount("/static", StaticFiles(directory=root / "web/static"), name="static")
        app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

        @app.middleware("http")
        async def add_session(request: Request, call_next):
            request.scope["session"] = session
            if request.headers.get("x-test-moderator"):
                request.state.channel_access = {"broadcaster_id": "owner"}
            return await call_next(request)

        app.include_router(streamer_setup.router)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            url = "/channel/setup"
            assert "Start setup" in (await client.get(url)).text
            assert (await client.get(url, headers={"x-test-moderator": "1"})).status_code == 403
            assert (await client.post(url, data={"action": "next", "expected_step": 0, "csrf_token": "wrong"})).status_code == 403

            async def act(action, step):
                response = await client.post(url, data={"action": action, "expected_step": step, "csrf_token": "secret"})
                assert response.status_code == 303
                return response.headers["location"]

            await act("next", 0)
            await act("next", 0)  # A second tab cannot advance a stale step.
            assert "/mod RatsBoomBot" in (await client.get(url)).text
            await act("check-moderator", 1)
            assert "Moderator role confirmed" in (await client.get(url)).text
            assert await act("dismiss", 1) == "/channel"
            assert "Setup paused" in (await client.get(url)).text
            await act("resume", 1)
            for step in (1, 2, 3):
                await act("next", step)
            await act("confirm-command", 4)
            review = (await client.get(url)).text
            assert "Reply confirmed by you" in review
            assert "Bot moderator role · Confirmed" in review
            assert await act("finish", 5) == "/channel"
            assert "Setup complete" in (await client.get(url)).text
            await act("restart", 5)
            assert "Start setup" in (await client.get(url)).text
