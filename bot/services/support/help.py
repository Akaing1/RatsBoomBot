from urllib.parse import quote

from config.settings import settings


class HelpService:

    def __init__(self, bot):
        self.bot = bot

    def format_help_message(self, channel_name: str) -> str:
        command_page_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/commands/{quote(channel_name)}"
        return f"View all active commands and raid information for {channel_name}: {command_page_url}"
