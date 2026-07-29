import logging

from twitchio.ext import commands

from bot.shared.commands.shoutout import send_shoutout_message

LOGGER = logging.getLogger("Bot")


class RaidEvents(commands.Component):
    def __init__(self, bot):
        self.bot = bot

    @commands.Component.listener()
    async def event_raid(self, payload):
        await self.handle_raid(payload)

    async def handle_raid(self, payload) -> None:
        raider = getattr(payload, "from_broadcaster", None)
        broadcaster = getattr(payload, "to_broadcaster", None)
        viewer_count = getattr(payload, "viewer_count", 0)

        if raider is None or broadcaster is None:
            LOGGER.warning("Could not process raid payload: %r", payload)
            return

        raider_name = getattr(raider, "name", None)

        if not raider_name:
            LOGGER.warning(
                "Could not find raider name from payload: %r",
                payload
            )
            return

        try:
            viewer_count = int(viewer_count)
        except (TypeError, ValueError):
            viewer_count = 0

        broadcaster_id = str(broadcaster.id)
        viewer_word = "viewer" if viewer_count == 1 else "viewers"

        if self.bot.services:
            self.bot.services.stream_logs.write(
                broadcaster_id,
                "RAID",
                f"{raider_name} raided with {viewer_count} {viewer_word}."
            )

        channel = self.bot.create_partialuser(broadcaster_id)

        await channel.send_message(
            sender=self.bot.user,
            message=(
                f"@{raider_name} has raided the basement with "
                f"{viewer_count} {viewer_word}! Rats stronk together!"
            )
        )

        await send_shoutout_message(
            bot=self.bot,
            broadcaster_id=broadcaster_id,
            username=raider_name
        )
