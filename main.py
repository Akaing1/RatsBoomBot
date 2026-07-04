import asyncio
import logging

import asqlite
import twitchio

from bot.bot import TwitchBot
from config.settings import settings
from database.db import setup_database

LOGGER = logging.getLogger("Bot")


async def runner():
    async with asqlite.create_pool(settings.DATABASE_PATH) as db:
        tokens, subs, broadcaster_ids = await setup_database(db)

        async with TwitchBot(token_database=db, subs=subs) as bot:
            for token_pair in tokens:
                await bot.add_token(*token_pair)

            await bot.start(load_tokens=False)


def main():
    twitchio.utils.setup_logging(level=logging.INFO)

    try:
        asyncio.run(runner())

    except KeyboardInterrupt:
        LOGGER.warning("Shutting down...")


if __name__ == "__main__":
    main()
