import logging

LOGGER = logging.getLogger("RatBoomBot")


class CounterService:

    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    async def setup(self) -> None:
        LOGGER.info("[Counters] Preparing counter storage.")

        query = """
        CREATE TABLE IF NOT EXISTS counters (
            name TEXT PRIMARY KEY,
            value INTEGER NOT NULL DEFAULT 0
        )
        """

        try:
            async with self.db.acquire() as connection:
                await connection.execute(query)
        except Exception:
            LOGGER.exception("[Counters] Failed to prepare counter storage.")
            raise

        LOGGER.info("[Counters] Counter storage ready.")

    async def get_counter(self, name: str) -> int:
        counter_name = name.lower()

        query = """
        SELECT value
        FROM counters
        WHERE name = ?
        """

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(query, (counter_name,))
        except Exception:
            LOGGER.exception(
                "[Counters] Failed to load counter %s.",
                counter_name
            )
            raise

        if not row:
            LOGGER.debug(
                "[Counters] Counter %s does not exist. Returning zero.",
                counter_name
            )
            return 0

        return int(row["value"])

    async def increment_counter(self, name: str, amount: int = 1) -> int:
        counter_name = name.lower()

        query = """
        INSERT INTO counters (name, value)
        VALUES (?, ?)
        ON CONFLICT(name) DO UPDATE SET
            value = counters.value + excluded.value
        RETURNING value
        """

        try:
            async with self.db.acquire() as connection:
                row = await connection.fetchone(query, (counter_name, amount))
        except Exception:
            LOGGER.exception(
                "[Counters] Failed to increment counter %s by %d.",
                counter_name,
                amount
            )
            raise

        new_value = int(row["value"])

        LOGGER.info(
            "[Counters] Counter %s increased by %d to %d.",
            counter_name,
            amount,
            new_value
        )

        return new_value
