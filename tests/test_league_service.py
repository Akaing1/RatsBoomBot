from datetime import UTC, datetime
from types import SimpleNamespace

import asqlite
import pytest

from bot.profiles import ChannelProfile, LeagueConfig, activate_profile, clear_profiles
from bot.services.engagement.league import ChampionRecommendation, CommunityRank, CoreBuild, LeagueRegistration, LeagueService, OpggMcpClient, RankEntry, RankProfile, RecentMatch, SeasonSummary, SeasonalChampion, parse_typed_response
from bot.shared.commands.league import LeagueCommands, assign_custom_lobby_teams


@pytest.mark.asyncio
async def test_null_ranked_summary_is_confirmed_before_returning_empty(monkeypatch) -> None:
    from bot.services.engagement.league import LeagueProviderError
    client = OpggMcpClient()
    calls = []
    parent_response = "LolGetSummonerProfile(Data(Summoner(null)))"

    async def fake_call(name, arguments):
        calls.append(arguments)
        if arguments["desired_output_fields"] == ["data.summoner.ranked_most_champions"]:
            return parent_response
        return 'LolGetSummonerProfile(FieldDiagnostics(["ranked_most_champions"],"unmatched fields"))'

    monkeypatch.setattr(client, "call_tool", fake_call)
    config = LeagueConfig(game_name="Rat Pee", tag_line="Boom")
    assert await client.fetch_season_summary(config) == SeasonSummary("", "RANKED", ())
    assert len(calls) == 2
    parent_response = 'LolGetSummonerProfile(FieldDiagnostics(["ranked_most_champions"],"schema changed"))'
    with pytest.raises(LeagueProviderError, match="schema changed"):
        await client.fetch_season_summary(config)


def test_response_data_accepts_diagnostics_before_data() -> None:
    from bot.services.engagement.league import response_data, unwrap_typed
    root = parse_typed_response('LolGetSummonerProfile(FieldDiagnostics([],"hint"),Data(Summoner(null)))')
    assert unwrap_typed(response_data(root, "LolGetSummonerProfile"), "Data")[0].name == "Summoner"


def test_typed_response_parser_rejects_executable_python() -> None:
    with pytest.raises(Exception):
        parse_typed_response("__import__('os').system('echo unsafe')")


def test_opgg_profile_parser_reads_seasonal_champion_pool(monkeypatch) -> None:
    response = """class LolGetSummonerProfile: data

LolGetSummonerProfile(Data(Summoner(RankedMostChampions(\"RANKED\",33,340,180,160,[MyChampionStat(100,60,40,\"Lux\"),MyChampionStat(80,32,48,\"Ahri\")]))))"""
    client = OpggMcpClient()

    async def fake_call_tool(name, arguments):
        return response

    monkeypatch.setattr(client, "call_tool", fake_call_tool)

    async def run_test():
        summary = await client.fetch_season_summary(LeagueConfig(game_name="steohany", tag_line="ant"))
        assert summary == SeasonSummary(
            season_id="33",
            game_type="RANKED",
            champions=(SeasonalChampion("Lux", 100, 60, 40), SeasonalChampion("Ahri", 80, 32, 48))
        )

    import asyncio
    asyncio.run(run_test())


def test_opgg_profile_parser_reads_ranked_queues(monkeypatch) -> None:
    response = """class LolGetSummonerProfile: data

LolGetSummonerProfile(Data(Summoner("steohany","ant",[LeagueStat("SOLORANKED",TierInfo("PLATINUM",4,32,null),261,264),LeagueStat("FLEXRANKED",TierInfo("GOLD",2,8,null),69,65),LeagueStat("ARENA",TierInfo(null,null,null,null),null,null)])))"""
    client = OpggMcpClient()

    async def fake_call_tool(name, arguments):
        return response

    monkeypatch.setattr(client, "call_tool", fake_call_tool)

    async def run_test():
        profile = await client.fetch_rank_profile("steohany", "ant", "NA")
        assert profile == RankProfile(
            game_name="steohany",
            tag_line="ant",
            region="NA",
            ranks=(
                RankEntry("SOLORANKED", "PLATINUM", "IV", 32, 261, 264),
                RankEntry("FLEXRANKED", "GOLD", "II", 8, 69, 65)
            )
        )

    import asyncio
    asyncio.run(run_test())


