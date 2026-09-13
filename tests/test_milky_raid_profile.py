from bot.channels.milky_galaxyvt.profile import MILKY_GALAXYVT_PROFILE
from bot.services.engagement.raid_boss import RaidBossService


def test_milky_raid_profile_uses_overwatch_loadout() -> None:
    config = MILKY_GALAXYVT_PROFILE.raid_bosses

    assert MILKY_GALAXYVT_PROFILE.features.raid_bosses is True
    assert config.enabled is True
    assert config.weapon_cost == 5000
    assert config.refined_crafting_cost == 5000
    assert config.masterwork_crafting_cost == 25000
    assert config.weapon_names.basic_sword == "Whip Flail"
    assert config.weapon_names.refined_sword == "Dragon Blade"
    assert config.weapon_names.masterwork_sword == "Reinhardt Hammer"
    assert config.weapon_names.mythical_blade == "The Doomfist Gauntlet"
    assert config.weapon_names.basic_bow == "Mercy's Blaster"
    assert config.weapon_names.refined_bow == "Dragon Bow"
    assert config.weapon_names.masterwork_bow == "Junkrat's Launcher"
    assert config.weapon_names.mythical_longbow == "Dual Miniguns"
    assert config.weapon_names.apprentice_tome == "Zenyatta's Balls"
    assert config.weapon_names.enchanted_tome == "Wuyangs Water Staff"
    assert config.weapon_names.archmage_grimoire == "Anran's Fire Fans"
    assert config.weapon_names.mythical_grimoire == "Sigma's Black Holes"


def test_milky_custom_item_names_are_valid_purchase_aliases() -> None:
    config = MILKY_GALAXYVT_PROFILE.raid_bosses

    assert RaidBossService.normalize_item("Pocket Mercy", config) == "potion"
    assert RaidBossService.normalize_item("Cooldown Refresh", config) == "second_wind"
    assert RaidBossService.normalize_item("Pocket Nano", config) == "berserk"
    assert RaidBossService.normalize_item("Valkyrie Boost", config) == "blessing"
    assert RaidBossService.normalize_item("Dmon Limit Break", config) == "ancient_pact"
    assert RaidBossService.normalize_item("Orisa Drum", config) == "flag_bearer"


def test_default_item_aliases_remain_valid_for_milky() -> None:
    config = MILKY_GALAXYVT_PROFILE.raid_bosses

    assert RaidBossService.normalize_item("potion", config) == "potion"
    assert RaidBossService.normalize_item("second wind", config) == "second_wind"
    assert RaidBossService.normalize_item("berserk", config) == "berserk"
    assert RaidBossService.normalize_item("blessing", config) == "blessing"
    assert RaidBossService.normalize_item("pact", config) == "ancient_pact"
    assert RaidBossService.normalize_item("flag", config) == "flag_bearer"
