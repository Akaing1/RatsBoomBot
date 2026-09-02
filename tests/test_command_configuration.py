from unittest.mock import patch

from bot.bot import TwitchBot
from bot.channels.meinya_yozakura.profile import MEINYA_PROFILE
from bot.channels.ninjakaing.profile import NINJAKAING_PROFILE
from bot.profiles import render_profile_message
from config.settings import settings


def test_bot_commands_are_case_insensitive() -> None:
    with patch("twitchio.ext.commands.AutoBot.__init__", return_value=None) as initialize:
        TwitchBot(token_database=None, subs=[], broadcaster_ids=[])

    assert initialize.call_args.kwargs["case_insensitive"] is True


def test_bot_authorization_includes_announcement_scope() -> None:
    assert "moderator:manage:announcements" in settings.BOT_SCOPES.split()


def test_social_messages_are_configured_per_profile() -> None:
    assert NINJAKAING_PROFILE.social_messages != MEINYA_PROFILE.social_messages
    assert render_profile_message(
        MEINYA_PROFILE.social_messages.overview,
        discord_url="https://discord.example",
        youtube_url="https://youtube.example"
    ) == (
        "Find more from the Blood Sakura Garden: "
        "Discord: https://discord.example | YouTube: https://youtube.example"
    )


def test_meinya_uses_final_fantasy_fourteen_raid_pilot() -> None:
    config = MEINYA_PROFILE.raid_bosses

    assert config.enabled is True
    assert MEINYA_PROFILE.features.raid_bosses is True
    assert config.tutorial_name == "Striking Dummy"
    assert config.names.melee == "Dragon-king Thordan"
    assert config.names.ranged == "The Ultima Weapon"
    assert config.names.magic == "Bahamut Prime"
    assert config.mini_names.melee == "Behemoth"
    assert config.mini_names.ranged == "Magitek Gunship"
    assert config.mini_names.magic == "Ahriman"
    assert config.weapon_names.basic_sword == "Weathered Shortsword"
    assert config.weapon_names.refined_sword == "Lost Allagan Saber"
    assert config.weapon_names.masterwork_sword == "Burtgang"
    assert config.weapon_names.mythical_blade == "Ultimate Sword of the Heavens"
    assert config.weapon_names.basic_bow == "Weathered Shortbow"
    assert config.weapon_names.refined_bow == "Lost Allagan Composite Bow"
    assert config.weapon_names.masterwork_bow == "Rosenbogen"
    assert config.weapon_names.mythical_longbow == "Ultimate Bow of the Heavens"
    assert config.weapon_names.apprentice_tome == "Weathered Grimoire"
    assert config.weapon_names.enchanted_tome == "Lost Allagan Grimoire"
    assert config.weapon_names.archmage_grimoire == "Ona Ramuhda"
    assert config.weapon_names.mythical_grimoire == "Ultimate Grimoire of the Heavens"
    assert config.weapon_cost == 5000
    assert config.potion_cost == 1500
    assert config.weapon_durability == 15
    assert config.repair_cost == 1500


def test_meinya_uses_custom_ad_announcement_message() -> None:
    assert MEINYA_PROFILE.ad_announcement_message == "3 minutes of ads starting in ~{time}! We have to run 3 minutes of ads at the top of every hour to disable the prerolls, so please forgive me! See you soon!"
