import random

from twitchio import User
from twitchio.ext import commands


class PointsCommands(commands.Component):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="bread", invoke_fallback=True)
    async def bread(self, ctx: commands.Context):
        if not self.bot.services:
            return

        points = await self.bot.services.points.get_points(ctx.chatter.id)

        await ctx.reply(
            f"{ctx.chatter.name}, you have {points} pieces of stale bread!"
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
    async def bread_add(self, ctx: commands.Context, target: User, amount: int):
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

    @bread.group(name="duel", invoke_fallback=True)
    async def bread_duel(self, ctx: commands.Context, opponent: User = None, amount: str = None):
        if not self.bot.services:
            return

        if opponent is None or amount is None:
            await ctx.reply("Use it like this: !bread duel @user 100")
            return

        all_in = amount.lower() == "all"
        if all_in:
            challenger_bread = await self.bot.services.points.get_points(ctx.chatter.id)
            amount = challenger_bread
        else:
            try:
                amount = int(amount)
            except ValueError:
                await ctx.reply("Duel amount must be a number or 'all'.")
                return

        challenger_id = ctx.chatter.id
        challenger_name = ctx.chatter.name
        opponent_id = opponent.id
        opponent_name = opponent.name

        if challenger_id == opponent_id:
            await ctx.reply("You can't duel yourself. The rats are confused.")
            return

        if amount <= 0:
            await ctx.reply("Duel amount must be greater than 0.")
            return

        challenger_bread = await self.bot.services.points.get_points(challenger_id)
        opponent_bread = await self.bot.services.points.get_points(opponent_id)

        if challenger_bread < amount:
            await ctx.reply(f"You only have {challenger_bread} stale bread.")
            return

        if opponent_bread < amount:
            await ctx.reply(f"{opponent_name} only has {opponent_bread} stale bread.")
            return

        self.bot.services.points.create_duel(
            challenger_id=challenger_id,
            challenger_name=challenger_name,
            opponent_id=opponent_id,
            opponent_name=opponent_name,
            amount=amount,
        )

        await ctx.send(
            f"@{opponent_name}, @{challenger_name} challenged you to a stale bread duel "
            f"for {amount} bread! Type !bread duel accept or !bread duel decline. "
            f"This duel expires in 60 seconds."
        )

    @bread_duel.command(name="accept")
    async def bread_duel_accept(self, ctx: commands.Context):
        if not self.bot.services:
            return

        opponent_id = ctx.chatter.id
        duel = self.bot.services.points.get_duel_for_user(opponent_id)

        if not duel:
            await ctx.reply("You don't have any pending bread duels, or your duel has expired.")
            return

        challenger_bread = await self.bot.services.points.get_points(duel.challenger_id)
        opponent_bread = await self.bot.services.points.get_points(duel.opponent_id)

        if challenger_bread < duel.amount or opponent_bread < duel.amount:
            self.bot.services.points.remove_duel_for_user(opponent_id)
            await ctx.reply("This duel was cancelled because someone no longer has enough stale bread.")
            return

        challenger_wins = random.choice([True, False])

        if challenger_wins:
            winner_id = duel.challenger_id
            winner_name = duel.challenger_name
            loser_id = duel.opponent_id
            loser_name = duel.opponent_name
        else:
            winner_id = duel.opponent_id
            winner_name = duel.opponent_name
            loser_id = duel.challenger_id
            loser_name = duel.challenger_name

        await self.bot.services.points.remove_points(loser_id, duel.amount)
        await self.bot.services.points.add_points(winner_id, winner_name, duel.amount)

        self.bot.services.points.remove_duel_for_user(opponent_id)

        await ctx.send(
            f"@{winner_name} beat @{loser_name} up "
            f"and stole {duel.amount} bread."
        )

    @bread_duel.command(name="decline")
    async def bread_duel_decline(self, ctx: commands.Context):
        if not self.bot.services:
            return

        opponent_id = ctx.chatter.id
        duel = self.bot.services.points.get_duel_for_user(opponent_id)

        if not duel:
            await ctx.reply("You don't have any pending bread duels, or your duel has expired.")
            return

        self.bot.services.points.remove_duel_for_user(opponent_id)

        await ctx.send(
            f"{ctx.chatter.name} has a family and decided to decline."
        )
