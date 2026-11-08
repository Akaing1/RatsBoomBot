import asyncio
from asyncio import CancelledError
import math
import logging

from aiohttp import ClientError
from twitchio import HTTPException

from bot.profiles import ClipConfig, render_profile_message


LOGGER = logging.getLogger(__name__)


class ClipInProgressError(RuntimeError):
    pass


class ClipOnCooldownError(RuntimeError):

    def __init__(self, remaining_seconds: int):
        self.remaining_seconds = remaining_seconds
        super().__init__(f"Clips are on cooldown for another {remaining_seconds} seconds.")


class ClipService:

    def __init__(self, bot):
        self.bot = bot
        self._locks: dict[str, asyncio.Lock] = {}
        self._cooldowns: dict[str, float] = {}

    def cooldown_remaining(self, broadcaster_id: str) -> int:
        expires_at = self._cooldowns.get(str(broadcaster_id), 0.0)
        return max(0, math.ceil(expires_at - asyncio.get_running_loop().time()))

    async def create_clip(self, broadcaster_id: str, channel_name: str, username: str, duration: int, config: ClipConfig):
        broadcaster_id = str(broadcaster_id)
        lock = self._locks.setdefault(broadcaster_id, asyncio.Lock())

        if lock.locked():
            raise ClipInProgressError("Another clip is already being created.")

        async with lock:
            remaining_seconds = self.cooldown_remaining(broadcaster_id)

            if remaining_seconds:
                raise ClipOnCooldownError(remaining_seconds)

            title = render_profile_message(config.title, channel_name=channel_name, username=username)
            broadcaster = self.bot.create_partialuser(broadcaster_id)
            created_clip = await broadcaster.create_clip(token_for=broadcaster_id, title=title, duration=duration)
            self._cooldowns[broadcaster_id] = asyncio.get_running_loop().time() + config.cooldown_seconds
            LOGGER.info("[Clips] Create accepted: clip=%s broadcaster=%s duration=%ss",
                        created_clip.id, broadcaster_id, duration)
            return created_clip

    async def wait_for_clip(self, broadcaster_id: str, clip_id: str, timeout_seconds: int):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        retry_delay = 1
        started = loop.time()
        attempts = empty = errors = 0
        outcome = "deadline"

        try:
            while (remaining := deadline - loop.time()) > 0:
                attempts += 1
                try:
                    async with asyncio.timeout(remaining):
                        clips = self.bot.fetch_clips(clip_ids=[clip_id], token_for=str(broadcaster_id), max_results=1)
                        async for clip in clips:
                            outcome = "found"
                            LOGGER.info("[Clips] Lookup: clip=%s broadcaster=%s attempt=%d result=found",
                                        clip_id, broadcaster_id, attempts)
                            return clip
                    empty += 1
                    LOGGER.info("[Clips] Lookup: clip=%s broadcaster=%s attempt=%d result=empty",
                                clip_id, broadcaster_id, attempts)
                except HTTPException as error:
                    errors += 1
                    retryable = error.status == 429 or 500 <= error.status < 600
                    LOGGER.warning("[Clips] Lookup: clip=%s broadcaster=%s attempt=%d result=http_error status=%s retryable=%s",
                                   clip_id, broadcaster_id, attempts, error.status, retryable)
                    if not retryable:
                        outcome = "http_error"
                        raise
                except (ClientError, TimeoutError) as error:
                    errors += 1
                    result = "timeout" if isinstance(error, TimeoutError) else "network_error"
                    # Never log exception text, headers, or tokens.
                    LOGGER.warning("[Clips] Lookup: clip=%s broadcaster=%s attempt=%d result=%s",
                                   clip_id, broadcaster_id, attempts, result)
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                await asyncio.sleep(min(retry_delay, remaining))
                retry_delay = min(5, retry_delay * 2)
            return None
        except CancelledError:
            outcome = "cancelled"
            raise
        except Exception:
            if outcome != "http_error":
                outcome = "unexpected_error"
            raise
        finally:
            LOGGER.info("[Clips] Lookup summary: clip=%s broadcaster=%s outcome=%s attempts=%d empty=%d errors=%d elapsed=%.1fs",
                        clip_id, broadcaster_id, outcome, attempts, empty, errors, loop.time() - started)
