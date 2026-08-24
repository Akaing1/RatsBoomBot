import logging

from twitchio import User
from twitchio.ext import commands

from bot.profiles import FeatureName, LeagueConfig, get_active_profile
from bot.services.engagement.league import CommunityRank, LeagueProviderError, RankEntry
from bot.shared.commands.converters import LocalizedUser
from bot.shared.commands.helpers import get_context_broadcaster_id, is_feature_enabled

LOGGER = logging.getLogger("RatBoomBot")


class LeagueCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot
        self.community = LeagueCommunityCommandHandler(bot)

    def get_context(self, ctx: commands.Context) -> tuple[str, LeagueConfig] | None:
        broadcaster_id = get_context_broadcaster_id(ctx)

        if broadcaster_id is None or not is_feature_enabled(self.bot, ctx, FeatureName.CHANNEL):
            return None

        profile = get_active_profile(broadcaster_id)

        if profile is None or not profile.league.enabled:
            return None

        return broadcaster_id, profile.league

    @commands.command(name="champs")
    async def champions(self, ctx: commands.Context, *, champion: str | None = None) -> None:
        context = self.get_context(ctx)

        if context is None:
            return

        broadcaster_id, config = context

        if champion:
            await self.send_core_build(ctx, broadcaster_id, config, champion)
            return

        top_champions = await self.bot.services.league.get_top_champions(broadcaster_id)

        if not top_champions:
            await ctx.send(f"{config.display_name}'s seasonal champion data is still warming up. Try again soon.")
            return

        entries = [f"{entry.name} ({entry.win_rate:.1f}% WR)" for entry in top_champions]
        await ctx.send(f"{config.display_name}'s most-played ranked champions this season: {', '.join(entries)}")

    async def send_core_build(self, ctx: commands.Context, broadcaster_id: str, config: LeagueConfig, champion: str) -> None:
        build = await self.bot.services.league.get_core_build(broadcaster_id, champion, config)

        if build is None:
            await ctx.send(f"There aren't enough recent ranked {champion.strip()} games to determine {config.display_name}'s common core build yet.")
            return

        items = ", ".join(build.item_names[:-1]) + f", and {build.item_names[-1]}"
        await ctx.send(f"{config.display_name}'s most common {build.champion_name} core includes: {items}.")

    @commands.command(name="register")
    async def register(self, ctx: commands.Context, *, riot_id: str | None = None) -> None:
        context = self.get_context(ctx)

        if context is None:
            return

        broadcaster_id, config = context
        await self.community.register(ctx, broadcaster_id, config, riot_id)

    @commands.command(name="unregister")
    async def unregister(self, ctx: commands.Context) -> None:
        context = self.get_context(ctx)

        if context is None:
            return

        await self.community.unregister(ctx, context[0])

    @commands.command(name="rank")
    async def rank(self, ctx: commands.Context, target: LocalizedUser = None) -> None:
        context = self.get_context(ctx)

        if context is None:
            return

        await self.community.rank(ctx, context[0], target)

    @commands.command(name="ladder")
    async def ladder(self, ctx: commands.Context) -> None:
        context = self.get_context(ctx)

        if context is None:
            return

        await self.community.ladder(ctx, context[0])


class LeagueCommunityCommandHandler:

    def __init__(self, bot):
        self.bot = bot

    async def register(self, ctx: commands.Context, broadcaster_id: str, config: LeagueConfig, riot_id: str | None) -> None:
        if not riot_id:
            await ctx.reply("Use it like this: !register PlayerName#TAG or !register PlayerName#TAG REGION")
            return

        chatter = ctx.chatter
        display_name = getattr(chatter, "display_name", None) or chatter.name

        try:
            community_rank = await self.bot.services.league.register_player(
                broadcaster_id, str(chatter.id), chatter.name, display_name, riot_id, config.region
            )
        except ValueError as error:
            await ctx.reply(str(error))
            return
        except LeagueProviderError:
            LOGGER.exception("[League] OP.GG could not register Riot ID %s for Twitch user %s.", riot_id, chatter.id)
            await ctx.reply("I couldn't find that Riot ID. Check the name, tag, and region, then try again.")
            return
        except Exception:
            LOGGER.exception("[League] Failed to register Riot ID %s for Twitch user %s.", riot_id, chatter.id)
            await ctx.reply("I couldn't register that Riot ID right now. Please try again later.")
            return

        await ctx.reply(self.registration_message(community_rank))

    async def unregister(self, ctx: commands.Context, broadcaster_id: str) -> None:
        removed = await self.bot.services.league.unregister_player(broadcaster_id, str(ctx.chatter.id))

        if not removed:
            await ctx.reply("You don't have a League account registered in this channel.")
            return

        await ctx.reply("Your League registration and saved rank history have been removed from this channel.")

    async def rank(self, ctx: commands.Context, broadcaster_id: str, target: User | None) -> None:
        chatter = target or ctx.chatter
        community_rank = await self.bot.services.league.get_community_rank(broadcaster_id, str(chatter.id))

        if community_rank is None:
            username = getattr(chatter, "display_name", None) or chatter.name

            if target is None:
                await ctx.reply("You aren't registered yet. Use !register PlayerName#TAG to join the community ladder.")
            else:
                await ctx.reply(f"{username} hasn't registered a League account in this channel.")

            return

        await ctx.send(self.rank_message(community_rank))

    async def ladder(self, ctx: commands.Context, broadcaster_id: str) -> None:
        entries = await self.bot.services.league.get_ladder(broadcaster_id)

        if not entries:
            await ctx.reply("The community League ladder is empty. Use !register PlayerName#TAG to join it.")
            return

        positions = []

        for index, entry in enumerate(entries, start=1):
            username = entry.registration.twitch_display_name
            rank = self.format_rank(entry.rank) if entry.rank and entry.rank.tier else "Unranked"
            positions.append(f"{index}. {username} — {rank}")

        await ctx.send(f"Community Solo/Duo ladder: {' | '.join(positions)}")

    @classmethod
    def registration_message(cls, community_rank: CommunityRank) -> str:
        registration = community_rank.registration
        riot_id = f"{registration.game_name}#{registration.tag_line}"

        if community_rank.rank is None or community_rank.rank.tier is None:
            return f"Registered {riot_id} ({registration.region}). This account is currently unranked in Solo/Duo."

        return f"Registered {riot_id} ({registration.region}) at {cls.format_rank(community_rank.rank)} Solo/Duo."

    @classmethod
    def rank_message(cls, community_rank: CommunityRank) -> str:
        registration = community_rank.registration
        riot_id = f"{registration.game_name}#{registration.tag_line}"
        username = registration.twitch_display_name
        rank = community_rank.rank

        if rank is None or rank.tier is None:
            return f"{username} ({riot_id}) is currently unranked in Solo/Duo."

        return f"{username} ({riot_id}) is {cls.format_rank(rank)} in Solo/Duo with a {rank.win_rate:.1f}% win rate ({rank.wins}W–{rank.losses}L)."

    @staticmethod
    def format_rank(rank: RankEntry) -> str:
        tier = rank.tier.title() if rank.tier else "Unranked"
        division = f" {rank.division}" if rank.division else ""
        return f"{tier}{division}, {rank.lp} LP"
