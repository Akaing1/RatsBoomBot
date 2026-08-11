from bot.services.viewer_queue_service import ViewerQueueService


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
    assert "@rat" in next_message
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


def test_remove_queue_discards_channel_state() -> None:
    service = ViewerQueueService(bot=None)
    service.open_queue("channel-1")
    service.join("channel-1", "alice")

    service.remove_queue("channel-1")

    assert service.is_queue_open("channel-1") is False
    assert service.list_queue("channel-1") == []
