import logging

from twitchio.ext import commands

from config.settings import settings

LOGGER = logging.getLogger("RatBoomBot")


class ChatEvents(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @commands.Component.listener()
    async def event_message(self, payload) -> None:
        broadcaster_id = str(payload.broadcaster.id)
        broadcaster_name = payload.broadcaster.name
        chatter_id = str(payload.chatter.id)
        chatter_name = payload.chatter.name
        message = payload.text
        services = self.bot.services

        LOGGER.debug(
            "[Chat] [%s] %s: %s",
            broadcaster_name,
            chatter_name,
            message
        )

        if services is None:
            LOGGER.warning(
                "[Chat] Received chat message before services were initialized."
            )
            return

        try:
            await services.chatters.observe(broadcaster_id, payload.chatter)
        except Exception:
            LOGGER.exception(
                "[Chatters] Failed to record identity for %s (%s) in %s.",
                chatter_name,
                chatter_id,
                broadcaster_name
            )

        try:
            moderation_result = await services.moderation.evaluate_message(payload)
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to evaluate message from %s (%s) in %s.",
                chatter_name,
                chatter_id,
                broadcaster_name
            )
            moderation_result = None

        if moderation_result is not None and moderation_result.should_ban:
            if settings.BOT_DETECTION_MODE == "active":
                banned = await services.moderation.ban_user(payload, moderation_result)
                result_text = "Banned" if banned else "Failed to ban"

                services.stream_logs.write(
                    broadcaster_id,
                    "MODERATION",
                    (
                        f"{result_text} {chatter_name} ({chatter_id}) | "
                        f"Mode: active | "
                        f"Campaign: {moderation_result.campaign_id} | "
                        f"Source: {moderation_result.source} | "
                        f"Reason: {moderation_result.reason}"
                    )
                )

                return

            if settings.BOT_DETECTION_MODE == "shadow":
                LOGGER.warning(
                    "[Moderation] Shadow match: would ban %s (%s) in broadcaster %s for campaign %s. Reason: %s",
                    chatter_name,
                    chatter_id,
                    broadcaster_id,
                    moderation_result.campaign_id,
                    moderation_result.reason
                )

                await services.moderation.record_action(
                    broadcaster_id=broadcaster_id,
                    user_id=chatter_id,
                    username=chatter_name,
                    campaign_id=moderation_result.campaign_id,
                    fingerprint=moderation_result.fingerprint,
                    action=moderation_result.action,
                    reason=moderation_result.reason,
                    source=f"{moderation_result.source}_shadow",
                    message=message,
                    successful=False
                )

                services.stream_logs.write(
                    broadcaster_id,
                    "MODERATION",
                    (
                        f"Would ban {chatter_name} ({chatter_id}) | "
                        f"Mode: shadow | "
                        f"Campaign: {moderation_result.campaign_id} | "
                        f"Source: {moderation_result.source} | "
                        f"Reason: {moderation_result.reason}"
                    )
                )

                return

            LOGGER.info(
                "[Moderation] Learning-mode campaign match for %s (%s) in broadcaster %s. No action taken.",
                chatter_name,
                chatter_id,
                broadcaster_id
            )

            services.stream_logs.write(
                broadcaster_id,
                "MODERATION",
                (
                    f"Observed confirmed campaign match from "
                    f"{chatter_name} ({chatter_id}) | "
                    f"Mode: learning | "
                    f"Campaign: {moderation_result.campaign_id} | "
                    f"Source: {moderation_result.source} | "
                    f"Reason: {moderation_result.reason}"
                )
            )

            return

        services.timers.track_message(payload)
        await services.raid_bosses.track_message(payload)

        try:
            await services.first_chat_shoutouts.handle_message(
                broadcaster_id=broadcaster_id,
                user_id=chatter_id,
                username=chatter_name
            )
        except Exception:
            LOGGER.exception("[First Chat Shoutouts] Failed to process %s in %s.", chatter_name, broadcaster_name)

        try:
            await services.points.track_message(payload)
        except Exception:
            LOGGER.exception(
                "[Chat] Failed to process message rewards for %s in %s.",
                chatter_name,
                broadcaster_name
            )
