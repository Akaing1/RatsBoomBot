import logging

from twitchio.ext import commands

from bot.profiles import get_active_profile, render_profile_message
from bot.shared.commands.shoutout import send_shoutout_message

LOGGER = logging.getLogger("RatBoomBot")


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
            LOGGER.warning(
                "[Events] Could not process raid because the payload was incomplete: %r",
                payload
            )
            return

        raider_name = getattr(raider, "name", None)
        broadcaster_name = getattr(broadcaster, "name", None)
        broadcaster_id = str(broadcaster.id)

        if not raider_name:
            LOGGER.warning(
                "[Events] Could not determine the raider name from payload: %r",
                payload
            )
            return

        try:
            viewer_count = int(viewer_count)
        except (TypeError, ValueError):
            LOGGER.warning(
                "[Events] Raid from %s had an invalid viewer count: %r",
                raider_name,
                viewer_count
            )
            viewer_count = 0

        viewer_word = "viewer" if viewer_count == 1 else "viewers"

        LOGGER.info(
            "[Events] %s raided %s (%s) with %d %s.",
            raider_name,
            broadcaster_name,
            broadcaster_id,
            viewer_count,
            viewer_word
        )

        if self.bot.services:
            self.bot.services.stream_logs.write(
                broadcaster_id,
                "RAID",
                f"{raider_name} raided with {viewer_count} {viewer_word}."
            )
        else:
            LOGGER.warning(
                "[Events] Raid event received before services were initialized."
            )

        profile = get_active_profile(broadcaster_id)

        if profile is None:
            LOGGER.debug(
                "[Events] No active profile found for raid event in %s (%s).",
                broadcaster_name,
                broadcaster_id
            )
        else:
            try:
                message = render_profile_message(
                    profile.raid_messages.incoming,
                    raider_name=raider_name,
                    viewer_count=viewer_count,
                    viewer_word=viewer_word
                )
            except Exception:
                LOGGER.exception(
                    "[Events] Failed to render raid message for %s (%s).",
                    broadcaster_name,
                    broadcaster_id
                )
                raise

            if message:
                channel = self.bot.create_partialuser(broadcaster_id)

                try:
                    await channel.send_message(
                        sender=self.bot.user,
                        message=message
                    )
                except Exception:
                    LOGGER.exception(
                        "[Events] Failed to send raid message in %s (%s).",
                        broadcaster_name,
                        broadcaster_id
                    )
                    raise
            else:
                LOGGER.debug(
                    "[Events] Incoming raid message is disabled for %s (%s).",
                    broadcaster_name,
                    broadcaster_id
                )

        try:
            await send_shoutout_message(
                bot=self.bot,
                broadcaster_id=broadcaster_id,
                username=raider_name
            )
        except Exception:
            LOGGER.exception(
                "[Events] Failed to send shoutout for raider %s in %s (%s).",
                raider_name,
                broadcaster_name,
                broadcaster_id
            )
            raise
