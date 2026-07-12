import asyncio
import logging
from pathlib import Path

import asqlite
import uvicorn
from rich.logging import RichHandler

from bot.bot import TwitchBot
from config.settings import settings
from storage.database import setup_database
from web.app import app as admin_app
from web.state import set_runtime

LOGGER = logging.getLogger("Bot")


async def run_runtime():
    database_path = Path(settings.DATABASE_PATH)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    async with asqlite.create_pool(str(database_path)) as db:
        tokens, subs, broadcaster_ids = await setup_database(db)

        async with TwitchBot(
            token_database=db,
            subs=subs,
            broadcaster_ids=broadcaster_ids
        ) as bot:
            for token, refresh in tokens:
                await bot.add_token(token, refresh)

            set_runtime(
                twitch_bot=bot,
                token_database=db
            )

            admin_server = uvicorn.Server(
                uvicorn.Config(
                    admin_app,
                    host=settings.ADMIN_HOST,
                    port=settings.ADMIN_PORT,
                    log_level="info"
                )
            )

            LOGGER.info(
                "Admin dashboard available at %s",
                settings.ADMIN_BASE_URL
            )

            await asyncio.gather(
                bot.start(load_tokens=False),
                admin_server.serve()
            )


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                markup=True
            )
        ]
    )

    try:
        asyncio.run(run_runtime())
    except KeyboardInterrupt:
        LOGGER.warning("Shutting down...")
