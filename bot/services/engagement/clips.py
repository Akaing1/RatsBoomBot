import asyncio
import math

from bot.profiles import ClipConfig, render_profile_message


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
            return created_clip

    async def wait_for_clip(self, broadcaster_id: str, clip_id: str, timeout_seconds: int):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds

        while loop.time() < deadline:
            clips = self.bot.fetch_clips(clip_ids=[clip_id], token_for=str(broadcaster_id), max_results=1)

            async for clip in clips:
                return clip

            await asyncio.sleep(1)

        return None
