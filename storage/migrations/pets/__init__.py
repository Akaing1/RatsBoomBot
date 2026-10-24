"""Historical migrations owned by pets."""

from storage.migrations.model import Migration

from .v048_global_pets import migrate as migrate_048
from .v049_pet_asset_path import migrate as migrate_049
from .v052_pet_passive_tiers import migrate as migrate_052
from .v053_repair_explosive_rat_seed import migrate as migrate_053
from .v054_pet_display_names import migrate as migrate_054
from .v055_sleepy_fox import migrate as migrate_055
from .v056_pet_summons import migrate as migrate_056
from .v057_common_pet_catalog import migrate as migrate_057
from .v058_fixed_pet_passives import migrate as migrate_058
from .v059_horned_wolf import migrate as migrate_059
from .v060_royal_raven import migrate as migrate_060
from .v062_witch_cat import migrate as migrate_062
from .v063_dog_of_the_sun import migrate as migrate_063
from .v064_honey_hen import migrate as migrate_064
from .v066_repair_honey_hen_collision import migrate as migrate_066


MIGRATIONS = (
    Migration(48, "global_pets", migrate_048),
    Migration(49, "pet_asset_path", migrate_049),
    Migration(52, "pet_passive_tiers", migrate_052),
    Migration(53, "repair_explosive_rat_seed", migrate_053),
    Migration(54, "pet_display_names", migrate_054),
    Migration(55, "sleepy_fox", migrate_055),
    Migration(56, "pet_summons", migrate_056),
    Migration(57, "common_pet_catalog", migrate_057),
    Migration(58, "fixed_pet_passives", migrate_058),
    Migration(59, "horned_wolf", migrate_059),
    Migration(60, "royal_raven", migrate_060),
    Migration(62, "witch_cat", migrate_062),
    Migration(63, "dog_of_the_sun", migrate_063),
    Migration(64, "honey_hen", migrate_064),
    Migration(66, "repair_honey_hen_collision", migrate_066),
)
