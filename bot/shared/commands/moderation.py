import asyncio
import logging
import random

from twitchio import User
from twitchio.ext import commands

LOGGER = logging.getLogger("RatBoomBot")


class ModerationCommands(commands.Component):

    KAMIKAZE_DURATION_SECONDS = 10
    KAMIKAZE_SUCCESS_THRESHOLD = 0
    REMOD_DELAY_SECONDS = 12

    def __init__(self, bot):
        self.bot = bot
        self._remod_tasks: set[asyncio.Task] = set()

    def is_broadcaster(self, user_id: str, broadcaster_id: str) -> bool:
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
        return (
            self.is_broadcaster(user_id, broadcaster_id)
            or self.is_bot(user_id)
        )

    async def is_moderator(self, channel, target_id: str, target_name: str, broadcaster_id: str) -> bool:
        try:
            moderators = channel.fetch_moderators(
                user_ids=[target_id],
                max_results=1
            )

            async for moderator in moderators:
                if str(moderator.id) == target_id:
                    LOGGER.debug(
                        "[Moderation] Confirmed %s is a moderator in broadcaster %s.",
                        target_name,
                        broadcaster_id
                    )
                    return True
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to check moderator status for %s in broadcaster %s.",
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
                "[Moderation] Failed to time out user %s in broadcaster %s.",
                username,
                broadcaster_id
            )
            return False

        return True

    async def restore_moderator(self, channel, broadcaster_id: str, target_id: str, target_name: str) -> None:
        try:
            await asyncio.sleep(self.REMOD_DELAY_SECONDS)

            await channel.add_moderator(
                user=target_id
            )
        except asyncio.CancelledError:
            LOGGER.debug(
                "[Moderation] Moderator restoration was cancelled for %s in broadcaster %s.",
                target_name,
                broadcaster_id
            )
            raise
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to restore moderator status for %s in broadcaster %s.",
                target_name,
                broadcaster_id
            )
            return

        LOGGER.info(
            "[Moderation] Restored moderator status for %s in broadcaster %s.",
            target_name,
            broadcaster_id
        )

    def schedule_moderator_restoration(self, channel, broadcaster_id: str, target_id: str, target_name: str) -> None:
        task = asyncio.create_task(
            self.restore_moderator(
                channel,
                broadcaster_id,
                target_id,
                target_name
            ),
            name=f"restore-moderator-{broadcaster_id}-{target_id}"
        )

        self._remod_tasks.add(task)
        task.add_done_callback(self._remod_tasks.discard)

        LOGGER.info(
            "[Moderation] Scheduled moderator restoration for %s in broadcaster %s.",
            target_name,
            broadcaster_id
        )

    async def timeout_with_moderator_restore(self, channel, broadcaster_id: str, user_id: str, username: str) -> bool:
        was_moderator = await self.is_moderator(
            channel,
            user_id,
            username,
            broadcaster_id
        )

        timed_out = await self.timeout_user(
            channel,
            broadcaster_id,
            user_id,
            username
        )

        if not timed_out:
            return False

        if was_moderator:
            self.schedule_moderator_restoration(
                channel,
                broadcaster_id,
                user_id,
                username
            )

        return True

    @commands.command(name="kamikaze")
    async def kamikaze(self, ctx: commands.Context, target: User = None):
        if not self.bot.services:
            LOGGER.warning(
                "[Commands] !kamikaze could not run because services are unavailable."
            )
            return

        caller = ctx.chatter
        broadcaster = ctx.broadcaster
        broadcaster_id = str(broadcaster.id)
        caller_id = str(caller.id)
        channel = self.bot.create_partialuser(broadcaster_id)

        LOGGER.debug(
            "[Commands] User %s invoked !kamikaze against %s in broadcaster %s.",
            caller.name,
            target.name if target else caller.name,
            broadcaster_id
        )

        if target is None or caller_id == str(target.id):
            if self.is_protected_target(caller_id, broadcaster_id):
                LOGGER.info(
                    "[Moderation] Protected user %s attempted to target themselves with !kamikaze in broadcaster %s.",
                    caller.name,
                    broadcaster_id
                )

                await ctx.reply(
                    "You cannot bomb this target, try someone else."
                )
                return

            await ctx.reply("You bomb yourself...")

            timed_out = await self.timeout_with_moderator_restore(
                channel,
                broadcaster_id,
                caller_id,
                caller.name
            )

            if not timed_out:
                return

            LOGGER.info(
                "[Moderation] User %s timed themselves out for %d seconds in broadcaster %s.",
                caller.name,
                self.KAMIKAZE_DURATION_SECONDS,
                broadcaster_id
            )
            return

        target_id = str(target.id)

        if self.is_protected_target(target_id, broadcaster_id):
            LOGGER.info(
                "[Moderation] User %s attempted to target protected user %s with !kamikaze in broadcaster %s.",
                caller.name,
                target.name,
                broadcaster_id
            )

            await ctx.reply(
                "You cannot bomb this target, try someone else."
            )
            return

        bomb_roll = random.randint(1, 100)

        LOGGER.debug(
            "[Commands] !kamikaze rolled %d for user %s against %s.",
            bomb_roll,
            caller.name,
            target.name
        )

        if bomb_roll > self.KAMIKAZE_SUCCESS_THRESHOLD:
            timed_out = await self.timeout_with_moderator_restore(
                channel,
                broadcaster_id,
                target_id,
                target.name
            )

            if not timed_out:
                return

            LOGGER.info(
                "[Moderation] User %s successfully timed out %s for %d seconds in broadcaster %s.",
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
                "[Moderation] Protected user %s missed !kamikaze but was not timed out in broadcaster %s.",
                caller.name,
                broadcaster_id
            )

            await ctx.send(
                f"{caller.name} missed, but they are protected from the explosion."
            )
            return

        timed_out = await self.timeout_with_moderator_restore(
            channel,
            broadcaster_id,
            caller_id,
            caller.name
        )

        if not timed_out:
            return

        LOGGER.info(
            "[Moderation] User %s missed !kamikaze and was timed out for %d seconds in broadcaster %s.",
            caller.name,
            self.KAMIKAZE_DURATION_SECONDS,
            broadcaster_id
        )

        await ctx.send(
            f"{caller.name} missed and blew themselves up~ they have been "
            f"timed out for {self.KAMIKAZE_DURATION_SECONDS} seconds."
        )
