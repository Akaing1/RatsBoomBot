import asyncio
import logging

import asqlite
import uvicorn

from bot.bot import TwitchBot
from config.settings import settings
from database.db import setup_database
from web.app import app as web_app

LOGGER = logging.getLogger("Bot")


async def run_bot_and_web():
    async with asqlite.create_pool(settings.DATABASE_PATH) as db:
        tokens, subs, broadcaster_ids = await setup_database(db)

        bot = TwitchBot(
            token_database=db,
            subs=subs,
            broadcaster_ids=broadcaster_ids
        )

        for token, refresh in tokens:
            await bot.add_token(token, refresh)

        config = uvicorn.Config(
            web_app,
            host="0.0.0.0",
            port=4343,
            log_level="info"
        )
        server = uvicorn.Server(config)

        async with bot:
            await asyncio.gather(
                bot.start(),
                server.serve()
            )


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s"
    )

    asyncio.run(run_bot_and_web())


if __name__ == "__main__":
    run()
