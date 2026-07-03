import asqlite
from twitchio import eventsub

from config.settings import settings


async def setup_database(db: asqlite.Pool, ) -> tuple[list[tuple[str, str]], list[eventsub.SubscriptionPayload]]:
    query = """
    CREATE TABLE IF NOT EXISTS tokens(
        user_id TEXT PRIMARY KEY,
        token TEXT NOT NULL,
        refresh TEXT NOT NULL
    )
    """

    async with db.acquire() as connection:
        await connection.execute(query)

        rows = await connection.fetchall("SELECT * FROM tokens")

        tokens = []
        subs = []

        for row in rows:
            tokens.append((row["token"], row["refresh"]))

            if row["user_id"] == settings.BOT_ID:
                continue

            subs.append(eventsub.ChatMessageSubscription(broadcaster_user_id=row["user_id"], user_id=settings.BOT_ID, ))

    return tokens, subs


async def save_token(db: asqlite.Pool, user_id: str, token: str, refresh: str, ):
    query = """
    INSERT INTO tokens (user_id, token, refresh)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id)
    DO UPDATE SET
        token = excluded.token,
        refresh = excluded.refresh
    """

    async with db.acquire() as connection:
        await connection.execute(query, (user_id, token, refresh), )
