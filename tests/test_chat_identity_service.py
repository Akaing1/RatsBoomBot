from types import SimpleNamespace

import asqlite
import pytest

from bot.services.channels.chat_identity import ChatIdentityService
from storage.database import setup_database
from storage.migration_runner import run_migrations


class FakeBroadcaster:

    def __init__(self, broadcaster_id: str = "channel-1"):
        self.id = broadcaster_id
        self.messages = []
        self.announcements = []
        self.rejected_senders = set()

    async def send_message(self, *, sender, message, reply_to_message_id=None):
        sender_id = str(getattr(sender, "id", sender))

        if sender_id in self.rejected_senders:
            raise RuntimeError("Sender rejected")

        self.messages.append((sender_id, message, reply_to_message_id))
        return self.messages[-1]

    async def send_announcement(self, *, moderator, message, color):
        moderator_id = str(getattr(moderator, "id", moderator))

        if moderator_id in self.rejected_senders:
            raise RuntimeError("Moderator rejected")

        self.announcements.append((moderator_id, message, color))


async def add_token(database, user_id: str) -> None:
    async with database.acquire() as connection:
        await connection.execute("INSERT INTO tokens (user_id, token, refresh) VALUES (?, 'token', 'refresh')", (user_id,))


@pytest.mark.asyncio
async def test_premium_identity_connects_and_routes_messages(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "identity.db")) as database:
        await run_migrations(database)

        service = ChatIdentityService(SimpleNamespace(bot_id="main-bot"), database)
        await service.setup()
        await service.set_premium_enabled("channel-1", True)
        await add_token(database, "custom-bot")
        await service.connect("channel-1", "custom-bot", "characterbot", "CharacterBot")
        broadcaster = FakeBroadcaster()

        await service.send_message(broadcaster, "Hello!")
        await service.send_announcement(broadcaster, "Boss time!", "purple")

        assert broadcaster.messages == [("custom-bot", "Hello!", None)]
        assert broadcaster.announcements == [("custom-bot", "Boss time!", "purple")]
        assert service.get_state("channel-1").connected is True


@pytest.mark.asyncio
async def test_custom_identity_requires_premium_access(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "identity.db")) as database:
        await run_migrations(database)

        service = ChatIdentityService(SimpleNamespace(bot_id="main-bot"), database)
        await service.setup()

        with pytest.raises(ValueError, match="Premium custom identity access"):
            await service.connect("channel-1", "custom-bot", "characterbot", "CharacterBot")


@pytest.mark.asyncio
async def test_custom_identity_resolves_its_assigned_channel(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "identity.db")) as database:
        await run_migrations(database)

        service = ChatIdentityService(SimpleNamespace(bot_id="main-bot"), database)
        await service.setup()
        await service.set_premium_enabled("channel-1", True)
        await add_token(database, "custom-bot")
        await service.connect("channel-1", "custom-bot", "characterbot", "CharacterBot")

        assert service.custom_bot_broadcaster_id("custom-bot") == "channel-1"
        assert service.custom_bot_broadcaster_id("unassigned-bot") is None


@pytest.mark.asyncio
async def test_failed_custom_identity_falls_back_to_main_bot(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "identity.db")) as database:
        await run_migrations(database)

        service = ChatIdentityService(SimpleNamespace(bot_id="main-bot"), database)
        await service.setup()
        await service.set_premium_enabled("channel-1", True)
        await add_token(database, "custom-bot")
        await service.connect("channel-1", "custom-bot", "characterbot", "CharacterBot")
        broadcaster = FakeBroadcaster()
        broadcaster.rejected_senders.add("custom-bot")

        await service.send_message(broadcaster, "Fallback")
        await service.send_announcement(broadcaster, "Fallback announcement", "orange")

        assert broadcaster.messages == [("main-bot", "Fallback", None)]
        assert broadcaster.announcements == [("main-bot", "Fallback announcement", "orange")]


@pytest.mark.asyncio
async def test_disabling_premium_preserves_assignment_but_uses_main_bot(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "identity.db")) as database:
        await run_migrations(database)

        service = ChatIdentityService(SimpleNamespace(bot_id="main-bot"), database)
        await service.setup()
        await service.set_premium_enabled("channel-1", True)
        await add_token(database, "custom-bot")
        await service.connect("channel-1", "custom-bot", "characterbot", "CharacterBot")
        await service.set_premium_enabled("channel-1", False)
        broadcaster = FakeBroadcaster()

        await service.send_message(broadcaster, "Standard sender")

        assert broadcaster.messages == [("main-bot", "Standard sender", None)]
        assert service.get_state("channel-1").bot_user_id == "custom-bot"
        assert service.get_state("channel-1").connected is False


@pytest.mark.asyncio
async def test_custom_bot_token_is_not_loaded_as_a_broadcaster(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("storage.database.create_broadcaster_subscriptions", lambda broadcaster_id: [f"subscription-{broadcaster_id}"])

    async with asqlite.create_pool(str(tmp_path / "identity.db")) as database:
        await run_migrations(database)

        async with database.acquire() as connection:
            await connection.execute("INSERT INTO tokens (user_id, token, refresh) VALUES (?, ?, ?)", ("999", "main-token", "main-refresh"))
            await connection.execute("INSERT INTO tokens (user_id, token, refresh) VALUES (?, ?, ?)", ("channel-1", "channel-token", "channel-refresh"))
            await connection.execute("INSERT INTO tokens (user_id, token, refresh) VALUES (?, ?, ?)", ("custom-bot", "custom-token", "custom-refresh"))
            await connection.execute(
                "INSERT INTO channel_chat_identities (broadcaster_id, premium_enabled, bot_user_id) VALUES (?, 1, ?)",
                ("channel-1", "custom-bot")
            )

        tokens, subscriptions, broadcasters = await setup_database(database)

        assert len(tokens) == 3
        assert broadcasters == ["channel-1"]
        assert subscriptions == ["subscription-channel-1"]
