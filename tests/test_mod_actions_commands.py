from types import SimpleNamespace

from bot.shared.commands.mod_actions import ModActionCommands


def create_commands() -> ModActionCommands:
    return ModActionCommands(SimpleNamespace())


def test_kamikaze_cooldown_notice_is_sent_once_per_window() -> None:
    command = create_commands()
    command.start_kamikaze_cooldown("channel-1", "viewer-1")

    assert command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-1", 599)
    assert not command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-1", 450)
    assert command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-1", 300)
    assert not command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-1", 1)


def test_kamikaze_cooldown_notices_are_separate_by_channel_and_viewer() -> None:
    command = create_commands()

    assert command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-1", 500)
    assert command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-2", 500)
    assert command.should_send_kamikaze_cooldown_notice("channel-2", "viewer-1", 500)


def test_starting_new_kamikaze_cooldown_resets_notice_windows() -> None:
    command = create_commands()

    command.start_kamikaze_cooldown("channel-1", "viewer-1")
    assert command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-1", 500)
    assert not command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-1", 500)

    command.start_kamikaze_cooldown("channel-1", "viewer-1")

    assert command.should_send_kamikaze_cooldown_notice("channel-1", "viewer-1", 500)