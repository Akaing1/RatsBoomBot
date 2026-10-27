"""Reward pool rules shared by Boss Hunt resolution."""


def minimum_main_boss_pool(tier: str, defeated: bool, damage: int, max_hp: int, earned: int) -> int:
    if not defeated and tier == "main" and 0 < damage * 4 < max_hp:
        return max(earned, round(max_hp * 0.10))
    return earned
