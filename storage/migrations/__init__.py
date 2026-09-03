from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from storage.migrations.v001_initial_schema import migrate as migrate_initial_schema
from storage.migrations.v002_redeem_stats import migrate as migrate_redeem_stats
from storage.migrations.v003_administrators import migrate as migrate_administrators
from storage.migrations.v004_imported_redeem_totals import migrate as migrate_imported_redeem_totals
from storage.migrations.v005_redemption_activity import migrate as migrate_redemption_activity
from storage.migrations.v006_second_redeem import migrate as migrate_second_redeem
from storage.migrations.v007_first_chat_shoutouts import migrate as migrate_first_chat_shoutouts
from storage.migrations.v008_chatter_identities import migrate as migrate_chatter_identities
from storage.migrations.v009_reklop_counter_700 import migrate as migrate_reklop_counter_700
from storage.migrations.v010_viewer_queue_persistence import migrate as migrate_viewer_queue_persistence
from storage.migrations.v011_raid_boss_persistence import migrate as migrate_raid_boss_persistence
from storage.migrations.v012_custom_bot_identities import migrate as migrate_custom_bot_identities
from storage.migrations.v013_chatter_profiles import migrate as migrate_chatter_profiles
from storage.migrations.v014_remove_test_raid_records import migrate as migrate_remove_test_raid_records
from storage.migrations.v015_passive_point_payouts import migrate as migrate_passive_point_payouts
from storage.migrations.v016_remove_remaining_ahirman_test_record import migrate as migrate_remove_remaining_ahirman_test_record
from storage.migrations.v017_remove_ahirman_test_run import migrate as migrate_remove_ahirman_test_run
from storage.migrations.v018_remove_ahriman_test_run import migrate as migrate_remove_ahriman_test_run
from storage.migrations.v019_custom_bot_authorization_links import migrate as migrate_custom_bot_authorization_links
from storage.migrations.v020_raid_crafting_progression import migrate as migrate_raid_crafting_progression
from storage.migrations.v021_patch_notes import migrate as migrate_patch_notes

MigrationFunction = Callable[[Any], Awaitable[None]]


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    run: MigrationFunction


MIGRATIONS: tuple[Migration, ...] = (
    Migration(version=1, name="initial_schema", run=migrate_initial_schema),
    Migration(version=2, name="redeem_stats", run=migrate_redeem_stats),
    Migration(version=3, name="administrators", run=migrate_administrators),
    Migration(version=4, name="imported_redeem_totals", run=migrate_imported_redeem_totals),
    Migration(version=5, name="redemption_activity", run=migrate_redemption_activity),
    Migration(version=6, name="second_redeem", run=migrate_second_redeem),
    Migration(version=7, name="first_chat_shoutouts", run=migrate_first_chat_shoutouts),
    Migration(version=8, name="chatter_identities", run=migrate_chatter_identities),
    Migration(version=9, name="reklop_counter_700", run=migrate_reklop_counter_700),
    Migration(version=10, name="viewer_queue_persistence", run=migrate_viewer_queue_persistence),
    Migration(version=11, name="raid_boss_persistence", run=migrate_raid_boss_persistence),
    Migration(version=12, name="custom_bot_identities", run=migrate_custom_bot_identities),
    Migration(version=13, name="chatter_profiles", run=migrate_chatter_profiles),
    Migration(version=14, name="remove_test_raid_records", run=migrate_remove_test_raid_records),
    Migration(version=15, name="passive_point_payouts", run=migrate_passive_point_payouts),
    Migration(version=16, name="remove_remaining_ahirman_test_record", run=migrate_remove_remaining_ahirman_test_record),
    Migration(version=17, name="remove_ahirman_test_run", run=migrate_remove_ahirman_test_run),
    Migration(version=18, name="remove_ahriman_test_run", run=migrate_remove_ahriman_test_run),
    Migration(version=19, name="custom_bot_authorization_links", run=migrate_custom_bot_authorization_links),
    Migration(version=20, name="raid_crafting_progression", run=migrate_raid_crafting_progression)
    , Migration(version=21, name="patch_notes", run=migrate_patch_notes)
)
