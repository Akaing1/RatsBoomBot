import asyncio
import logging
import random
import time

from twitchio import User
from twitchio.ext import commands

from bot.profiles import FeatureName
from bot.shared.commands.helpers import get_context_broadcaster_id, is_feature_enabled

LOGGER = logging.getLogger("RatBoomBot")


class ModActionCommands(commands.Component):
    KAMIKAZE_DURATION_SECONDS = 10
    KAMIKAZE_SUCCESS_THRESHOLD = 90
    REMOD_DELAY_SECONDS = 12
    KAMIKAZE_COOLDOWN_SECONDS = 60 * 10

    def __init__(self, bot):
        self.bot = bot
        self._remod_tasks: set[asyncio.Task] = set()
        self._kamikaze_cooldowns: dict[tuple[str, str], float] = {}

    @staticmethod
    def is_broadcaster(user_id: str, broadcaster_id: str) -> bool:
        return str(user_id) == str(broadcaster_id)

    def is_bot(self, user_id: str) -> bool:
        bot_id = getattr(self.bot, "bot_id", None)

        if bot_id is None:
            bot_user = getattr(self.bot, "user", None)
            bot_id = getattr(bot_user, "id", None)

        if bot_id is None:
            return False

        return str(user_id) == str(bot_id)

    def is_protected_target(self, user_id: str, broadcaster_id: str) -> bool:
        return self.is_broadcaster(user_id, broadcaster_id) or self.is_bot(user_id)

    def get_kamikaze_cooldown_remaining(self, broadcaster_id: str, user_id: str) -> int:
        key = (str(broadcaster_id), str(user_id))
        cooldown_ends_at = self._kamikaze_cooldowns.get(key)

        if cooldown_ends_at is None:
            return 0

        remaining = cooldown_ends_at - time.monotonic()

        if remaining <= 0:
            self._kamikaze_cooldowns.pop(key, None)
            return 0

        return max(1, int(remaining) + 1)

    def start_kamikaze_cooldown(self, broadcaster_id: str, user_id: str) -> None:
        key = (str(broadcaster_id), str(user_id))
        self._kamikaze_cooldowns[key] = time.monotonic() + self.KAMIKAZE_COOLDOWN_SECONDS

    @staticmethod
    def format_cooldown(seconds: int) -> str:
        minutes, remaining_seconds = divmod(seconds, 60)

        if minutes and remaining_seconds:
            return f"{minutes}m {remaining_seconds}s"

        if minutes:
            return f"{minutes}m"

        return f"{remaining_seconds}s"

    async def is_moderator(self, channel, target_id: str, target_name: str, broadcaster_id: str) -> bool:
        try:
            moderators = channel.fetch_moderators(user_ids=[target_id], max_results=1)

            async for moderator in moderators:
                if str(moderator.id) == target_id:
                    LOGGER.debug(
                        "[Mod Actions] Confirmed %s is a moderator in broadcaster %s.",
                        target_name,
                        broadcaster_id
                    )
                    return True
        except Exception:
            LOGGER.exception(
                "[Mod Actions] Failed to check moderator status for %s in broadcaster %s.",
                target_name,
                broadcaster_id
            )

        return False

    async def timeout_user(self, channel, broadcaster_id: str, user_id: str, username: str) -> bool:
        try:
            await channel.timeout_user(
                moderator=broadcaster_id,
                user=user_id,
                duration=self.KAMIKAZE_DURATION_SECONDS,
                reason="Blown up."
            )
        except Exception:
            LOGGER.exception(
                "[Mod Actions] Failed to time out user %s in broadcaster %s.",
                username,
                broadcaster_id
            )
            return False

        return True

    async def restore_moderator(self, channel, broadcaster_id: str, target_id: str, target_name: str) -> None:
        try:
            await asyncio.sleep(self.REMOD_DELAY_SECONDS)
            await channel.add_moderator(user=target_id)
        except asyncio.CancelledError:
            LOGGER.debug(
                "[Mod Actions] Moderator restoration was cancelled for %s in broadcaster %s.",
                target_name,
                broadcaster_id
            )
            raise
        except Exception:
            LOGGER.exception(
                "[Mod Actions] Failed to restore moderator status for %s in broadcaster %s.",
                target_name,
                broadcaster_id
            )
            return

        LOGGER.info(
            "[Mod Actions] Restored moderator status for %s in broadcaster %s.",
            target_name,
            broadcaster_id
        )

    def schedule_moderator_restoration(self, channel, broadcaster_id: str, target_id: str, target_name: str) -> None:
        task = asyncio.create_task(
            self.restore_moderator(channel, broadcaster_id, target_id, target_name),
            name=f"restore-moderator-{broadcaster_id}-{target_id}"
        )

        self._remod_tasks.add(task)
        task.add_done_callback(self._remod_tasks.discard)

        LOGGER.info(
            "[Mod Actions] Scheduled moderator restoration for %s in broadcaster %s.",
            target_name,
            broadcaster_id
        )

    async def timeout_with_moderator_restore(self, channel, broadcaster_id: str, user_id: str, username: str) -> bool:
        was_moderator = await self.is_moderator(channel, user_id, username, broadcaster_id)
        timed_out = await self.timeout_user(channel, broadcaster_id, user_id, username)

        if not timed_out:
            return False

        if was_moderator:
            self.schedule_moderator_restoration(channel, broadcaster_id, user_id, username)

        return True

    @commands.command(name="kamikaze")
    async def kamikaze(self, ctx: commands.Context, target: User = None) -> None:
        services = self.bot.services

        if services is None:
            LOGGER.warning(
                "[Commands] !kamikaze could not run because services are unavailable."
            )
            return

        broadcaster_id = get_context_broadcaster_id(ctx)

        if broadcaster_id is None:
            LOGGER.warning(
                "[Commands] !kamikaze could not resolve its broadcaster."
            )
            return

        if not is_feature_enabled(self.bot, ctx, FeatureName.KAMIKAZE):
            LOGGER.debug(
                "[Mod Actions] Kamikaze is disabled for broadcaster %s.",
                broadcaster_id
            )
            return

        caller = ctx.chatter
        caller_id = str(caller.id)
        target_name = target.name if target else caller.name
        channel = self.bot.create_partialuser(broadcaster_id)

        LOGGER.debug(
            "[Commands] User %s invoked !kamikaze against %s in broadcaster %s.",
            caller.name,
            target_name,
            broadcaster_id
        )

        cooldown_remaining = self.get_kamikaze_cooldown_remaining(broadcaster_id, caller_id)

        if cooldown_remaining > 0:
            cooldown_text = self.format_cooldown(cooldown_remaining)

            LOGGER.debug(
                "[Commands] User %s attempted !kamikaze during cooldown in broadcaster %s with %s remaining.",
                caller.name,
                broadcaster_id,
                cooldown_text
            )

            await ctx.reply(f"!kamikaze is on cooldown for you. Try again in {cooldown_text}.")
            return

        if target is None or caller_id == str(target.id):
            if self.is_protected_target(caller_id, broadcaster_id):
                LOGGER.info(
                    "[Mod Actions] Protected user %s attempted to target themselves with !kamikaze in broadcaster %s.",
                    caller.name,
                    broadcaster_id
                )

                await ctx.reply("You cannot bomb this target, try someone else.")
                return

            self.start_kamikaze_cooldown(broadcaster_id, caller_id)

            await ctx.reply("You bomb yourself...")

            timed_out = await self.timeout_with_moderator_restore(channel, broadcaster_id, caller_id, caller.name)

            if not timed_out:
                return

            LOGGER.info(
                "[Mod Actions] User %s timed themselves out for %d seconds in broadcaster %s.",
                caller.name,
                self.KAMIKAZE_DURATION_SECONDS,
                broadcaster_id
            )
            return

        target_id = str(target.id)

        if self.is_protected_target(target_id, broadcaster_id):
            LOGGER.info(
                "[Mod Actions] User %s attempted to target protected user %s with !kamikaze in broadcaster %s.",
                caller.name,
                target.name,
                broadcaster_id
            )

            await ctx.reply("You cannot bomb this target, try someone else.")
            return

        self.start_kamikaze_cooldown(broadcaster_id, caller_id)

        bomb_roll = random.randint(1, 100)

        LOGGER.debug(
            "[Commands] !kamikaze rolled %d for user %s against %s.",
            bomb_roll,
            caller.name,
            target.name
        )

        if bomb_roll > self.KAMIKAZE_SUCCESS_THRESHOLD:
            timed_out = await self.timeout_with_moderator_restore(channel, broadcaster_id, target_id, target.name)

            if not timed_out:
                return

            LOGGER.info(
                "[Mod Actions] User %s successfully timed out %s for %d seconds in broadcaster %s.",
                caller.name,
                target.name,
                self.KAMIKAZE_DURATION_SECONDS,
                broadcaster_id
            )

            await ctx.send(
                f"{target.name} has been blown up and timed out for "
                f"{self.KAMIKAZE_DURATION_SECONDS} seconds."
            )
            return

        if self.is_protected_target(caller_id, broadcaster_id):
            LOGGER.info(
                "[Mod Actions] Protected user %s missed !kamikaze but was not timed out in broadcaster %s.",
                caller.name,
                broadcaster_id
            )

            await ctx.send(f"{caller.name} missed, but they are protected from the explosion.")
            return

        timed_out = await self.timeout_with_moderator_restore(channel, broadcaster_id, caller_id, caller.name)

        if not timed_out:
            return

        LOGGER.info(
            "[Mod Actions] User %s missed !kamikaze and was timed out for %d seconds in broadcaster %s.",
            caller.name,
            self.KAMIKAZE_DURATION_SECONDS,
            broadcaster_id
        )

        await ctx.send(
            f"{caller.name} missed and blew themselves up~ they have been "
            f"timed out for {self.KAMIKAZE_DURATION_SECONDS} seconds."
        )
