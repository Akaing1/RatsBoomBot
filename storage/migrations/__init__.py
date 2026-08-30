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
    Migration(version=10, name="viewer_queue_persistence", run=migrate_viewer_queue_persistence)
)
