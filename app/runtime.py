


import asyncio
import logging
import sys
from pathlib import Path
from time import perf_counter
from aiohttp.web_runner import GracefulExit

import asqlite
import uvicorn
from rich.logging import RichHandler

from bot.bot import TwitchBot
from app.runtime_logs import runtime_log_buffer
from config.settings import settings
from config.version import APP_NAME, APP_VERSION
from storage.database import setup_database
from web.app import app as admin_app
from web.state import clear_runtime, set_runtime

LOGGER = logging.getLogger("RatBoomBot")
SEPARATOR = "=" * 60


async def run_services(bot: TwitchBot, admin_server: uvicorn.Server) -> None:
    bot_task = asyncio.create_task(bot.start(load_tokens=False), name="twitch-bot")
    admin_task = asyncio.create_task(admin_server.serve(), name="admin-dashboard")
    tasks = {bot_task, admin_task}

    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        for task in done:
            exception = task.exception()

            if exception is not None:
                raise exception

        if admin_task in done and not bot_task.done():
            LOGGER.info("[Shutdown] Admin dashboard stopped; closing Twitch bot.")
            await bot.close()

        if bot_task in done and not admin_task.done():
            LOGGER.info("[Shutdown] Twitch bot stopped; closing admin dashboard.")
            admin_server.should_exit = True

        if pending:
            await asyncio.gather(*pending)
    finally:
        admin_server.should_exit = True

        if not bot_task.done():
            await bot.close()

        await asyncio.gather(*tasks, return_exceptions=True)


async def run_runtime() -> None:
    startup_started_at = perf_counter()
    database_path = Path(settings.DATABASE_PATH)
    league_database_path = Path(settings.LEAGUE_DATABASE_PATH)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    league_database_path.parent.mkdir(parents=True, exist_ok=True)

    LOGGER.info(SEPARATOR)
    LOGGER.info("[Startup] %s v%s starting.", APP_NAME, APP_VERSION)
    LOGGER.info("[Startup] Python %s", sys.version.split()[0])
    LOGGER.info("[Startup] Database path: %s", database_path)
    LOGGER.info("[Startup] League database path: %s", league_database_path)
    LOGGER.info("[Startup] Admin dashboard: %s", settings.ADMIN_BASE_URL)
    LOGGER.info(SEPARATOR)

    LOGGER.info("[Database] Opening SQLite connection pool.")

    try:
        async with asqlite.create_pool(str(database_path)) as database, asqlite.create_pool(str(league_database_path)) as league_database:
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

            async with TwitchBot(token_database=database, league_database=league_database, subs=subscriptions, broadcaster_ids=broadcaster_ids) as bot:
                LOGGER.info("[OAuth] Loading %d stored OAuth tokens.", len(tokens))

                for token, refresh_token in tokens:
                    await bot.add_token(token, refresh_token)

                LOGGER.info("[OAuth] Stored OAuth tokens loaded.")

                set_runtime(twitch_bot=bot, token_database=database)

                LOGGER.info("[Runtime] Shared runtime state initialized.")

                admin_config = uvicorn.Config(
                    admin_app,
                    host=settings.ADMIN_HOST,
                    port=settings.ADMIN_PORT,
                    log_level="info",
                    proxy_headers=settings.TRUST_PROXY_HEADERS,
                    forwarded_allow_ips="127.0.0.1" if settings.TRUST_PROXY_HEADERS else None
                )

                admin_server = uvicorn.Server(admin_config)

                LOGGER.info("[Runtime] Starting Twitch bot.")
                LOGGER.info(
                    "[Dashboard] Starting admin dashboard at %s.",
                    settings.ADMIN_BASE_URL
                )
                LOGGER.info(
                    "[Startup] Runtime initialization completed in %.3f seconds.",
                    perf_counter() - startup_started_at
                )

                try:
                    await run_services(bot, admin_server)
                finally:
                    clear_runtime()
                    LOGGER.info("[Runtime] Shared runtime state cleared.")
    except asyncio.CancelledError:
        LOGGER.info("[Shutdown] Runtime tasks were cancelled.")
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
        handlers=[RichHandler(rich_tracebacks=True, markup=True)],
        force=True
    )

    logger = logging.getLogger("RatBoomBot")

    if runtime_log_buffer not in logger.handlers:
        logger.addHandler(runtime_log_buffer)


def run() -> None:
    configure_logging()

    try:
        asyncio.run(run_runtime())
    except (KeyboardInterrupt, GracefulExit):
        LOGGER.info("[Shutdown] Shutdown requested.")
    except Exception:
        LOGGER.critical("[Shutdown] RatBoomBot stopped because of a fatal error.")
        raise
    else:
        LOGGER.info("[Shutdown] RatBoomBot stopped cleanly.")
