from dataclasses import dataclass
import logging

LOGGER = logging.getLogger("Bot")


@dataclass
class Broadcaster:
    id: str
    name: str | None = None
    is_live: bool = False


class BroadcasterService:
    def __init__(self, bot, broadcaster_ids: list[str]):
        self.bot = bot
        self.broadcasters: dict[str, Broadcaster] = {}

        for broadcaster_id in broadcaster_ids:
            self.add_broadcaster(broadcaster_id)

    async def setup(self) -> None:
        LOGGER.info("Loaded %s broadcasters.", len(self.broadcasters))

    def add_broadcaster(self, broadcaster_id: str, broadcaster_name: str | None = None, ) -> None:
        self.broadcasters[broadcaster_id] = Broadcaster(
            id=broadcaster_id,
            name=broadcaster_name,
        )

    def get_broadcasters(self) -> dict[str, Broadcaster]:
        return self.broadcasters.copy()

    async def get_live_broadcasters(self) -> dict[str, str]:
        live_broadcasters: dict[str, str] = {}

        for broadcaster_id, broadcaster in self.broadcasters.items():
            user = self.bot.create_partialuser(broadcaster_id)
            stream = await user.fetch_stream()

            broadcaster.is_live = stream is not None

            if broadcaster.is_live:
                live_broadcasters[broadcaster_id] = broadcaster.name or broadcaster_id

        return live_broadcasters

    async def get_offline_broadcasters(self) -> dict[str, str]:
        offline_broadcasters: dict[str, str] = {}

        for broadcaster_id, broadcaster in self.broadcasters.items():
            user = self.bot.create_partialuser(broadcaster_id)
            stream = await user.fetch_stream()

            broadcaster.is_live = stream is not None

            if not broadcaster.is_live:
                offline_broadcasters[broadcaster_id] = broadcaster.name or broadcaster_id

        return offline_broadcasters
