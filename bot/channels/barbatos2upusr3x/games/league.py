from twitchio.ext import commands

from bot.channels.component import ChannelComponent
from bot.profiles import ChannelProfile


class Barbatos2upusr3xLeagueCommands(ChannelComponent):

    def __init__(self, bot, profile: ChannelProfile, broadcaster_id: str):
        super().__init__(bot, profile, broadcaster_id)

    @commands.command(name="champs")
    async def champions(self, ctx: commands.Context, *, champion: str | None = None) -> None:
        if not await self.require_profile_channel(ctx) or not self.profile.league.enabled:
            return

        if champion:
            await self.send_core_build(ctx, champion)
            return

        top_champions = await self.bot.services.league.get_top_champions(self.broadcaster_id)

        if not top_champions:
            await ctx.send(f"{self.profile.league.display_name}'s seasonal champion data is still warming up. Try again soon.")
            return

        entries = [f"{entry.name} ({entry.win_rate:.1f}% WR)" for entry in top_champions]
        await ctx.send(f"{self.profile.league.display_name}'s most-played ranked champions this season: {', '.join(entries)}")

    async def send_core_build(self, ctx: commands.Context, champion: str) -> None:
        build = await self.bot.services.league.get_core_build(self.broadcaster_id, champion, self.profile.league)

        if build is None:
            await ctx.send(f"There aren't enough recent ranked {champion.strip()} games to determine {self.profile.league.display_name}'s common core build yet.")
            return

        items = ", ".join(build.item_names[:-1]) + f", and {build.item_names[-1]}"
        await ctx.send(f"{self.profile.league.display_name} commonly builds these 3 core items on {build.champion_name}: {items}.")
