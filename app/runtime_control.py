import asyncio
import logging
import os
import signal

LOGGER = logging.getLogger("RatBoomBot")

RESTART_DELAY_SECONDS = 1.0


async def restart_runtime() -> None:
    await asyncio.sleep(RESTART_DELAY_SECONDS)

    LOGGER.warning("[Runtime] Restart requested from the administrator dashboard.")
    os.kill(os.getpid(), signal.SIGTERM)
