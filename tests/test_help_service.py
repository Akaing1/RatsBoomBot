from bot.services.support.help import HelpService
from config.settings import settings


def test_help_message_links_to_channel_public_command_page(monkeypatch) -> None:
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://ratsboombot.com/")
    service = HelpService(bot=None)

    message = service.format_help_message("MeinyaYozakura")

    assert message == "View all active commands and raid information for MeinyaYozakura: https://ratsboombot.com/commands/MeinyaYozakura"
