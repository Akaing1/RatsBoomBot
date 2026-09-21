import logging
import random

from twitchio import User
from twitchio.ext import commands

from bot.profiles import GlobalCommandGroup, LeagueConfig, ProfileFeatureName, get_active_profile
from bot.services.engagement.league import ChampionRecommendation, CommunityRank, LeagueProviderError, RankEntry
from bot.shared.commands.converters import LocalizedUser
from bot.shared.commands.helpers import get_context_broadcaster_id, is_global_group_enabled, is_profile_feature_enabled
from bot.shared.commands.viewer_queue import is_mod_or_broadcaster

LOGGER = logging.getLogger("RatBoomBot")


def assign_custom_lobby_teams(players: list[dict[str, str]], ranks: dict[str, CommunityRank], *, balanced: bool) -> tuple[list[str], list[str]]:
    shuffled_players = list(players)
    random.shuffle(shuffled_players)
    first_team_size = (len(shuffled_players) + 1) // 2
    team_limits = (first_team_size, len(shuffled_players) - first_team_size)

    if not balanced:
        return (
            [player["display_name"] for player in shuffled_players[:first_team_size]],
            [player["display_name"] for player in shuffled_players[first_team_size:]]
        )

    ranked_players = []
    unranked_players = []

    for player in shuffled_players:
        community_rank = ranks.get(player["username"].casefold())

        if community_rank is None or community_rank.rank is None or community_rank.rank.tier is None:
            unranked_players.append(player)
        else:
            ranked_players.append((community_rank.rank.score, player))

    ranked_players.sort(key=lambda entry: entry[0], reverse=True)
    teams = ([], [])
    team_scores = [0, 0]

    for score, player in ranked_players:
        available_teams = [index for index in range(2) if len(teams[index]) < team_limits[index]]
        team_index = min(available_teams, key=lambda index: (team_scores[index], len(teams[index])))
        teams[team_index].append(player["display_name"])
        team_scores[team_index] += score

    random.shuffle(unranked_players)

    for player in unranked_players:
        available_teams = [index for index in range(2) if len(teams[index]) < team_limits[index]]
        team_index = min(available_teams, key=lambda index: len(teams[index]))
        teams[team_index].append(player["display_name"])

    return teams


class LeagueCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot
        self.community = LeagueCommunityCommandHandler(bot)

    def get_context(self, ctx: commands.Context) -> tuple[str, LeagueConfig] | None:
        broadcaster_id = get_context_broadcaster_id(ctx)

        if broadcaster_id is None or not is_profile_feature_enabled(self.bot, ctx, ProfileFeatureName.LEAGUE):
            return None

        profile = get_active_profile(broadcaster_id)

        if profile is None:
            return None

        return broadcaster_id, profile.league

    @commands.command(name="champs")
    async def champions(self, ctx: commands.Context, *, champion: str | None = None) -> None:
        context = self.get_context(ctx)

        if context is None:
            return

        broadcaster_id, config = context

        if not config.game_name or not config.tag_line:
            await ctx.send("This channel's League account is not configured yet. Community commands !register, !rank, and !ladder are available.")
            return

        if champion:
            await self.send_core_build(ctx, broadcaster_id, config, champion)
            return

        top_champions = await self.bot.services.league.get_top_champions(broadcaster_id)

        if not top_champions:
            await ctx.send(f"No ranked champion data is available for {config.display_name} yet. OP.GG may not have ranked games for this season, or the data may still be loading.")
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

    @commands.command(name="build")
    async def build(self, ctx: commands.Context, *, champion: str | None = None) -> None:
        if self.get_context(ctx) is None:
            return

        if not champion:
            await ctx.reply("Use it like this: !build <champion name>")
            return

        recommendation = await self.get_champion_recommendation(ctx, champion)

        if recommendation is None:
            return

        items = ", ".join(recommendation.item_names)
        await ctx.send(
            f"Most common {recommendation.champion_name} {recommendation.position.title()} core: {items} "
            f"({recommendation.item_pick_rate:.1%} pick rate)."
        )

    @commands.command(name="runes")
    async def runes(self, ctx: commands.Context, *, champion: str | None = None) -> None:
        if self.get_context(ctx) is None:
            return

        if not champion:
            await ctx.reply("Use it like this: !runes <champion name>")
            return

        recommendation = await self.get_champion_recommendation(ctx, champion)

        if recommendation is None:
            return

        primary = ", ".join(recommendation.primary_runes)
        secondary = ", ".join(recommendation.secondary_runes)
        await ctx.send(
            f"Most common {recommendation.champion_name} {recommendation.position.title()} runes: "
            f"{recommendation.primary_rune_page} ({primary}) + {recommendation.secondary_rune_page} ({secondary}) "
            f"({recommendation.rune_pick_rate:.1%} pick rate)."
        )

    async def get_champion_recommendation(self, ctx: commands.Context, champion: str) -> ChampionRecommendation | None:
        try:
            recommendation = await self.bot.services.league.get_champion_recommendation(champion.strip())
        except LeagueProviderError:
            LOGGER.exception("[League] OP.GG could not load a recommendation for %s.", champion)
            await ctx.reply("I couldn't load that champion from OP.GG right now. Check the name and try again.")
            return None
        except Exception:
            LOGGER.exception("[League] Failed to load a recommendation for %s.", champion)
            await ctx.reply("I couldn't load OP.GG recommendations right now. Please try again later.")
            return None

        if recommendation is None:
            await ctx.reply(f"I couldn't find a ranked build for {champion.strip()}.")

        return recommendation

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

    @commands.command(name="duo")
    async def duo(self, ctx: commands.Context) -> None:
        context = self.get_context(ctx)

        if context is None:
            return

        broadcaster_id, _config = context
        requester = await self.bot.services.league.get_community_rank(broadcaster_id, str(ctx.chatter.id))

        if requester is None:
            await ctx.reply("Register your League account with !register PlayerName#TAG before looking for a duo.")
            return

        if requester.rank is None or requester.rank.tier is None:
            await ctx.reply("Your registered account is unranked in Solo/Duo, so I can't determine your ranked range.")
            return

        try:
            active_logins = await self.get_active_chatter_logins(broadcaster_id)
        except Exception:
            LOGGER.exception("[League] Could not fetch active chatters for !duo in broadcaster %s.", broadcaster_id)
            await ctx.reply("I couldn't check who is currently in chat. Please try !duo again later.")
            return

        matches = await self.bot.services.league.get_duo_matches(
            broadcaster_id, str(ctx.chatter.id), active_logins, limit=3
        )

        if not matches:
            await ctx.reply("There is no one in chat within your ranked range right now.")
            return

        entries = [
            f"{match.registration.twitch_display_name} ({self.community.format_rank(match.rank)})"
            for match in matches
        ]
        await ctx.reply(f"Closest duo matches in chat: {' | '.join(entries)}")

    async def get_active_chatter_logins(self, broadcaster_id: str) -> set[str]:
        broadcaster = self.bot.create_partialuser(str(broadcaster_id))
        moderator_id = str(self.bot.services.chat_identity.sender_id(broadcaster_id))
        chatters = await broadcaster.fetch_chatters(moderator=moderator_id, first=1000, max_results=None)
        active_logins = set()

        async for chatter in chatters.users:
            active_logins.add(str(chatter.name).casefold())

        return active_logins

    @commands.group(name="custom", invoke_fallback=True, case_insensitive=True)
    async def custom(self, ctx: commands.Context) -> None:
        if self.get_context(ctx) is not None:
            await ctx.reply("Use !custom lobby for random teams or !custom lobby balance for rank-balanced teams.")

    @custom.group(name="lobby", invoke_fallback=True, case_insensitive=True)
    async def custom_lobby(self, ctx: commands.Context) -> None:
        await self.create_custom_lobby(ctx, balanced=False)

    @custom_lobby.command(name="balance")
    async def custom_lobby_balance(self, ctx: commands.Context) -> None:
        await self.create_custom_lobby(ctx, balanced=True)

    async def create_custom_lobby(self, ctx: commands.Context, *, balanced: bool) -> None:
        context = self.get_context(ctx)

        if context is None:
            return

        if not is_mod_or_broadcaster(ctx):
            await ctx.reply("Only the broadcaster or mods can create a custom lobby.")
            return

        if not is_global_group_enabled(self.bot, ctx, GlobalCommandGroup.VIEWER_QUEUE):
            await ctx.reply("The viewer queue is disabled for this channel.")
            return

        broadcaster_id, _config = context
        broadcaster = getattr(ctx, "broadcaster", None) or getattr(ctx, "channel", None)
        broadcaster_login = str(getattr(broadcaster, "name", "") or "").casefold()
        broadcaster_name = str(getattr(broadcaster, "display_name", None) or broadcaster_login or "Broadcaster")
        queued_members = await self.bot.services.viewer_queue.take_queue_members(
            broadcaster_id, 9, exclude={broadcaster_login} if broadcaster_login else set()
        )

        if not queued_members:
            await ctx.reply("The viewer queue is empty, so there is no custom lobby to create.")
            return

        players = [{"username": broadcaster_login, "display_name": broadcaster_name}, *queued_members]
        ranks = {}

        if balanced:
            ranks = await self.bot.services.league.get_community_ranks_by_login(
                broadcaster_id, {player["username"] for player in players}
            )

        first_team, second_team = assign_custom_lobby_teams(players, ranks, balanced=balanced)
        lobby_type = "Rank-balanced custom lobby" if balanced else "Custom lobby"
        await ctx.send(
            f"{lobby_type} — Team 1: {', '.join(first_team)} | Team 2: {', '.join(second_team)}"
        )


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
            LOGGER.exception("[League] OP.GG could not register Riot ID %s for Twitch user %s.", riot_id, chatter.id, extra={"broadcaster_id": broadcaster_id})
            await ctx.reply("I couldn't find that Riot ID. Check the name, tag, and region, then try again.")
            return
        except Exception:
            LOGGER.exception("[League] Failed to register Riot ID %s for Twitch user %s.", riot_id, chatter.id, extra={"broadcaster_id": broadcaster_id})
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
