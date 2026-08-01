import logging
import random

from twitchio import User
from twitchio.ext import commands

LOGGER = logging.getLogger("RatBoomBot")


class ModerationCommands(commands.Component):

    KAMIKAZE_DURATION_SECONDS = 10
    KAMIKAZE_SUCCESS_THRESHOLD = 75

    def __init__(self, bot):
        self.bot = bot

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
            await ctx.reply("You bomb yourself...")

            try:
                await channel.timeout_user(
                    moderator=broadcaster_id,
                    user=caller_id,
                    duration=self.KAMIKAZE_DURATION_SECONDS,
                    reason="Blown up."
                )
            except Exception:
                LOGGER.exception(
                    "[Moderation] Failed to time out user %s after self-targeted !kamikaze in broadcaster %s.",
                    caller.name,
                    broadcaster_id
                )
                raise

            LOGGER.info(
                "[Moderation] User %s timed themselves out for %d seconds in broadcaster %s.",
                caller.name,
                self.KAMIKAZE_DURATION_SECONDS,
                broadcaster_id
            )
            return

        is_moderator = getattr(target, "moderator", False)
        target_id = str(target.id)

        if target_id == broadcaster_id or is_moderator:
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
            try:
                await channel.timeout_user(
                    moderator=broadcaster_id,
                    user=target_id,
                    duration=self.KAMIKAZE_DURATION_SECONDS,
                    reason="Blown up."
                )
            except Exception:
                LOGGER.exception(
                    "[Moderation] Failed to time out target %s after !kamikaze in broadcaster %s.",
                    target.name,
                    broadcaster_id
                )
                raise

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

        try:
            await channel.timeout_user(
                moderator=broadcaster_id,
                user=caller_id,
                duration=self.KAMIKAZE_DURATION_SECONDS,
                reason="Blown up."
            )
        except Exception:
            LOGGER.exception(
                "[Moderation] Failed to time out user %s after missed !kamikaze in broadcaster %s.",
                caller.name,
                broadcaster_id
            )
            raise

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
