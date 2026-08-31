import asyncio
import logging
import os
import signal

LOGGER = logging.getLogger("RatBoomBot")

# Give the browser and reverse proxy enough time to receive the restarting page
# before this process closes its active connections.
RESTART_DELAY_SECONDS = 5.0


async def restart_runtime() -> None:
    await asyncio.sleep(RESTART_DELAY_SECONDS)

    LOGGER.warning("[Runtime] Restart requested from the administrator dashboard.")
    os.kill(os.getpid(), signal.SIGTERM)
