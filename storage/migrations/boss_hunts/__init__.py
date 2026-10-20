"""Historical migrations owned by boss hunts."""

from storage.migrations.model import Migration

from .v011_raid_boss_persistence import migrate as migrate_011
from .v014_remove_test_raid_records import migrate as migrate_014
from .v016_remove_remaining_ahirman_test_record import migrate as migrate_016
from .v017_remove_ahirman_test_run import migrate as migrate_017
from .v018_remove_ahriman_test_run import migrate as migrate_018
from .v020_raid_crafting_progression import migrate as migrate_020
from .v024_raid_gamble_consumables import migrate as migrate_024
from .v025_ancient_pact import migrate as migrate_025
from .v026_flag_bearers_will import migrate as migrate_026
from .v027_overclocked_weapons import migrate as migrate_027
from .v036_raid_progress_checkpoints import migrate as migrate_036
from .v061_adaptive_mini_bosses import migrate as migrate_061


MIGRATIONS = (
    Migration(11, "raid_boss_persistence", migrate_011),
    Migration(14, "remove_test_raid_records", migrate_014),
    Migration(16, "remove_remaining_ahirman_test_record", migrate_016),
    Migration(17, "remove_ahirman_test_run", migrate_017),
    Migration(18, "remove_ahriman_test_run", migrate_018),
    Migration(20, "raid_crafting_progression", migrate_020),
    Migration(24, "raid_gamble_consumables", migrate_024),
    Migration(25, "ancient_pact", migrate_025),
    Migration(26, "flag_bearers_will", migrate_026),
    Migration(27, "overclocked_weapons", migrate_027),
    Migration(36, "raid_progress_checkpoints", migrate_036),
    Migration(61, "adaptive_mini_bosses", migrate_061),
)
