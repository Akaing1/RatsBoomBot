import asyncio
import logging

import asqlite
import uvicorn

from bot.bot import TwitchBot
from config.settings import settings
from storage.database import setup_database
from web.app import app as web_app

LOGGER = logging.getLogger("Bot")


async def run_runtime():
    async with asqlite.create_pool(settings.DATABASE_PATH) as db:
        tokens, subs, broadcaster_ids = await setup_database(db)

        async with TwitchBot(
            token_database=db,
            subs=subs,
            broadcaster_ids=broadcaster_ids
        ) as bot:
            for token, refresh in tokens:
                await bot.add_token(token, refresh)

            server = uvicorn.Server(
                uvicorn.Config(
                    web_app,
                    host="0.0.0.0",
                    port=4343,
                    log_level="info"
                )
            )

            await asyncio.gather(
                bot.start(load_tokens=False),
                server.serve()
            )


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s"
    )

    try:
        asyncio.run(run_runtime())
    except KeyboardInterrupt:
        LOGGER.warning("Shutting down...")