@pytest.mark.asyncio
async def test_opgg_champion_recommendation_uses_primary_role(monkeypatch) -> None:
    position_response = """class LolListLaneMetaChampions: data
class Data: positions
class Positions: top,mid,jungle,adc,support
class Top: champion,role_rate

LolListLaneMetaChampions(Data(Positions([Top("Lux",0.1)],[Top("Lux",0.8)],[],[],[Top("Lux",0.2)])))"""
    analysis_response = """class LolGetChampionAnalysis: champion,position,data
class Data: core_items,runes
class CoreItems: ids_names,play,win,pick_rate
class Runes: primary_page_name,primary_rune_names,secondary_page_name,secondary_rune_names,stat_mod_names,play,win,pick_rate

LolGetChampionAnalysis("LUX","MID",Data(CoreItems(["Luden's Echo","Stormsurge","Shadowflame"],8214,4342,0.18),Runes("Sorcery",["Arcane Comet","Manaflow Band","Transcendence","Scorch"],"Domination",["Ultimate Hunter","Cheap Shot"],[5008,5008,5001],29051,14775,0.39)))"""
    client = OpggMcpClient()
    calls = []

    async def fake_call_tool(name, arguments):
        calls.append((name, arguments))
        return position_response if name == "lol_list_lane_meta_champions" else analysis_response

    monkeypatch.setattr(client, "call_tool", fake_call_tool)

    recommendation = await client.fetch_champion_recommendation("lux")

    assert recommendation == ChampionRecommendation(
        champion_name="Lux",
        position="mid",
        item_names=("Luden's Echo", "Stormsurge", "Shadowflame"),
        item_pick_rate=0.18,
        primary_rune_page="Sorcery",
        primary_runes=("Arcane Comet", "Manaflow Band", "Transcendence", "Scorch"),
        secondary_rune_page="Domination",
        secondary_runes=("Ultimate Hunter", "Cheap Shot"),
        rune_pick_rate=0.39
    )
    assert calls[1][1]["champion"] == "LUX"
    assert calls[1][1]["position"] == "mid"


def test_registration_parser_supports_spaced_names_and_optional_regions() -> None:
    assert LeagueService.parse_registration("Hide on bush#KR1 KR", "NA") == ("Hide on bush", "KR1", "KR")
    assert LeagueService.parse_registration("steohany#ant", "NA") == ("steohany", "ant", "NA")

    with pytest.raises(ValueError):
        LeagueService.parse_registration("missing-tag", "NA")


@pytest.mark.asyncio
async def test_league_data_persists_and_build_uses_repeated_completed_core(tmp_path) -> None:
    database_path = tmp_path / "league.db"
    config = LeagueConfig(enabled=True, game_name="steohany", tag_line="ant", display_name="Steohany")

    async with asqlite.create_pool(str(database_path)) as database:
        service = LeagueService(bot=None, db=database)
        await service.setup()
        await service.save_season_summary("channel-1", "opgg", SeasonSummary(
            season_id="33",
            game_type="RANKED",
            champions=(
                SeasonalChampion("Lux", 100, 60, 40),
                SeasonalChampion("Ahri", 80, 32, 48),
                SeasonalChampion("Nami", 40, 20, 20)
            )
        ))
        now = datetime.now(UTC).isoformat()
        matches = (
            RecentMatch("match-1", now, "SOLORANKED", 1800, "Lux", "WIN", (6655, 4645, 3157, 3175, 1058), None),
            RecentMatch("match-2", now, "SOLORANKED", 1900, "Lux", "LOSE", (6655, 4645, 3157, 3175), None),
            RecentMatch("normal-1", now, "NORMAL", 1900, "Lux", "WIN", (6655, 4645, 3157), None)
        )
        assert await service.save_matches("channel-1", matches) == 2
        assert await service.save_matches("channel-1", matches) == 0

        item_query = """
        INSERT INTO league_items (item_id, name, from_items, into_items, gold_purchasable, is_boot, refreshed_at)
        VALUES (?, ?, ?, ?, 1, ?, ?)
        """
        items = (
            (6655, "Luden's Echo", "[1026]", "[]", 0),
            (4645, "Shadowflame", "[1026]", "[]", 0),
            (3157, "Zhonya's Hourglass", "[2420]", "[]", 0),
            (3175, "Spellslinger's Shoes", "[1001]", "[]", 1),
            (1058, "Needlessly Large Rod", "[]", "[3089]", 0)
        )

        async with database.acquire() as connection:
            for item_id, name, from_items, into_items, is_boot in items:
                await connection.execute(item_query, (item_id, name, from_items, into_items, is_boot, now))

        top_champions = await service.get_top_champions("channel-1", limit=2)
        assert [champion.name for champion in top_champions] == ["Lux", "Ahri"]

        build = await service.get_core_build("channel-1", "lux", config)
        assert build is not None
        assert build.item_names == ("Zhonya's Hourglass", "Shadowflame", "Luden's Echo")
        assert build.games == 2
        assert build.matching_games == 2

    async with asqlite.create_pool(str(database_path)) as reopened_database:
        reopened_service = LeagueService(bot=None, db=reopened_database)
        await reopened_service.setup()
        assert [champion.name for champion in await reopened_service.get_top_champions("channel-1")] == ["Lux", "Ahri", "Nami"]


