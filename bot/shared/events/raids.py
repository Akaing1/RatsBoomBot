import logging
import time

from twitchio.ext import commands

from bot.services.stream.automatic_shoutouts import automatic_shoutout
from storage.incoming_raids import record_incoming_raid

LOGGER = logging.getLogger("RatBoomBot")


class RaidEvents(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @commands.Component.listener()
    async def event_raid(self, payload) -> None:
        await self.handle_raid(payload)

    async def handle_raid(self, payload) -> None:
        raider = getattr(payload, "from_broadcaster", None)
        broadcaster = getattr(payload, "to_broadcaster", None)
        viewer_count = getattr(payload, "viewer_count", None)
        services = self.bot.services

        if raider is None or broadcaster is None:
            LOGGER.warning(
                "[Events] Could not process raid because the payload was incomplete: %r",
                payload
            )
            return

        raider_name = getattr(raider, "name", None)
        raider_id = getattr(raider, "id", None)
        broadcaster_name = getattr(broadcaster, "name", None) or "unknown"
        broadcaster_id = str(broadcaster.id)

        if not raider_name or raider_id is None:
            LOGGER.warning(
                "[Events] Could not determine the raider identity from payload: %r",
                payload
            )
            return

        raider_id = str(raider_id)

        pending = getattr(self.bot, "_dashboard_pending_raids", {}).get(raider_id)
        if pending and pending.get("target_id") == broadcaster_id and time.time() <= pending["expires_at"] + 120:
            # Only the completed raid event reports participants, including offline lurkers.
            pending["viewer_count"] = (
                viewer_count if isinstance(viewer_count, int) and not isinstance(viewer_count, bool)
                and viewer_count >= 0 else None
            )
            pending["completed"] = True
        # Outgoing subscriptions must not trigger responses in unrelated channels.
        connected = getattr(services, "broadcasters", None)
        if connected is not None and broadcaster_id not in connected.get_broadcasters():
            return
        recent = getattr(self, "_recent_raids", {})
        key = (raider_id, broadcaster_id)
        now = time.monotonic()
        if now - recent.get(key, -60) < 10:
            return
        self._recent_raids = {key_: at for key_, at in recent.items() if now - at < 10}
        self._recent_raids[key] = now

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

        if services is None:
            LOGGER.warning(
                "[Events] Raid event received before services were initialized."
            )
            return

        try:
            await record_incoming_raid(services.db, broadcaster_id, raider_id)
        except Exception:
            LOGGER.exception("[Events] Could not record incoming raid for %s.", broadcaster_id)

        services.stream_logs.write(
            broadcaster_id,
            "RAID",
            f"{raider_name} raided with {viewer_count} {viewer_word}."
        )

        await automatic_shoutout(self.bot, broadcaster_id, raider_id, raider_name, "raid", viewer_count)
