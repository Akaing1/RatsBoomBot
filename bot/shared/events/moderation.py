import logging

from twitchio.ext import commands

from config.settings import settings

LOGGER = logging.getLogger("RatBoomBot")


class ModerationEvents(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @commands.Component.listener()
    async def event_mod_action(self, payload) -> None:
        services = self.bot.services

        if services is None:
            LOGGER.warning(
                "[Moderation] Received moderation event before services were initialized."
            )
            return

        action = getattr(payload, "action", None)
        moderator = getattr(payload, "moderator", None)
        ban = getattr(payload, "ban", None)

        if action != "ban" or moderator is None or ban is None:
            return

        moderator_id = str(moderator.id)

        if moderator_id != str(settings.SERYBOT_USER_ID):
            return

        banned_user = getattr(ban, "user", None)

        if banned_user is None:
            LOGGER.warning(
                "[Moderation] SeryBot ban event did not include a banned user."
            )
            return

        broadcaster = getattr(payload, "broadcaster", None)
        broadcaster_id = getattr(broadcaster, "id", None)

        if broadcaster_id is None:
            LOGGER.warning(
                "[Moderation] SeryBot ban event did not include a broadcaster."
            )
            return

        broadcaster_id = str(broadcaster_id)
        user_id = str(banned_user.id)
        username = banned_user.name
        moderator_name = moderator.name
        reason = getattr(ban, "reason", None)

        LOGGER.warning(
            "[Moderation] Observed SeryBot banning %s (%s) in broadcaster %s.",
            username,
            user_id,
            broadcaster_id
        )

        try:
            recorded = await services.moderation.observe_external_ban(
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=username,
                moderator_id=moderator_id,
                moderator_name=moderator_name,
                reason=reason,
                source="serybot"
            )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to process SeryBot ban of %s (%s).",
                username,
                user_id
            )
            return

        if not recorded:
            return

        services.stream_logs.write(
            broadcaster_id,
            "MODERATION",
            (
                f"Recorded SeryBot campaign evidence for "
                f"{username} ({user_id}) | "
                f"Reason: {reason or 'No reason supplied'}"
            )
        )
