import logging

import httpx
from twitchio.ext import commands

from bot.channels.component import ChannelComponent
from bot.profiles import ChannelProfile
from bot.services.engagement.overwatch import OverwatchNotConfiguredError

LOGGER = logging.getLogger("RatBoomBot")


class MilkyGalaxyOverwatchCommands(ChannelComponent):

    def __init__(self, bot, profile: ChannelProfile, broadcaster_id: str):
        super().__init__(bot, profile, broadcaster_id)

    async def require_overwatch(self, ctx: commands.Context) -> bool:
        if not await self.require_profile_channel(ctx):
            return False

        if await self.bot.services.overwatch.is_allowed_game(self.broadcaster_id, self.profile.overwatch):
            return True

        await ctx.send("Overwatch commands are only available while Milky is live and playing Overwatch 2.")
        return False

    @staticmethod
    def is_mod_or_broadcaster(ctx: commands.Context, broadcaster_id: str) -> bool:
        chatter = getattr(ctx, "chatter", None) or getattr(ctx, "author", None)
        if chatter is None:
            return False

        return bool(getattr(chatter, "moderator", False)) or str(chatter.id) == str(broadcaster_id)

    @commands.command(name="ow")
    async def overwatch_summary(self, ctx: commands.Context) -> None:
        # if not await self.require_overwatch(ctx):
        #     return

        session = await self.bot.services.overwatch.get_session(self.broadcaster_id)

        try:
            ranks = await self.bot.services.overwatch.fetch_ranks(self.profile.overwatch)
        except OverwatchNotConfiguredError:
            await ctx.send(f"Milky's Overwatch session: {session.wins}W-{session.losses}L. Rank lookup is not configured yet.")
            return
        except (httpx.HTTPError, ValueError):
            LOGGER.exception("[Overwatch] Failed to fetch Milky's ranks.")
            await ctx.send(f"Milky's Overwatch session: {session.wins}W-{session.losses}L. Rank data is unavailable right now.")
            return

        await ctx.send(f"Milky's Overwatch session: {session.wins}W-{session.losses}L | {self.format_ranks(ranks)}")

    @commands.command(name="owrank")
    async def overwatch_rank(self, ctx: commands.Context) -> None:
        # if not await self.require_overwatch(ctx):
        #     return

        try:
            ranks = await self.bot.services.overwatch.fetch_ranks(self.profile.overwatch)
        except OverwatchNotConfiguredError:
            await ctx.send("Milky's Overwatch BattleTag has not been configured yet.")
            return
        except (httpx.HTTPError, ValueError):
            LOGGER.exception("[Overwatch] Failed to fetch Milky's ranks.")
            await ctx.send("Milky's Overwatch rank data is unavailable right now.")
            return

        await ctx.send(f"Milky's Overwatch ranks | {self.format_ranks(ranks)}")

    @commands.command(name="owrecord")
    async def overwatch_record(self, ctx: commands.Context, result: str | None = None) -> None:
        # if not await self.require_overwatch(ctx):
        #     return

        if not self.is_mod_or_broadcaster(ctx, self.broadcaster_id):
            await ctx.send("Only Milky or a moderator can record Overwatch match results.")
            return

        result = (result or "").lower()
        if result not in {"win", "loss"}:
            await ctx.send("Use !owrecord win or !owrecord loss.")
            return

        session = await self.bot.services.overwatch.record_result(self.broadcaster_id, result)
        await ctx.send(f"Recorded a {result}. Milky's session is now {session.wins}W-{session.losses}L.")

    @commands.command(name="owreset")
    async def overwatch_reset(self, ctx: commands.Context) -> None:
        # if not await self.require_overwatch(ctx):
        #     return

        if not self.is_mod_or_broadcaster(ctx, self.broadcaster_id):
            await ctx.send("Only Milky or a moderator can reset the Overwatch session.")
            return

        await self.bot.services.overwatch.reset_session(self.broadcaster_id)
        await ctx.send("Milky's Overwatch session has been reset to 0W-0L.")

    @staticmethod
    def format_ranks(ranks: dict[str, str | None]) -> str:
        labels = (("tank", "Tank"), ("damage", "Damage"), ("support", "Support"), ("open", "Open"))
        entries = [f"{label}: {ranks[role]}" for role, label in labels if ranks.get(role)]
        return " | ".join(entries) if entries else "No public competitive ranks found"
