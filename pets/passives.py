"""Pet passive catalog and level scaling, shared by all game integrations."""

from dataclasses import dataclass


COMMON = "common"
RARE = "rare"
ULTRA_RARE = "ultra_rare"

LOYALTY_GAIN = "loyalty_gain"
RAID_DAMAGE = "raid_damage"
GAMBLE_ODDS = "gamble_odds"
RAID_PROFIT = "raid_profit"
RARE_DROP_CHANCE = "rare_drop_chance"
KAMIKAZE_ODDS = "kamikaze_odds"
GAMBLE_LOSS_REFUND = "gamble_loss_refund"


@dataclass(frozen=True)
class PassiveDefinition:
    name: str
    rarity: str
    min_bps: int
    max_bps: int
    description: str


PASSIVES = {
    LOYALTY_GAIN: PassiveDefinition("Loyalty Gain", COMMON, 1000, 1500, "bonus loyalty points earned"),
    RAID_DAMAGE: PassiveDefinition("Boss Hunt Damage", COMMON, 1000, 2000, "bonus Boss Hunt damage"),
    GAMBLE_ODDS: PassiveDefinition("Gamble Luck", COMMON, 500, 1000, "added gamble win chance"),
    RAID_PROFIT: PassiveDefinition("Boss Hunt Profit", COMMON, 1000, 2000, "bonus Boss Hunt point rewards"),
    RARE_DROP_CHANCE: PassiveDefinition("Rare Drop Luck", RARE, 100, 500, "added mythical weapon drop chance"),
    KAMIKAZE_ODDS: PassiveDefinition("Kamikaze Luck", RARE, 500, 1000, "added kamikaze hit chance"),
    GAMBLE_LOSS_REFUND: PassiveDefinition("Second Chance", ULTRA_RARE, 1000, 1000, "gamble loss refunded"),
}


def scaled_bps(base_bps: int, max_bps: int, level: int, max_level: int) -> int:
    """Apply one upgrade per ten levels, with the final upgrade at the cap."""
    if level >= max_level:
        return max_bps
    steps = max(1, (max_level + 9) // 10)
    return base_bps + max(0, max_bps - base_bps) * (max(0, level) // 10) // steps