@pytest.mark.asyncio
async def test_community_ranks_are_channel_scoped_ordered_and_removable(tmp_path) -> None:
    database_path = tmp_path / "league-community.db"

    async with asqlite.create_pool(str(database_path)) as database:
        service = LeagueService(bot=None, db=database)
        await service.setup()
        now = datetime.now(UTC).isoformat()
        registration_query = """
        INSERT INTO league_registrations (
            broadcaster_id, user_id, twitch_login, twitch_display_name,
            game_name, tag_line, region, registered_at, refreshed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        async with database.acquire() as connection:
            await connection.execute(registration_query, ("channel-1", "user-1", "alice", "Alice", "Alice", "NA1", "NA", now, now))
            await connection.execute(registration_query, ("channel-1", "user-2", "bob", "Bob", "Bob", "NA1", "NA", now, now))
            await connection.execute(registration_query, ("channel-2", "user-1", "alice", "Alice", "Alice", "NA1", "NA", now, now))

        await service.save_registration_ranks("channel-1", "user-1", RankProfile("Alice", "NA1", "NA", (RankEntry("SOLORANKED", "GOLD", "I", 50, 20, 10),)))
        await service.save_registration_ranks("channel-1", "user-2", RankProfile("Bob", "NA1", "NA", (RankEntry("SOLORANKED", "PLATINUM", "IV", 1, 12, 12),)))
        await service.save_registration_ranks("channel-2", "user-1", RankProfile("Alice", "NA1", "NA", (RankEntry("SOLORANKED", "DIAMOND", "IV", 1, 30, 20),)))

        ladder = await service.get_ladder("channel-1")
        assert [entry.registration.twitch_display_name for entry in ladder] == ["Bob", "Alice"]
        assert (await service.get_community_rank("channel-1", "user-1")).rank.tier == "GOLD"
        assert (await service.get_community_rank("channel-2", "user-1")).rank.tier == "DIAMOND"

        assert await service.unregister_player("channel-1", "user-1") is True
        assert await service.get_community_rank("channel-1", "user-1") is None
        assert await service.get_community_rank("channel-2", "user-1") is not None


@pytest.mark.asyncio
async def test_duo_matches_require_presence_region_and_compatible_rank(tmp_path) -> None:
    database_path = tmp_path / "league-duos.db"

    async with asqlite.create_pool(str(database_path)) as database:
        service = LeagueService(bot=None, db=database)
        await service.setup()
        now = datetime.now(UTC).isoformat()
        players = (
            ("requester", "requester", "Requester", "NA", RankEntry("SOLORANKED", "GOLD", "I", 50, 20, 10)),
            ("platinum", "platinum", "Platinum", "NA", RankEntry("SOLORANKED", "PLATINUM", "IV", 1, 20, 10)),
            ("silver", "silver", "Silver", "NA", RankEntry("SOLORANKED", "SILVER", "I", 50, 20, 10)),
            ("diamond", "diamond", "Diamond", "NA", RankEntry("SOLORANKED", "DIAMOND", "IV", 1, 20, 10)),
            ("euw", "euw", "EUW", "EUW", RankEntry("SOLORANKED", "GOLD", "I", 49, 20, 10)),
            ("absent", "absent", "Absent", "NA", RankEntry("SOLORANKED", "GOLD", "I", 49, 20, 10))
        )

        async with database.acquire() as connection:
            for user_id, login, display_name, region, _rank in players:
                await connection.execute(
                    """
                    INSERT INTO league_registrations (
                        broadcaster_id, user_id, twitch_login, twitch_display_name,
                        game_name, tag_line, region, registered_at, refreshed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("channel-1", user_id, login, display_name, display_name, "NA1", region, now, now)
                )

        for user_id, _login, display_name, region, rank in players:
            await service.save_registration_ranks("channel-1", user_id, RankProfile(display_name, "NA1", region, (rank,)))

        matches = await service.get_duo_matches(
            "channel-1", "requester", {"requester", "platinum", "silver", "diamond", "euw"}
        )

        assert [match.registration.twitch_login for match in matches] == ["platinum", "silver"]


