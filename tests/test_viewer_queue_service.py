import asqlite
import pytest

from bot.services.engagement.viewer_queue import ViewerQueueService
from bot.shared.commands.viewer_queue import ViewerQueueCommands
from storage.migration_runner import run_migrations


@pytest.mark.asyncio
async def test_queue_starts_closed(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "queue.db")) as database:
        await run_migrations(database)
        service = ViewerQueueService(bot=None, db=database)
        await service.setup()

        assert service.is_queue_open("channel-1") is False
        assert service.size("channel-1") == 0


@pytest.mark.asyncio
async def test_open_join_and_next_viewer(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "queue.db")) as database:
        await run_migrations(database)
        service = ViewerQueueService(bot=None, db=database)
        await service.setup()
        open_message = await service.open_queue("channel-1")

        assert "now open" in open_message.lower()
        joined, join_message = await service.join("channel-1", "Rat")

        assert joined is True
        assert "position: 1" in join_message.lower()
        assert service.list_queue("channel-1") == ["rat"]
        found, viewers, next_message = await service.next_viewers("channel-1")

        assert found is True
        assert viewers == ["rat"]
        assert "Next up: rat!" == next_message
        assert service.size("channel-1") == 0


@pytest.mark.asyncio
async def test_take_queue_members_preserves_display_names_and_excluded_users(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "queue.db")) as database:
        await run_migrations(database)
        service = ViewerQueueService(bot=None, db=database)
        await service.setup()
        await service.open_queue("channel-1")
        await service.join("channel-1", "streamer", "Streamer")
        await service.join("channel-1", "alice", "Alice")
        await service.join("channel-1", "bob", "Bob")

        selected = await service.take_queue_members("channel-1", 2, exclude={"streamer"})

        assert [member["username"] for member in selected] == ["alice", "bob"]
        assert [member["display_name"] for member in selected] == ["Alice", "Bob"]
        assert service.list_queue("channel-1") == ["streamer"]


@pytest.mark.asyncio
async def test_duplicate_user_is_rejected_case_insensitively(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "queue.db")) as database:
        await run_migrations(database)
        service = ViewerQueueService(bot=None, db=database)
        await service.setup()

        await service.open_queue("channel-1")

        joined, _ = await service.join("channel-1", "Rat")

        assert joined is True
        duplicate_joined, duplicate_message = await service.join("channel-1", "Rat")

        assert duplicate_joined is False
        assert "already in the queue" in duplicate_message
        assert service.size("channel-1") == 1


@pytest.mark.asyncio
async def test_queues_are_isolated_per_broadcaster(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "queue.db")) as database:
        await run_migrations(database)
        service = ViewerQueueService(bot=None, db=database)
        await service.setup()

        await service.open_queue("channel-1")

        await service.open_queue("channel-2")

        await service.join("channel-1", "alice")

        await service.join("channel-2", "bob")

    assert service.list_queue("channel-1") == ["alice"]

    assert service.list_queue("channel-2") == ["bob"]


@pytest.mark.asyncio
async def test_queue_management_works_while_closed(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "queue.db")) as database:
        await run_migrations(database)
        service = ViewerQueueService(bot=None, db=database)
        await service.setup()
        await service.open_queue("channel-1")

        for username in ("alice", "bob", "carol"):
            await service.join("channel-1", username)

        await service.close_queue("channel-1")
        swapped, _ = await service.swap("channel-1", 1, 3)
        moved, _ = await service.requeue("channel-1", 3, 1)
        found, viewers, _ = await service.next_viewers("channel-1")
        removed, username, _ = await service.remove_position("channel-1", 1)

    assert swapped is True
    assert moved is True
    assert found is True
    assert viewers == ["alice"]
    assert removed is True
    assert username == "carol"
    assert service.list_queue("channel-1") == ["bob"]


