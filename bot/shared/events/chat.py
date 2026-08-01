import logging

from twitchio.ext import commands

LOGGER = logging.getLogger("RatBoomBot")


class ChatEvents(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @commands.Component.listener()
    async def event_message(self, payload):

        broadcaster_id = str(payload.broadcaster.id)
        broadcaster_name = payload.broadcaster.name
        chatter_id = str(payload.chatter.id)
        chatter_name = payload.chatter.name
        message = payload.text

        LOGGER.debug(
            "[Chat] [%s] %s: %s",
            broadcaster_name,
            chatter_name,
            message
        )

        if not self.bot.services:
            LOGGER.warning(
                "[Chat] Received chat message before services were initialized."
            )
            return

        self.bot.services.stream_logs.write(
            broadcaster_id,
            "CHAT",
            f"{chatter_name}: {message}"
        )

        try:
            moderation_result = await self.bot.services.moderation.evaluate_message(
                payload
            )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to evaluate message from %s (%s) in %s.",
                chatter_name,
                chatter_id,
                broadcaster_name
            )
            moderation_result = None

        if moderation_result is not None and moderation_result.should_ban:
            banned = await self.bot.services.moderation.ban_user(
                payload,
                moderation_result
            )

            if banned:
                self.bot.services.stream_logs.write(
                    broadcaster_id,
                    "MODERATION",
                    (
                        f"Banned known bot {chatter_name} ({chatter_id}) | "
                        f"Source: {moderation_result.source} | "
                        f"Reason: {moderation_result.reason}"
                    )
                )
            else:
                self.bot.services.stream_logs.write(
                    broadcaster_id,
                    "MODERATION",
                    (
                        f"Failed to ban known bot {chatter_name} ({chatter_id}) | "
                        f"Source: {moderation_result.source} | "
                        f"Reason: {moderation_result.reason}"
                    )
                )

            return

        if moderation_result is not None and moderation_result.should_flag:
            try:
                await self.bot.services.moderation.flag_user(
                    payload,
                    moderation_result
                )
            except Exception:
                LOGGER.exception(
                    "[Moderation] Failed to flag user %s (%s) in %s.",
                    chatter_name,
                    chatter_id,
                    broadcaster_name
                )

            self.bot.services.stream_logs.write(
                broadcaster_id,
                "MODERATION",
                (
                    f"Flagged user {chatter_name} ({chatter_id}) | "
                    f"Source: {moderation_result.source} | "
                    f"Reason: {moderation_result.reason}"
                )
            )

        self.bot.services.timers.track_message(payload)

        try:
            await self.bot.services.points.track_message(payload)
        except Exception:
            LOGGER.exception(
                "[Chat] Failed to process message rewards for %s in %s.",
                chatter_name,
                broadcaster_name
            )
