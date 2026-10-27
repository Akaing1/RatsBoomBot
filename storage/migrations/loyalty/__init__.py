"""Historical migrations owned by loyalty."""

from storage.migrations.model import Migration

from .v015_passive_point_payouts import migrate as migrate_015
from .v023_gambling_loss_totals import migrate as migrate_023
from .v028_point_reward_events import migrate as migrate_028
from .v051_gamble_outcomes import migrate as migrate_051
from .v071_follower_last_watched_index import migrate as migrate_071


MIGRATIONS = (
    Migration(15, "passive_point_payouts", migrate_015),
    Migration(23, "gambling_loss_totals", migrate_023),
    Migration(28, "point_reward_events", migrate_028),
    Migration(51, "gamble_outcomes", migrate_051),
    Migration(71, "follower_last_watched_index", migrate_071),
)
