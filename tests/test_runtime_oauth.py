import logging

import asqlite
import pytest

import app.runtime as runtime
from storage.migration_runner import run_migrations


class InvalidTokenError(Exception):
    pass


class FakeBot:

    def __init__(self):
        self.loaded_tokens = []

    async def add_token(self, token: str, refresh_token: str) -> None:
        if token == "sensitive-invalid-token":
            raise InvalidTokenError

        self.loaded_tokens.append((token, refresh_token))


@pytest.mark.asyncio
async def test_invalid_stored_token_is_removed_without_exposing_it(tmp_path, monkeypatch, caplog) -> None:
    monkeypatch.setattr(runtime, "InvalidTokenException", InvalidTokenError)

    async with asqlite.create_pool(str(tmp_path / "tokens.db")) as database:
        await run_migrations(database)

        async with database.acquire() as connection:
            await connection.execute("INSERT INTO tokens (user_id, token, refresh) VALUES (?, ?, ?)", ("good-user", "good-token", "good-refresh"))
            await connection.execute("INSERT INTO tokens (user_id, token, refresh) VALUES (?, ?, ?)", ("bad-user", "sensitive-invalid-token", "sensitive-refresh"))

        bot = FakeBot()

        with caplog.at_level(logging.WARNING, logger="RatBoomBot"):
            invalid_user_ids = await runtime.load_stored_tokens(bot, database, (
                ("good-user", "good-token", "good-refresh"),
                ("bad-user", "sensitive-invalid-token", "sensitive-refresh")
            ))

        async with database.acquire() as connection:
            rows = await connection.fetchall("SELECT user_id FROM tokens ORDER BY user_id")

    assert invalid_user_ids == ("bad-user",)
    assert bot.loaded_tokens == [("good-token", "good-refresh")]
    assert [row["user_id"] for row in rows] == ["good-user"]
    assert "bad-user" in caplog.text
    assert "sensitive-invalid-token" not in caplog.text
    assert "sensitive-refresh" not in caplog.text
