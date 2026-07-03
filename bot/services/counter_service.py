import logging

LOGGER = logging.getLogger("Bot")


class CounterService:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    async def setup(self) -> None:
        query = """
        CREATE TABLE IF NOT EXISTS counters (
            name TEXT PRIMARY KEY,
            value INTEGER NOT NULL DEFAULT 0
        )
        """

        async with self.db.acquire() as connection:
            await connection.execute(query)

    async def get_counter(self, name: str) -> int:
        query = "SELECT value FROM counters WHERE name = ?"

        async with self.db.acquire() as connection:
            row = await connection.fetchone(query, (name.lower(),))

        if not row:
            return 0

        return row["value"]

    async def increment_counter(self, name: str, amount: int = 1) -> int:
        current_value = await self.get_counter(name)
        new_value = current_value + amount

        query = """
        INSERT INTO counters (name, value)
        VALUES (?, ?)
        ON CONFLICT(name) DO UPDATE SET
            value = excluded.value
        """

        async with self.db.acquire() as connection:
            await connection.execute(query, (name.lower(), new_value))

        LOGGER.info("Counter %s increased to %s", name, new_value)

        return new_value
