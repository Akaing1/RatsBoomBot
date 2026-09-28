import random

from storage.transactions import immediate_transaction


class QuoteService:
    def __init__(self, db):
        self.db = db

    async def add(self, broadcaster_id: str, message: str, added_by: str) -> int:
        async with self.db.acquire() as connection:
            async with immediate_transaction(connection):
                row = await connection.fetchone(
                    """
                    INSERT INTO channel_quote_sequences (broadcaster_id, last_number)
                    VALUES (?, 1)
                    ON CONFLICT (broadcaster_id) DO UPDATE SET last_number = last_number + 1
                    RETURNING last_number
                    """,
                    (broadcaster_id,),
                )
                number = int(row["last_number"])
                await connection.execute(
                    "INSERT INTO channel_quotes (broadcaster_id, number, message, added_by) VALUES (?, ?, ?, ?)",
                    (broadcaster_id, number, message, added_by),
                )
                return number

    async def get(self, broadcaster_id: str, number: int) -> str | None:
        async with self.db.acquire() as connection:
            row = await connection.fetchone(
                "SELECT message FROM channel_quotes WHERE broadcaster_id = ? AND number = ?",
                (broadcaster_id, number),
            )
        return str(row["message"]) if row else None

    async def random(self, broadcaster_id: str) -> tuple[int, str] | None:
        async with self.db.acquire() as connection:
            rows = await connection.fetchall(
                "SELECT number, message FROM channel_quotes WHERE broadcaster_id = ?",
                (broadcaster_id,),
            )
        if not rows:
            return None
        row = random.choice(rows)
        return int(row["number"]), str(row["message"])

    async def remove(self, broadcaster_id: str, number: int) -> bool:
        async with self.db.acquire() as connection:
            async with immediate_transaction(connection):
                row = await connection.fetchone(
                    "DELETE FROM channel_quotes WHERE broadcaster_id = ? AND number = ? RETURNING number",
                    (broadcaster_id, number),
                )
                if row is None:
                    return False

                # Move affected numbers into a temporary negative range so the
                # channel's (broadcaster_id, number) primary key never collides.
                await connection.execute(
                    "UPDATE channel_quotes SET number = -number WHERE broadcaster_id = ? AND number > ?",
                    (broadcaster_id, number),
                )
                await connection.execute(
                    "UPDATE channel_quotes SET number = -number - 1 WHERE broadcaster_id = ? AND number < 0",
                    (broadcaster_id,),
                )
                await connection.execute(
                    "UPDATE channel_quote_sequences SET last_number = last_number - 1 WHERE broadcaster_id = ?",
                    (broadcaster_id,),
                )
                return True