def test_balanced_custom_lobby_uses_ranked_players_then_randomly_fills_unranked(monkeypatch) -> None:
    monkeypatch.setattr("bot.shared.commands.league.random.shuffle", lambda values: None)
    players = [
        {"username": "one", "display_name": "One"},
        {"username": "two", "display_name": "Two"},
        {"username": "three", "display_name": "Three"},
        {"username": "four", "display_name": "Four"},
        {"username": "five", "display_name": "Five"},
        {"username": "six", "display_name": "Six"}
    ]
    ranks = {}

    for login, tier, division, lp in (
        ("one", "DIAMOND", "I", 0),
        ("two", "DIAMOND", "II", 0),
        ("three", "PLATINUM", "I", 0),
        ("four", "PLATINUM", "II", 0)
    ):
        registration = LeagueRegistration("channel-1", login, login, login.title(), login, "NA1", "NA", "now")
        ranks[login] = CommunityRank(registration, RankEntry("SOLORANKED", tier, division, lp, 1, 1))

    first_team, second_team = assign_custom_lobby_teams(players, ranks, balanced=True)

    assert len(first_team) == len(second_team) == 3
    assert {"One", "Two"} != set(first_team[:2])
    assert set(first_team + second_team) == {player["display_name"] for player in players}


class FakeLeagueService:

    async def get_top_champions(self, broadcaster_id: str):
        return (SeasonalChampion("Lux", 100, 60, 40), SeasonalChampion("Ahri", 80, 32, 48))

    async def get_core_build(self, broadcaster_id: str, champion: str, config: LeagueConfig):
        return CoreBuild("Lux", ("Luden's Echo", "Shadowflame", "Zhonya's Hourglass"), 6, 2)

    async def get_champion_recommendation(self, champion: str):
        return ChampionRecommendation(
            "Lux", "mid", ("Luden's Echo", "Stormsurge", "Shadowflame"), 0.18,
            "Sorcery", ("Arcane Comet", "Manaflow Band", "Transcendence", "Scorch"),
            "Domination", ("Ultimate Hunter", "Cheap Shot"), 0.39
        )


class FakeFeatures:

    @staticmethod
    def is_profile_feature_enabled(broadcaster_id, feature) -> bool:
        return True


class FakeContext:

    def __init__(self):
        self.broadcaster = SimpleNamespace(id="channel-1")
        self.messages = []

    async def send(self, message: str) -> None:
        self.messages.append(message)

    async def reply(self, message: str) -> None:
        self.messages.append(message)


@pytest.mark.asyncio
async def test_dashboard_override_enables_default_disabled_league(monkeypatch) -> None:
    profile = ChannelProfile(channel_name="uat", league=LeagueConfig(enabled=False))
    features = FakeFeatures()
    bot = SimpleNamespace(services=SimpleNamespace(features=features))
    activate_profile("channel-1", profile)
    component = LeagueCommands(bot)
    context = FakeContext()
    service = LeagueService(bot, None)

    try:
        assert component.get_context(context) == ("channel-1", profile.league)
        assert service.configured_profiles() == (("channel-1", profile.league),)
        await component.champions.callback(component, context, champion=None)
        assert "not configured yet" in context.messages[0]
        monkeypatch.setattr(features, "is_profile_feature_enabled", lambda *args: False)
        assert component.get_context(context) is None
        assert service.configured_profiles() == ()
    finally:
        clear_profiles()


@pytest.mark.asyncio
async def test_champs_command_formats_season_and_recent_build_messages() -> None:
    config = LeagueConfig(enabled=True, display_name="Steohany", game_name="Steohany", tag_line="NA1")
    profile = ChannelProfile(channel_name="steohanyy", league=config)
    bot = SimpleNamespace(services=SimpleNamespace(features=FakeFeatures(), league=FakeLeagueService()))
    activate_profile("channel-1", profile)
    component = LeagueCommands(bot)
    context = FakeContext()

    try:
        await component.champions.callback(component, context, champion=None)
        await component.champions.callback(component, context, champion="lux")
    finally:
        clear_profiles()

    assert context.messages == [
        "Steohany's most-played ranked champions this season: Lux (60.0% WR), Ahri (40.0% WR)",
        "Steohany's most common Lux core includes: Luden's Echo, Shadowflame, and Zhonya's Hourglass."
    ]


@pytest.mark.asyncio
async def test_build_and_runes_commands_format_opgg_recommendations() -> None:
    config = LeagueConfig(enabled=True, display_name="Steohany", game_name="Steohany", tag_line="NA1")
    profile = ChannelProfile(channel_name="steohanyy", league=config)
    bot = SimpleNamespace(services=SimpleNamespace(features=FakeFeatures(), league=FakeLeagueService()))
    activate_profile("channel-1", profile)
    component = LeagueCommands(bot)
    context = FakeContext()

    try:
        await component.build.callback(component, context, champion="lux")
        await component.runes.callback(component, context, champion="lux")
    finally:
        clear_profiles()

    assert context.messages == [
        "Most common Lux Mid core: Luden's Echo, Stormsurge, Shadowflame (18.0% pick rate).",
        "Most common Lux Mid runes: Sorcery (Arcane Comet, Manaflow Band, Transcendence, Scorch) + Domination (Ultimate Hunter, Cheap Shot) (39.0% pick rate)."
    ]
