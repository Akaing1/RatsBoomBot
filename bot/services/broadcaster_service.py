class BroadcasterService:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.broadcasters: dict[str, str] = {}

    async def setup(self) -> None:
        # TODO: load authorized users from your token table
        # self.broadcasters[user_id] = username
        pass

    def add_broadcaster(self, broadcaster_id: str, broadcaster_name: str | None = None) -> None:
        self.broadcasters[broadcaster_id] = broadcaster_name or broadcaster_id

    def get_broadcasters(self) -> dict[str, str]:
        return self.broadcasters.copy()

    async def get_live_broadcasters(self) -> dict[str, str]:
        live = {}

        for broadcaster_id, broadcaster_name in self.broadcasters.items():
            broadcaster = self.bot.create_partialuser(broadcaster_id)
            stream = await broadcaster.fetch_stream()

            if stream is not None:
                live[broadcaster_id] = broadcaster_name

        return live
