import logging

import httpx
from twitchio.ext import commands

from bot.profiles import OverwatchConfig, ProfileFeatureName, get_active_profile
from bot.services.engagement.overwatch import OverwatchNotConfiguredError
from bot.shared.commands.helpers import get_context_broadcaster_id, is_profile_feature_enabled

LOGGER = logging.getLogger("RatBoomBot")


class OverwatchCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    def get_context(self, ctx: commands.Context) -> tuple[str, OverwatchConfig] | None:
        broadcaster_id = get_context_broadcaster_id(ctx)

        if broadcaster_id is None or not is_profile_feature_enabled(self.bot, ctx, ProfileFeatureName.OVERWATCH):
            return None

        profile = get_active_profile(broadcaster_id)
        return (broadcaster_id, profile.overwatch) if profile is not None else None

    async def require_overwatch(self, ctx: commands.Context) -> tuple[str, OverwatchConfig] | None:
        context = self.get_context(ctx)

        if context is None:
            return None

        broadcaster_id, config = context

        if await self.bot.services.overwatch.is_allowed_game(broadcaster_id, config):
            return context

        await ctx.send("Overwatch commands are only available while the streamer is live and playing Overwatch 2.")
        return None

    @staticmethod
    def is_mod_or_broadcaster(ctx: commands.Context, broadcaster_id: str) -> bool:
        chatter = getattr(ctx, "chatter", None) or getattr(ctx, "author", None)
        return chatter is not None and (bool(getattr(chatter, "moderator", False)) or str(chatter.id) == str(broadcaster_id))

    @commands.command(name="ow")
    async def overwatch_summary(self, ctx: commands.Context) -> None:
        context = await self.require_overwatch(ctx)

        if context is None:
            return

        broadcaster_id, config = context
        session = await self.bot.services.overwatch.get_session(broadcaster_id)

        try:
            ranks = await self.bot.services.overwatch.fetch_ranks(config)
        except OverwatchNotConfiguredError:
            await ctx.send(f"{config.display_name}'s Overwatch session: {session.wins}W-{session.losses}L. Rank lookup is not configured yet.")
            return
        except (httpx.HTTPError, ValueError):
            LOGGER.exception("[Overwatch] Failed to fetch ranks for broadcaster %s.", broadcaster_id)
            await ctx.send(f"{config.display_name}'s Overwatch session: {session.wins}W-{session.losses}L. Rank data is unavailable right now.")
            return

        await ctx.send(f"{config.display_name}'s Overwatch session: {session.wins}W-{session.losses}L | {self.format_ranks(ranks)}")

    @commands.command(name="owrank")
    async def overwatch_rank(self, ctx: commands.Context) -> None:
        context = await self.require_overwatch(ctx)

        if context is None:
            return

        broadcaster_id, config = context

        try:
            ranks = await self.bot.services.overwatch.fetch_ranks(config)
        except OverwatchNotConfiguredError:
            await ctx.send(f"{config.display_name}'s Overwatch BattleTag has not been configured yet.")
            return
        except (httpx.HTTPError, ValueError):
            LOGGER.exception("[Overwatch] Failed to fetch ranks for broadcaster %s.", broadcaster_id)
            await ctx.send(f"{config.display_name}'s Overwatch rank data is unavailable right now.")
            return

        await ctx.send(f"{config.display_name}'s Overwatch ranks | {self.format_ranks(ranks)}")

    @commands.command(name="owrecord")
    async def overwatch_record(self, ctx: commands.Context, result: str | None = None) -> None:
        context = await self.require_overwatch(ctx)

        if context is None:
            return

        broadcaster_id, config = context

        if not self.is_mod_or_broadcaster(ctx, broadcaster_id):
            await ctx.send("Only the broadcaster or a moderator can record Overwatch match results.")
            return

        result = (result or "").lower()

        if result not in {"win", "loss"}:
            await ctx.send("Use !owrecord win or !owrecord loss.")
            return

        session = await self.bot.services.overwatch.record_result(broadcaster_id, result)
        await ctx.send(f"Recorded a {result}. {config.display_name}'s session is now {session.wins}W-{session.losses}L.")

    @commands.command(name="owreset")
    async def overwatch_reset(self, ctx: commands.Context) -> None:
        context = await self.require_overwatch(ctx)

        if context is None:
            return

        broadcaster_id, config = context

        if not self.is_mod_or_broadcaster(ctx, broadcaster_id):
            await ctx.send("Only the broadcaster or a moderator can reset the Overwatch session.")
            return

        await self.bot.services.overwatch.reset_session(broadcaster_id)
        await ctx.send(f"{config.display_name}'s Overwatch session has been reset to 0W-0L.")

    @staticmethod
    def format_ranks(ranks: dict[str, str | None]) -> str:
        labels = (("tank", "Tank"), ("damage", "Damage"), ("support", "Support"), ("open", "Open"))
        entries = [f"{label}: {ranks[role]}" for role, label in labels if ranks.get(role)]
        return " | ".join(entries) if entries else "No public competitive ranks found"
