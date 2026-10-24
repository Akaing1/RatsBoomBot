import logging

from twitchio.ext import commands

from config.settings import settings
from bot.shared.pending_raids import raid_lock, raid_state, remember_raid

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
        if action in {"raid", "unraid"}:
            broadcaster_id = str(payload.broadcaster.id)
            source = getattr(payload, "source_broadcaster", None)
            source_id = getattr(source, "id", None)
            # TwitchIO wraps even a missing source ID in PartialUser, whose
            # ID becomes the string "None". This is not another channel.
            has_external_source = source_id not in {None, "", "None", broadcaster_id}
            channels = getattr(services, "broadcasters", None)
            LOGGER.info("[Dashboard] Twitch %s event: broadcaster=%s source=%s target=%s.",
                        action, broadcaster_id, source_id,
                        getattr(getattr(getattr(payload, "raid", None), "user", None), "id", None)
                        if action == "raid" else getattr(getattr(payload, "unraid", None), "id", None))
            if (channels is not None and broadcaster_id in channels.get_broadcasters()
                    and not has_external_source):
                async with raid_lock(self.bot, broadcaster_id):
                    if action == "raid":
                        target = getattr(getattr(payload, "raid", None), "user", None)
                        if target is not None:
                            # Moderation events only carry a PartialUser, without a picture.
                            fetch_user = getattr(self.bot, "fetch_user", None)
                            pending = raid_state(self.bot).get(broadcaster_id)
                            has_picture = (pending and pending["target_id"] == str(target.id)
                                           and pending.get("profile_image_url"))
                            if fetch_user is not None and not has_picture:
                                try:
                                    target = await fetch_user(id=str(target.id)) or target
                                except Exception:
                                    LOGGER.warning("[Dashboard] Could not load raid target profile for %s.",
                                                   target.id, exc_info=True)
                            remember_raid(self.bot, broadcaster_id, target, getattr(payload, "timestamp", None))
                            LOGGER.info("[Dashboard] Pending raid recorded for %s to %s.", broadcaster_id, target.id)
                    else:
                        pending = raid_state(self.bot).get(broadcaster_id)
                        target = getattr(payload, "unraid", None)
                        if pending and (target is None or pending["target_id"] == str(target.id)):
                            raid_state(self.bot).pop(broadcaster_id, None)
        moderator = getattr(payload, "moderator", None)
        ban = getattr(payload, "ban", None)

        live_chat = getattr(services, "live_chat", None)
        if live_chat is not None:
            live_chat.record_mod_action(payload)
            if action == "clear":
                live_chat.clear_chat(str(payload.broadcaster.id))

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
            "[Moderation] Observed SeryBot banning %s (%s) in broadcaster %s | Moderator: %s (%s) | Reason: %s",
            username,
            user_id,
            broadcaster_id,
            moderator_name,
            moderator_id,
            reason or "No reason supplied",
            extra={"broadcaster_id": broadcaster_id}
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
                "[Moderation] Failed to process SeryBot ban of %s (%s) in broadcaster %s.",
                username,
                user_id,
                broadcaster_id,
                extra={"broadcaster_id": broadcaster_id}
            )
            return

        if not recorded:
            LOGGER.info(
                "[Moderation] SeryBot ban evidence for %s (%s) in broadcaster %s was already recorded.",
                username,
                user_id,
                broadcaster_id,
                extra={"broadcaster_id": broadcaster_id}
            )
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

    @commands.Component.listener()
    async def event_automod_message_hold(self, payload) -> None:
        services = self.bot.services
        if services is not None and getattr(services, "live_chat", None) is not None:
            services.live_chat.hold_automod_message(payload)

    @commands.Component.listener()
    async def event_automod_message_update(self, payload) -> None:
        services = self.bot.services
        if services is not None and getattr(services, "live_chat", None) is not None:
            services.live_chat.resolve_automod_message(str(payload.broadcaster.id), str(payload.message_id))

    @commands.Component.listener()
    async def event_message_delete(self, payload) -> None:
        services = self.bot.services
        if services is None or getattr(services, "live_chat", None) is None:
            return
        message_id = f"twitch:{payload.message_id}"
        await services.live_chat.remove_message(str(payload.broadcaster.id), message_id)
