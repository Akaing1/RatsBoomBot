from bot.services.engagement.viewer_queue import ViewerQueueService
from bot.shared.commands.viewer_queue import ViewerQueueCommands


def test_queue_starts_closed() -> None:
    service = ViewerQueueService(bot=None)

    assert service.is_queue_open("channel-1") is False
    assert service.size("channel-1") == 0


def test_open_join_and_next_viewer() -> None:
    service = ViewerQueueService(bot=None)
    open_message = service.open_queue("channel-1")

    assert "now open" in open_message.lower()

    joined, join_message = service.join("channel-1", "Rat")

    assert joined is True
    assert "position: 1" in join_message.lower()
    assert service.list_queue("channel-1") == ["rat"]

    found, viewers, next_message = service.next_viewers("channel-1")

    assert found is True
    assert viewers == ["rat"]
    assert "Next up: rat!" == next_message
    assert service.size("channel-1") == 0


def test_duplicate_user_is_rejected_case_insensitively() -> None:
    service = ViewerQueueService(bot=None)

    service.open_queue("channel-1")

    joined, _ = service.join("channel-1", "Rat")

    assert joined is True

    duplicate_joined, duplicate_message = service.join("channel-1", "Rat")

    assert duplicate_joined is False
    assert "already in the queue" in duplicate_message

    assert service.size("channel-1") == 1


def test_queues_are_isolated_per_broadcaster() -> None:
    service = ViewerQueueService(bot=None)

    service.open_queue("channel-1")

    service.open_queue("channel-2")

    service.join("channel-1", "alice")

    service.join("channel-2", "bob")

    assert service.list_queue("channel-1") == ["alice"]

    assert service.list_queue("channel-2") == ["bob"]


def test_queue_management_works_while_closed() -> None:
    service = ViewerQueueService(bot=None)
    service.open_queue("channel-1")

    for username in ("alice", "bob", "carol"):
        service.join("channel-1", username)

    service.close_queue("channel-1")
    swapped, _ = service.swap("channel-1", 1, 3)
    moved, _ = service.requeue("channel-1", 3, 1)
    found, viewers, _ = service.next_viewers("channel-1")
    removed, username, _ = service.remove_position("channel-1", 1)

    assert swapped is True
    assert moved is True
    assert found is True
    assert viewers == ["alice"]
    assert removed is True
    assert username == "carol"
    assert service.list_queue("channel-1") == ["bob"]


def test_remove_queue_discards_channel_state() -> None:
    service = ViewerQueueService(bot=None)
    service.open_queue("channel-1")
    service.join("channel-1", "alice")

    service.remove_queue("channel-1")

    assert service.is_queue_open("channel-1") is False
    assert service.list_queue("channel-1") == []


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
