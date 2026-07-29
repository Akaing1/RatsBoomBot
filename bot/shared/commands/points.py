import random

from twitchio import User
from twitchio.ext import commands

from bot.profiles import PointsConfig, get_active_profile, render_profile_message


class PointsCommandHandler:
    def __init__(self, bot):
        self.bot = bot

    def get_config(self, broadcaster_id: str) -> PointsConfig | None:
        profile = get_active_profile(str(broadcaster_id))

        if profile is None:
            return None

        if not profile.points.enabled:
            return None

        return profile.points

    async def send_message(self, ctx: commands.Context, template: str | None, **values) -> None:
        message = render_profile_message(template, **values)

        if message:
            await ctx.reply(message)

    async def show_balance(self, ctx: commands.Context, target: User | None, command_name: str) -> None:
        if not self.bot.services:
            return

        broadcaster_id = str(ctx.broadcaster.id)
        config = self.get_config(broadcaster_id)

        if config is None:
            return

        if target is None:
            points = await self.bot.services.points.get_points(
                broadcaster_id,
                str(ctx.chatter.id),
            )

            await self.send_message(
                ctx,
                config.messages.balance_self,
                username=ctx.chatter.name,
                points=points,
                command=command_name,
            )
            return

        points = await self.bot.services.points.get_points(
            broadcaster_id,
            str(target.id),
        )

        await self.send_message(
            ctx,
            config.messages.balance_other,
            username=target.name,
            points=points,
            command=command_name,
        )

    async def show_leaderboard(self, ctx: commands.Context, command_name: str) -> None:
        if not self.bot.services:
            return

        broadcaster_id = str(ctx.broadcaster.id)
        config = self.get_config(broadcaster_id)

        if config is None:
            return

        rows = await self.bot.services.points.get_leaderboard(
            broadcaster_id,
            limit=5,
        )

        if not rows:
            await self.send_message(
                ctx,
                config.messages.leaderboard_empty,
                command=command_name,
            )
            return

        entries: list[str] = []

        for index, row in enumerate(rows):
            entry = render_profile_message(
                config.messages.leaderboard_entry,
                position=index + 1,
                username=row["username"],
                points=row["points"],
                command=command_name,
            )

            if entry:
                entries.append(entry)

        leaderboard = " | ".join(entries)

        await self.send_message(
            ctx,
            config.messages.leaderboard_title,
            leaderboard=leaderboard,
            command=command_name,
        )

    async def reset_points(self, ctx: commands.Context, command_name: str) -> None:
        if not self.bot.services:
            return

        broadcaster_id = str(ctx.broadcaster.id)
        config = self.get_config(broadcaster_id)

        if config is None:
            return

        if str(ctx.chatter.id) != broadcaster_id:
            await self.send_message(
                ctx,
                config.messages.reset_denied,
                command=command_name,
            )
            return

        await self.bot.services.points.reset_all_points(broadcaster_id)

        await self.send_message(
            ctx,
            config.messages.reset_success,
            command=command_name,
        )

    async def add_points(self, ctx: commands.Context, target: User, amount: int, command_name: str) -> None:
        if not self.bot.services:
            return

        broadcaster_id = str(ctx.broadcaster.id)
        config = self.get_config(broadcaster_id)

        if config is None:
            return

        is_broadcaster = str(ctx.chatter.id) == broadcaster_id
        is_moderator = getattr(ctx.chatter, "moderator", False)

        if not (is_broadcaster or is_moderator):
            await self.send_message(
                ctx,
                config.messages.add_denied,
                command=command_name,
            )
            return

        if amount <= 0:
            await self.send_message(
                ctx,
                config.messages.add_invalid,
                command=command_name,
            )
            return

        await self.bot.services.points.add_points(
            broadcaster_id=broadcaster_id,
            user_id=str(target.id),
            username=target.name,
            amount=amount,
        )

        await self.send_message(
            ctx,
            config.messages.add_success,
            username=target.name,
            amount=amount,
            command=command_name,
        )

    async def gamble(self, ctx: commands.Context, amount: str, command_name: str) -> None:
        if not self.bot.services:
            return

        broadcaster_id = str(ctx.broadcaster.id)
        user_id = str(ctx.chatter.id)
        username = ctx.chatter.name
        config = self.get_config(broadcaster_id)

        if config is None:
            return

        current_points = await self.bot.services.points.get_points(
            broadcaster_id,
            user_id,
        )

        if current_points <= 0:
            await self.send_message(
                ctx,
                config.messages.gamble_no_points,
                username=username,
                points=current_points,
                command=command_name,
            )
            return

        all_in = amount.lower() == "all"

        if all_in:
            gamble_amount = current_points
        else:
            try:
                gamble_amount = int(amount)
            except ValueError:
                await self.send_message(
                    ctx,
                    config.messages.gamble_usage,
                    username=username,
                    points=current_points,
                    command=command_name,
                )
                return

        if gamble_amount <= 0:
            await self.send_message(
                ctx,
                config.messages.gamble_invalid,
                username=username,
                points=current_points,
                command=command_name,
            )
            return

        if gamble_amount > current_points:
            await self.send_message(
                ctx,
                config.messages.gamble_insufficient,
                username=username,
                points=current_points,
                amount=gamble_amount,
                command=command_name,
            )
            return

        won = random.random() < config.gamble_win_chance

        if won:
            await self.bot.services.points.add_points(
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=username,
                amount=gamble_amount,
            )

            new_balance = current_points + gamble_amount
            template = config.messages.gamble_all_win if all_in else config.messages.gamble_win

            await self.send_message(
                ctx,
                template,
                username=username,
                points=current_points,
                amount=gamble_amount,
                new_balance=new_balance,
                command=command_name,
            )
            return

        await self.bot.services.points.remove_points(
            broadcaster_id=broadcaster_id,
            user_id=user_id,
            amount=gamble_amount,
        )

        new_balance = current_points - gamble_amount
        template = config.messages.gamble_all_loss if all_in else config.messages.gamble_loss

        await self.send_message(
            ctx,
            template,
            username=username,
            points=current_points,
            amount=gamble_amount,
            new_balance=new_balance,
            command=command_name,
        )

    async def create_duel(self, ctx: commands.Context, opponent: User | None, amount: str | None, command_name: str) -> None:
        if not self.bot.services:
            return

        broadcaster_id = str(ctx.broadcaster.id)
        config = self.get_config(broadcaster_id)

        if config is None:
            return

        if opponent is None or amount is None:
            await self.send_message(
                ctx,
                config.messages.duel_usage,
                command=command_name,
            )
            return

        challenger_id = str(ctx.chatter.id)
        challenger_name = ctx.chatter.name
        opponent_id = str(opponent.id)
        opponent_name = opponent.name
        all_in = amount.lower() == "all"

        if all_in:
            duel_amount = await self.bot.services.points.get_points(
                broadcaster_id,
                challenger_id,
            )
        else:
            try:
                duel_amount = int(amount)
            except ValueError:
                await self.send_message(
                    ctx,
                    config.messages.duel_amount_invalid,
                    challenger=challenger_name,
                    opponent=opponent_name,
                    command=command_name,
                )
                return

        if challenger_id == opponent_id:
            await self.send_message(
                ctx,
                config.messages.duel_self,
                challenger=challenger_name,
                opponent=opponent_name,
                command=command_name,
            )
            return

        if duel_amount <= 0:
            await self.send_message(
                ctx,
                config.messages.duel_invalid,
                challenger=challenger_name,
                opponent=opponent_name,
                amount=duel_amount,
                command=command_name,
            )
            return

        challenger_points = await self.bot.services.points.get_points(
            broadcaster_id,
            challenger_id,
        )

        opponent_points = await self.bot.services.points.get_points(
            broadcaster_id,
            opponent_id,
        )

        if challenger_points < duel_amount:
            await self.send_message(
                ctx,
                config.messages.duel_challenger_insufficient,
                username=challenger_name,
                points=challenger_points,
                amount=duel_amount,
                command=command_name,
            )
            return

        if opponent_points < duel_amount:
            await self.send_message(
                ctx,
                config.messages.duel_opponent_insufficient,
                username=opponent_name,
                points=opponent_points,
                amount=duel_amount,
                command=command_name,
            )
            return

        self.bot.services.points.create_duel(
            broadcaster_id=broadcaster_id,
            challenger_id=challenger_id,
            challenger_name=challenger_name,
            opponent_id=opponent_id,
            opponent_name=opponent_name,
            amount=duel_amount,
            expiration_seconds=config.duel_expiration_seconds,
        )

        await self.send_message(
            ctx,
            config.messages.duel_challenge,
            challenger=challenger_name,
            opponent=opponent_name,
            amount=duel_amount,
            expiration=config.duel_expiration_seconds,
            command=command_name,
        )

    async def accept_duel(self, ctx: commands.Context, command_name: str) -> None:
        if not self.bot.services:
            return

        broadcaster_id = str(ctx.broadcaster.id)
        opponent_id = str(ctx.chatter.id)
        config = self.get_config(broadcaster_id)

        if config is None:
            return

        duel = self.bot.services.points.get_duel_for_user(
            broadcaster_id,
            opponent_id,
        )

        if not duel:
            await self.send_message(
                ctx,
                config.messages.duel_missing,
                command=command_name,
            )
            return

        challenger_points = await self.bot.services.points.get_points(
            broadcaster_id,
            duel.challenger_id,
        )

        opponent_points = await self.bot.services.points.get_points(
            broadcaster_id,
            duel.opponent_id,
        )

        if challenger_points < duel.amount or opponent_points < duel.amount:
            self.bot.services.points.remove_duel_for_user(
                broadcaster_id,
                opponent_id,
            )

            await self.send_message(
                ctx,
                config.messages.duel_cancelled,
                challenger=duel.challenger_name,
                opponent=duel.opponent_name,
                amount=duel.amount,
                command=command_name,
            )
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

        await self.bot.services.points.remove_points(
            broadcaster_id=broadcaster_id,
            user_id=loser_id,
            amount=duel.amount,
        )

        await self.bot.services.points.add_points(
            broadcaster_id=broadcaster_id,
            user_id=winner_id,
            username=winner_name,
            amount=duel.amount,
        )

        self.bot.services.points.remove_duel_for_user(
            broadcaster_id,
            opponent_id,
        )

        await self.send_message(
            ctx,
            config.messages.duel_result,
            winner=winner_name,
            loser=loser_name,
            amount=duel.amount,
            command=command_name,
        )

    async def decline_duel(self, ctx: commands.Context, command_name: str) -> None:
        if not self.bot.services:
            return

        broadcaster_id = str(ctx.broadcaster.id)
        opponent_id = str(ctx.chatter.id)
        config = self.get_config(broadcaster_id)

        if config is None:
            return

        duel = self.bot.services.points.get_duel_for_user(
            broadcaster_id,
            opponent_id,
        )

        if not duel:
            await self.send_message(
                ctx,
                config.messages.duel_missing,
                command=command_name,
            )
            return

        self.bot.services.points.remove_duel_for_user(
            broadcaster_id,
            opponent_id,
        )

        await self.send_message(
            ctx,
            config.messages.duel_declined,
            username=ctx.chatter.name,
            challenger=duel.challenger_name,
            opponent=duel.opponent_name,
            amount=duel.amount,
            command=command_name,
        )


