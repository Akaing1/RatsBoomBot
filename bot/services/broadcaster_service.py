import logging
from dataclasses import dataclass

LOGGER = logging.getLogger("Bot")


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
        await self.refresh_all_broadcasters()
        LOGGER.info("Loaded %s broadcasters.", len(self.broadcasters))

    def add_broadcaster(self, broadcaster_id: str, broadcaster_name: str | None = None) -> None:
        existing = self.broadcasters.get(broadcaster_id)

        if existing:
            if broadcaster_name:
                existing.display_name = broadcaster_name

            return

        self.broadcasters[broadcaster_id] = Broadcaster(
            id=broadcaster_id,
            display_name=broadcaster_name
        )

    def remove_broadcaster(self, broadcaster_id: str) -> bool:
        broadcaster = self.broadcasters.pop(broadcaster_id, None)

        if broadcaster is None:
            return False

        LOGGER.info(
            "Removed broadcaster %s (%s).",
            broadcaster_id,
            broadcaster.name or "Unknown"
        )
        return True

    async def refresh_all_broadcasters(self) -> None:
        broadcaster_ids = list(self.broadcasters.keys())

        if not broadcaster_ids:
            return

        try:
            users = await self.bot.fetch_users(ids=broadcaster_ids)
        except Exception as error:
            LOGGER.error("Failed to resolve broadcaster details: %r", error)
            return

        for user in users:
            self.update_broadcaster_from_user(user)

    async def refresh_broadcaster(self, broadcaster_id: str) -> Broadcaster | None:
        try:
            user = await self.bot.fetch_user(id=broadcaster_id)
        except Exception as error:
            LOGGER.error(
                "Failed to resolve broadcaster %s: %r",
                broadcaster_id,
                error
            )
            return self.broadcasters.get(broadcaster_id)

        if user is None:
            LOGGER.warning("No Twitch user found for broadcaster %s.", broadcaster_id)
            return self.broadcasters.get(broadcaster_id)

        self.update_broadcaster_from_user(user)
        return self.broadcasters.get(broadcaster_id)

    def update_broadcaster_from_user(self, user) -> None:
        broadcaster_id = str(user.id)

        broadcaster = self.broadcasters.get(broadcaster_id)

        if broadcaster is None:
            broadcaster = Broadcaster(id=broadcaster_id)
            self.broadcasters[broadcaster_id] = broadcaster

        broadcaster.login = getattr(user, "name", None)
        broadcaster.display_name = getattr(user, "display_name", None)
        broadcaster.profile_image_url = getattr(user, "profile_image", None)

        LOGGER.info(
            "Resolved broadcaster %s as %s.",
            broadcaster_id,
            broadcaster.name or "Unknown"
        )

    async def refresh_live_statuses(self) -> None:
        for broadcaster_id, broadcaster in self.broadcasters.items():
            try:
                user = self.bot.create_partialuser(broadcaster_id)
                stream = await user.fetch_stream()
                broadcaster.is_live = stream is not None
            except Exception as error:
                broadcaster.is_live = False
                LOGGER.warning(
                    "Failed checking live status for broadcaster %s: %r",
                    broadcaster_id,
                    error
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