@pytest.mark.asyncio
async def test_remove_queue_discards_channel_state(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "queue.db")) as database:
        await run_migrations(database)
        service = ViewerQueueService(bot=None, db=database)
        await service.setup()
        await service.open_queue("channel-1")
        await service.join("channel-1", "alice")

        await service.remove_queue("channel-1")

    assert service.is_queue_open("channel-1") is False
    assert service.list_queue("channel-1") == []


@pytest.mark.asyncio
async def test_queue_state_and_order_survive_service_restart(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "queue.db")) as database:
        await run_migrations(database)
        service = ViewerQueueService(bot=None, db=database)
        await service.setup()
        await service.open_queue("channel-1")
        await service.join("channel-1", "alice", "AliceTheRat")
        await service.join("channel-1", "bob")
        await service.join("channel-1", "carol")
        await service.requeue("channel-1", 3, 1)

        restarted_service = ViewerQueueService(bot=None, db=database)
        await restarted_service.setup()

        assert restarted_service.is_queue_open("channel-1") is True
        assert restarted_service.list_queue("channel-1") == ["carol", "alice", "bob"]
        assert restarted_service.list_queue_members("channel-1")[1] == {
            "username": "alice", "display_name": "AliceTheRat", "label": "AliceTheRat (alice)"
        }


@pytest.mark.asyncio
async def test_queue_hides_display_name_when_it_only_differs_by_case(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "queue.db")) as database:
        await run_migrations(database)
        service = ViewerQueueService(bot=None, db=database)
        await service.setup()
        await service.open_queue("channel-1")

        await service.join("channel-1", "caseuser", "CaseUser")

        assert service.list_queue_members("channel-1") == [{
            "username": "caseuser", "display_name": "CaseUser", "label": "caseuser"
        }]


@pytest.mark.asyncio
async def test_blacklist_blocks_joins_and_survives_service_restart(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "queue.db")) as database:
        await run_migrations(database)
        service = ViewerQueueService(bot=None, db=database)
        await service.setup()
        await service.open_queue("channel-1")

        added, message = await service.add_to_blacklist("channel-1", "BadUser")
        joined, join_message = await service.join("channel-1", "baduser")

        assert added is True
        assert "added" in message
        assert joined is False
        assert "not allowed" in join_message

        restarted_service = ViewerQueueService(bot=None, db=database)
        await restarted_service.setup()

        assert restarted_service.list_blacklist("channel-1") == ["baduser"]
        removed, _ = await restarted_service.remove_from_blacklist("channel-1", "BADUSER")
        joined, _ = await restarted_service.join("channel-1", "baduser")

        assert removed is True
        assert joined is True


@pytest.mark.asyncio
async def test_blacklisting_a_queued_viewer_removes_them(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "queue.db")) as database:
        await run_migrations(database)
        service = ViewerQueueService(bot=None, db=database)
        await service.setup()
        await service.open_queue("channel-1")
        await service.join("channel-1", "alice")
        await service.join("channel-1", "bob")

        added, _ = await service.add_to_blacklist("channel-1", "Alice")

        assert added is True
        assert service.list_queue("channel-1") == ["bob"]


def test_queue_messages_include_every_viewer() -> None:
    queue = [f"viewer{index}" for index in range(1, 9)]

    messages = ViewerQueueCommands.format_queue_messages(queue)

    assert messages == [
        "Current queue: 1. viewer1, 2. viewer2, 3. viewer3, 4. viewer4, "
        "5. viewer5, 6. viewer6, 7. viewer7, 8. viewer8"
    ]


def test_large_queue_is_split_without_omitting_viewers(monkeypatch) -> None:
    queue = [f"viewer{index}" for index in range(1, 9)]
    monkeypatch.setattr(ViewerQueueCommands, "QUEUE_MESSAGE_MAX_LENGTH", 55)

    messages = ViewerQueueCommands.format_queue_messages(queue)
    combined_messages = " ".join(messages)

    assert len(messages) > 1
    assert all(len(message) <= ViewerQueueCommands.QUEUE_MESSAGE_MAX_LENGTH for message in messages)

    for index, viewer in enumerate(queue, start=1):
        assert f"{index}. {viewer}" in combined_messages