class PointsCommands(commands.Component):
    def __init__(self, bot):
        self.bot = bot
        self.handler = PointsCommandHandler(bot)

    @commands.group(name="points", invoke_fallback=True)
    async def points(self, ctx: commands.Context, target: User = None):
        await self.handler.show_balance(ctx, target, "points")

    @points.command(name="leaderboard")
    async def points_leaderboard(self, ctx: commands.Context):
        await self.handler.show_leaderboard(ctx, "points")

    @points.command(name="reset")
    async def points_reset(self, ctx: commands.Context):
        await self.handler.reset_points(ctx, "points")

    @points.command(name="add")
    async def points_add(self, ctx: commands.Context, target: User, amount: int):
        await self.handler.add_points(ctx, target, amount, "points")

    @points.command(name="gamble")
    async def points_gamble(self, ctx: commands.Context, amount: str):
        await self.handler.gamble(ctx, amount, "points")

    @points.group(name="duel", invoke_fallback=True)
    async def points_duel(self, ctx: commands.Context, opponent: User = None, amount: str = None):
        await self.handler.create_duel(ctx, opponent, amount, "points")

    @points_duel.command(name="accept")
    async def points_duel_accept(self, ctx: commands.Context):
        await self.handler.accept_duel(ctx, "points")

    @points_duel.command(name="decline")
    async def points_duel_decline(self, ctx: commands.Context):
        await self.handler.decline_duel(ctx, "points")
