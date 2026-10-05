from dataclasses import dataclass


@dataclass(frozen=True)
class RaidBossNames:
    melee: str | tuple[str, ...] = "Ironclad Brute"
    ranged: str | tuple[str, ...] = "Storm Archer"
    magic: str | tuple[str, ...] = "Arcane Tyrant"

    def choices_for(self, boss_type: str) -> tuple[str, ...]:
        names = getattr(self, boss_type)
        return (names,) if isinstance(names, str) else names


@dataclass(frozen=True)
class RaidWeaponNames:
    basic_sword: str = "Basic Sword"
    refined_sword: str = "Refined Sword"
    masterwork_sword: str = "Masterwork Sword"
    mythical_blade: str = "Mythical Blade"
    basic_bow: str = "Basic Bow"
    refined_bow: str = "Refined Bow"
    masterwork_bow: str = "Masterwork Bow"
    mythical_longbow: str = "Mythical Longbow"
    apprentice_tome: str = "Apprentice Tome"
    enchanted_tome: str = "Enchanted Tome"
    archmage_grimoire: str = "Archmage's Grimoire"
    mythical_grimoire: str = "Mythical Grimoire"
    overclocked_sword: str = "Overclocked Sword"
    overclocked_bow: str = "Overclocked Bow"
    overclocked_tome: str = "Overclocked Tome"
    heavens_judgement: str = "Heaven's Judgement"
    fools_dagger: str = "The Fool's Dagger"
    obsidian_brutalizer: str = "Obsidian Brutalizer"
    forgotten_daggers: str = "Forgotten Daggers of the Faithless"
    branch_of_yggdrasil: str = "Branch of Yggdrasil"

    def display(self, item_id: str) -> str:
        return str(getattr(self, item_id, item_id.replace("_", " ").title()))


@dataclass(frozen=True)
class RaidItemNames:
    potion: str = "Power Potion"
    second_wind: str = "Second Wind"
    berserk: str = "Berserk"
    lucky_dice: str = "Lucky Dice"
    fools_card: str = "The Fool's Card"
    blessing: str = "Blessing of the Gods"
    ancient_pact: str = "Ancient Pact"
    flag_bearer: str = "Flag Bearer's Will"

    def display(self, item_id: str) -> str:
        return str(getattr(self, item_id, item_id.replace("_", " ").title()))


@dataclass(frozen=True)
class RaidBossConfig:
    enabled: bool = False
    offline_testing_enabled: bool = False
    tutorial_name: str = "Training Dummy"
    names: RaidBossNames = RaidBossNames()
    mini_names: RaidBossNames = RaidBossNames()
    weapon_names: RaidWeaponNames = RaidWeaponNames()
    item_names: RaidItemNames = RaidItemNames()
    max_hp: int = 150000
    duration_streams: int = 5
    reward_pool: int = 100000
    final_hit_reward: int = 2500
    mini_duration_streams: int = 3
    mini_reward_pool: int = 25000
    mini_final_hit_reward: int = 1000
    base_damage_min: int = 390
    base_damage_max: int = 430
    weapon_cost: int = 25000
    overclocked_weapon_cost: int = 100000
    potion_cost: int = 1500
    lucky_dice_cost: int = 1000
    fools_card_cost: int = 500
    lucky_dice_floor_multiplier: float = 0.5
    lucky_dice_ceiling_multiplier: float = 2.0
    fools_card_points_min: int = -500
    fools_card_points_max: int = 1500
    weapon_attack: int = 40
    refined_weapon_attack: int = 80
    masterwork_weapon_attack: int = 150
    overclocked_weapon_attack: int = 150
    refined_crafting_cost: int = 5000
    masterwork_crafting_cost: int = 25000
    weapon_durability: int = 15
    repair_cost: int = 1500
    overclocked_weapon_durability: int = 25
    overclocked_repair_cost: int = 2500
    overdrive_chance: float = 0.50
    blessed_unique_drop_chance: float = 0.01
    blessed_unique_durability: int = 35
    blessed_unique_repair_cost: int = 5000
    heavens_judgement_attack: int = 200
    fools_dagger_attack: int = 80
    fools_dagger_critical_bonus: float = 0.50
    fools_dagger_points_min: float = 0.10
    fools_dagger_points_max: float = 0.50
    obsidian_brutalizer_attack: int = 150
    obsidian_brutalizer_stack_damage: int = 25
    forgotten_daggers_attack: int = 50
    forgotten_daggers_max_hp_damage: float = 0.0025
    branch_of_yggdrasil_attack: int = 100
    branch_of_yggdrasil_chatter_damage: int = 2
    branch_of_yggdrasil_chatter_cap: int = 200
    weapon_multiplier: float = 2.0
    all_weapon_multiplier: float = 1.5
    potion_multiplier: float = 2.0
    potion_attacks: int = 3
    critical_chance: float = 0.05
    critical_multiplier: float = 1.5
    tutorial_hp: int = 10000
    tutorial_duration_streams: int = 2
    tutorial_complete_collection_points: int = 5000
    reward_points_per_hp: float = 1.0
    final_hit_unique_drop_chance: float = 0.03
    top_contributor_unique_drop_chance: float = 0.03
    top_contributor_percent: float = 0.10
    basic_weapon_drop_chance: float = 0.05
    unique_weapon_attack: int = 225
    second_wind_cost: int = 1000
    berserk_cost: int = 3000
    blessing_cost: int = 500
    ancient_pact_cost: int = 750
    ancient_pact_ceiling_bonus: int = 200
    flag_bearer_cost: int = 5000
    flag_bearer_multiplier: float = 1.30
    flag_bearer_charges: int = 10
    berserk_multiplier: float = 5.0
    berserk_durability_cost: int = 5
    berserk_shatter_chance: float = 0.10
    blessing_multiplier: float = 1.25
    tutorial_enabled: bool = True
    automatic_spawning_enabled: bool = True
    main_boss_chance_after_three_minis: float = 0.25
    main_boss_chance_after_four_minis: float = 0.50
    main_boss_guaranteed_after_minis: int = 5
