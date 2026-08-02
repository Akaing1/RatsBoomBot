import asyncio
import logging
import sys
from pathlib import Path
from time import perf_counter

import asqlite
import uvicorn
from rich.logging import RichHandler

from bot.bot import TwitchBot
from config.settings import settings
from storage.database import setup_database
from web.app import app as admin_app
from web.state import set_runtime

LOGGER = logging.getLogger("RatBoomBot")
SEPARATOR = "=" * 60


async def run_runtime() -> None:
    startup_started_at = perf_counter()
    database_path = Path(settings.DATABASE_PATH)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    LOGGER.info(SEPARATOR)
    LOGGER.info("[Startup] RatBoomBot v4.1.1 starting.")
    LOGGER.info("[Startup] Python %s", sys.version.split()[0])
    LOGGER.info("[Startup] Database path: %s", database_path)
    LOGGER.info("[Startup] Admin dashboard: %s", settings.ADMIN_BASE_URL)
    LOGGER.info(SEPARATOR)

    LOGGER.info("[Database] Opening SQLite connection pool.")

    try:
        async with asqlite.create_pool(str(database_path)) as database:
            LOGGER.info("[Database] SQLite connection pool opened.")

            setup_started_at = perf_counter()
            tokens, subscriptions, broadcaster_ids = await setup_database(database)

            LOGGER.info(
                "[Database] Startup data loaded in %.3f seconds: "
                "%d tokens, %d broadcasters, %d EventSub subscriptions.",
                perf_counter() - setup_started_at,
                len(tokens),
                len(broadcaster_ids),
                len(subscriptions)
            )

            LOGGER.info("[Runtime] Creating Twitch bot instance.")

            async with TwitchBot(token_database=database, subs=subscriptions, broadcaster_ids=broadcaster_ids) as bot:
                LOGGER.info("[OAuth] Loading %d stored OAuth tokens.", len(tokens))

                for token, refresh_token in tokens:
                    await bot.add_token(token, refresh_token)

                LOGGER.info("[OAuth] Stored OAuth tokens loaded.")

                set_runtime(
                    twitch_bot=bot,
                    token_database=database
                )

                LOGGER.info("[Runtime] Shared runtime state initialized.")

                admin_server = uvicorn.Server(
                    uvicorn.Config(
                        admin_app,
                        host=settings.ADMIN_HOST,
                        port=settings.ADMIN_PORT,
                        log_level="info"
                    )
                )

                LOGGER.info("[Runtime] Starting Twitch bot.")
                LOGGER.info(
                    "[Dashboard] Starting admin dashboard at %s.",
                    settings.ADMIN_BASE_URL
                )
                LOGGER.info(
                    "[Startup] Runtime initialization completed in %.3f seconds.",
                    perf_counter() - startup_started_at
                )

                await asyncio.gather(
                    bot.start(load_tokens=False),
                    admin_server.serve()
                )

    except asyncio.CancelledError:
        LOGGER.info("[Shutdown] Runtime tasks were cancelled.")
        raise
    except Exception:
        LOGGER.exception("[Startup] Fatal error while running RatBoomBot.")
        raise
    finally:
        LOGGER.info("[Shutdown] Runtime resources released.")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                markup=True
            )
        ],
        force=True
    )


def run() -> None:
    configure_logging()

    try:
        asyncio.run(run_runtime())
    except KeyboardInterrupt:
        LOGGER.info("[Shutdown] Shutdown requested by user.")
    except Exception:
        LOGGER.critical(
            "[Shutdown] RatBoomBot stopped because of a fatal error."
        )
        raise
    else:
        LOGGER.info("[Shutdown] RatBoomBot stopped cleanly.")
