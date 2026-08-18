import logging
from dataclasses import dataclass

LOGGER = logging.getLogger("RatBoomBot")


@dataclass
class Broadcaster:
    id: str
    login: str | None = None
    display_name: str | None = None
    profile_image_url: str | None = None
    is_live: bool = False

    @property
    def name(self) -> str | None:
        return self.display_name or self.login


class BroadcasterService:

    def __init__(self, bot, broadcaster_ids: list[str]):
        self.bot = bot
        self.broadcasters: dict[str, Broadcaster] = {}

        for broadcaster_id in broadcaster_ids:
            self.add_broadcaster(broadcaster_id)

    async def setup(self) -> None:
        LOGGER.info(
            "[Broadcasters] Preparing %d broadcasters.",
            len(self.broadcasters)
        )

        await self.refresh_all_broadcasters()

        LOGGER.info(
            "[Broadcasters] Broadcaster service ready with %d broadcasters.",
            len(self.broadcasters)
        )

    def add_broadcaster(self, broadcaster_id: str, broadcaster_name: str | None = None) -> None:
        broadcaster_id = str(broadcaster_id)
        existing = self.broadcasters.get(broadcaster_id)

        if existing is not None:
            if broadcaster_name:
                existing.display_name = broadcaster_name

            LOGGER.debug(
                "[Broadcasters] Broadcaster %s is already tracked.",
                broadcaster_id
            )
            return

        self.broadcasters[broadcaster_id] = Broadcaster(id=broadcaster_id, display_name=broadcaster_name)

        LOGGER.info(
            "[Broadcasters] Added broadcaster %s%s.",
            broadcaster_id,
            f" ({broadcaster_name})" if broadcaster_name else ""
        )

    def remove_broadcaster(self, broadcaster_id: str) -> bool:
        broadcaster_id = str(broadcaster_id)
        broadcaster = self.broadcasters.pop(broadcaster_id, None)

        if broadcaster is None:
            LOGGER.debug(
                "[Broadcasters] Broadcaster %s was not tracked.",
                broadcaster_id
            )
            return False

        LOGGER.info(
            "[Broadcasters] Removed broadcaster %s (%s).",
            broadcaster_id,
            broadcaster.name or "Unknown"
        )

        return True

    async def refresh_all_broadcasters(self) -> None:
        broadcaster_ids = list(self.broadcasters)

        if not broadcaster_ids:
            LOGGER.info("[Broadcasters] No broadcasters are available to refresh.")
            return

        LOGGER.info(
            "[Broadcasters] Refreshing details for %d broadcasters.",
            len(broadcaster_ids)
        )

        try:
            users = await self.bot.fetch_users(ids=broadcaster_ids)
        except Exception:
            LOGGER.exception(
                "[Broadcasters] Failed to resolve broadcaster details."
            )
            return

        resolved_ids: set[str] = set()

        for user in users:
            broadcaster_id = str(user.id)
            resolved_ids.add(broadcaster_id)
            self.update_broadcaster_from_user(user)

        unresolved_ids = set(broadcaster_ids) - resolved_ids

        for broadcaster_id in unresolved_ids:
            LOGGER.warning(
                "[Broadcasters] Twitch did not return details for broadcaster %s.",
                broadcaster_id
            )

        LOGGER.info(
            "[Broadcasters] Refreshed %d of %d broadcasters.",
            len(resolved_ids),
            len(broadcaster_ids)
        )

    async def refresh_broadcaster(self, broadcaster_id: str) -> Broadcaster | None:
        broadcaster_id = str(broadcaster_id)

        LOGGER.debug(
            "[Broadcasters] Refreshing broadcaster %s.",
            broadcaster_id
        )

        try:
            user = await self.bot.fetch_user(id=broadcaster_id)
        except Exception:
            LOGGER.exception(
                "[Broadcasters] Failed to resolve broadcaster %s.",
                broadcaster_id
            )
            return self.broadcasters.get(broadcaster_id)

        if user is None:
            LOGGER.warning(
                "[Broadcasters] No Twitch user found for broadcaster %s.",
                broadcaster_id
            )
            return self.broadcasters.get(broadcaster_id)

        self.update_broadcaster_from_user(user)

        return self.broadcasters.get(broadcaster_id)

    def update_broadcaster_from_user(self, user) -> None:
        broadcaster_id = str(user.id)
        broadcaster = self.broadcasters.get(broadcaster_id)

        if broadcaster is None:
            broadcaster = Broadcaster(id=broadcaster_id)
            self.broadcasters[broadcaster_id] = broadcaster

            LOGGER.info(
                "[Broadcasters] Added broadcaster %s from Twitch user data.",
                broadcaster_id
            )

        broadcaster.login = getattr(user, "name", None)
        broadcaster.display_name = getattr(user, "display_name", None)
        broadcaster.profile_image_url = getattr(user, "profile_image", None)

        LOGGER.debug(
            "[Broadcasters] Resolved broadcaster %s as %s.",
            broadcaster_id,
            broadcaster.name or "Unknown"
        )

    async def refresh_live_statuses(self) -> None:
        if not self.broadcasters:
            LOGGER.debug(
                "[Broadcasters] No broadcasters are available for live-status refresh."
            )
            return

        LOGGER.debug(
            "[Broadcasters] Refreshing live status for %d broadcasters.",
            len(self.broadcasters)
        )

        live_count = 0

        for broadcaster_id, broadcaster in self.broadcasters.items():
            try:
                user = self.bot.create_partialuser(broadcaster_id)
                stream = await user.fetch_stream()
            except Exception:
                LOGGER.exception(
                    "[Broadcasters] Failed to check live status for broadcaster %s.",
                    broadcaster_id,
                    extra={"broadcaster_id": broadcaster_id}
                )
                broadcaster.is_live = False
                continue

            broadcaster.is_live = stream is not None

            if broadcaster.is_live:
                live_count += 1

            LOGGER.debug(
                "[Broadcasters] Broadcaster %s is %s.",
                broadcaster_id,
                "live" if broadcaster.is_live else "offline"
            )

        LOGGER.debug(
            "[Broadcasters] Live-status refresh complete. %d of %d broadcasters are live.",
            live_count,
            len(self.broadcasters)
        )

    def get_broadcasters(self) -> dict[str, Broadcaster]:
        return self.broadcasters.copy()

    async def get_live_broadcasters(self) -> dict[str, str]:
        await self.refresh_live_statuses()

        return {
            broadcaster_id: broadcaster.name or broadcaster_id
            for broadcaster_id, broadcaster in self.broadcasters.items()
            if broadcaster.is_live
        }

    async def get_offline_broadcasters(self) -> dict[str, str]:
        await self.refresh_live_statuses()

        return {
            broadcaster_id: broadcaster.name or broadcaster_id
            for broadcaster_id, broadcaster in self.broadcasters.items()
            if not broadcaster.is_live
        }
