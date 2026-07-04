import logging

LOGGER = logging.getLogger("Bot")


class StartUpService:
    def __init__(self, bot):
        self.bot = bot

    async def start(self, channels: dict[str, str]) -> None:
        for broadcaster_id, broadcaster_name in channels.items():
            try:
                broadcaster = self.bot.create_partialuser(broadcaster_id)

                await broadcaster.send_message(
                    sender=self.bot.user,
                    message="🐀 RatsBoomBot is now online!"
                )

                LOGGER.info("Startup announcement sent to %s", broadcaster_name)

            except Exception as error:
                LOGGER.error(
                    "Failed sending startup announcement to %s: %r",
                    broadcaster_name,
                    error,
                )