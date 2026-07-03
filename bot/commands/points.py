from twitchio import User
from twitchio.ext import commands

import random


class PointsCommands(commands.Component):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="bread", invoke_fallback=True)
    async def bread(self, ctx: commands.Context):
        if not self.bot.services:
            return

        points = await self.bot.services.points.get_points(ctx.chatter.id)

        await ctx.reply(
            f"{ctx.chatter.name}, you have stolen {points} pieces of stale bread!"
        )

    @bread.command(name="leaderboard")
    async def bread_leaderboard(self, ctx: commands.Context):
        if not self.bot.services:
            return

        rows = await self.bot.services.points.get_leaderboard(limit=5)

        if not rows:
            await ctx.reply("No stale bread has been collected yet. What an upstanding citizen!")
            return

        leaderboard = " | ".join(
            f"{index + 1}. {row['username']}: {row['points']} bread"
            for index, row in enumerate(rows)
        )

        await ctx.reply(f"Top stale bread hoarders: {leaderboard}")

    @bread.command(name="reset")
    async def bread_reset(self, ctx: commands.Context):
        if not self.bot.services:
            return

        if ctx.chatter.id != ctx.broadcaster.id:
            await ctx.reply("Only the broadcaster can reset the stale bread stash.")
            return

        await self.bot.services.points.reset_all_points()

        await ctx.send("All stale bread has been thrown away. The leaderboard has been reset.")

    @bread.command(name="add")
    async def bread_add(self, ctx: commands.Context, target: User,amount: int, ):
        if not self.bot.services:
            return

        is_broadcaster = ctx.chatter.id == ctx.broadcaster.id
        is_moderator = getattr(ctx.chatter, "moderator", False)

        if not (is_broadcaster or is_moderator):
            await ctx.reply("Only moderators can add stale bread to viewers.")
            return

        if amount <= 0:
            await ctx.reply("Bread amount must be greater than 0.")
            return

        await self.bot.services.points.add_points(
            user_id=target.id,
            username=target.name,
            amount=amount,
        )

        await ctx.send(
            f"Added {amount} pieces of stale bread to {target.name}'s stash."
        )

    @bread.command(name="gamble")
    async def bread_gamble(self, ctx: commands.Context, amount: str):
        if not self.bot.services:
            return

        user_id = ctx.chatter.id
        username = ctx.chatter.name

        current_bread = await self.bot.services.points.get_points(user_id)

        if current_bread <= 0:
            await ctx.reply("You don't have any stale bread to gamble.")
            return

        all_in = amount.lower() == "all"

        if all_in:
            gamble_amount = current_bread
        else:
            try:
                gamble_amount = int(amount)
            except ValueError:
                await ctx.reply("Use it like this: !bread gamble 50 or !bread gamble all")
                return

        if gamble_amount <= 0:
            await ctx.reply("You need to gamble at least 1 piece of stale bread.")
            return

        if gamble_amount > current_bread:
            await ctx.reply(f"You only have {current_bread} pieces of stale bread.")
            return

        won = random.random() < 0.45

        if won and all_in:
            await self.bot.services.points.add_points(user_id, username, gamble_amount)
            await ctx.reply(
                f"{username} raided the pantry and found a hidden stash of stale bread! "
                f"You now have {current_bread * 2} bread."
            )
        elif won:
            await self.bot.services.points.add_points(user_id, username, gamble_amount)
            await ctx.reply(
                f"{username} found {gamble_amount} stale bread on the ground "
                f"and now has {current_bread + gamble_amount} bread."
            )
        elif all_in:
            await self.bot.services.points.remove_points(user_id, gamble_amount)
            await ctx.reply(
                f"{username} got into a fight with the other rats and got mugged. "
                f"You lost all your stale bread."
            )
        else:
            await self.bot.services.points.remove_points(user_id, gamble_amount)
            await ctx.reply(
                f"{username} got caught by a rat trap and lost {gamble_amount} stale bread "
                f"and now has {current_bread - gamble_amount} bread."
            )


