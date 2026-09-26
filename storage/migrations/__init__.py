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
from storage.migrations.v022_seed_crafting_patch_note import migrate as migrate_seed_crafting_patch_note
from storage.migrations.v023_gambling_loss_totals import migrate as migrate_gambling_loss_totals
from storage.migrations.v024_raid_gamble_consumables import migrate as migrate_raid_gamble_consumables
from storage.migrations.v025_ancient_pact import migrate as migrate_ancient_pact
from storage.migrations.v026_flag_bearers_will import migrate as migrate_flag_bearers_will
from storage.migrations.v027_overclocked_weapons import migrate as migrate_overclocked_weapons
from storage.migrations.v028_point_reward_events import migrate as migrate_point_reward_events
from storage.migrations.v029_achievements import migrate as migrate_achievements
from storage.migrations.v030_chat_achievements import migrate as migrate_chat_achievements
from storage.migrations.v031_raid_achievements import migrate as migrate_raid_achievements
from storage.migrations.v032_global_blessed_achievements import migrate as migrate_global_blessed_achievements
from storage.migrations.v033_channel_achievements import migrate as migrate_channel_achievements
from storage.migrations.v034_secret_command_achievements import migrate as migrate_secret_command_achievements
from storage.migrations.v035_community_achievements import migrate as migrate_community_achievements
from storage.migrations.v036_raid_progress_checkpoints import migrate as migrate_raid_progress_checkpoints
from storage.migrations.v037_chatter_profile_images import migrate as migrate_chatter_profile_images
from storage.migrations.v038_live_command_roll_limits import migrate as migrate_live_command_roll_limits
from storage.migrations.v039_command_slowmode import migrate as migrate_command_slowmode
from storage.migrations.v040_youtube_chat import migrate as migrate_youtube_chat
from storage.migrations.v041_viewer_queue_blacklist import migrate as migrate_viewer_queue_blacklist
from storage.migrations.v042_viewer_queue_display_names import migrate as migrate_viewer_queue_display_names
from storage.migrations.v043_pinned_chat_messages import migrate as migrate_pinned_chat_messages
from storage.migrations.v044_channel_protected_users import migrate as migrate_channel_protected_users
from storage.migrations.v045_unpublish_test_patch_note import migrate as migrate_unpublish_test_patch_note
from storage.migrations.v046_channel_quotes import migrate as migrate_channel_quotes
from storage.migrations.v047_compact_channel_quotes import migrate as migrate_compact_channel_quotes
from storage.migrations.v048_global_pets import migrate as migrate_global_pets
from storage.migrations.v049_pet_asset_path import migrate as migrate_pet_asset_path
from storage.migrations.v050_viewer_sessions import migrate as migrate_viewer_sessions

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
    , Migration(version=22, name="seed_crafting_patch_note", run=migrate_seed_crafting_patch_note)
    , Migration(version=23, name="gambling_loss_totals", run=migrate_gambling_loss_totals)
    , Migration(version=24, name="raid_gamble_consumables", run=migrate_raid_gamble_consumables)
    , Migration(version=25, name="ancient_pact", run=migrate_ancient_pact)
    , Migration(version=26, name="flag_bearers_will", run=migrate_flag_bearers_will)
    , Migration(version=27, name="overclocked_weapons", run=migrate_overclocked_weapons)
    , Migration(version=28, name="point_reward_events", run=migrate_point_reward_events)
    , Migration(version=29, name="achievements", run=migrate_achievements)
    , Migration(version=30, name="chat_achievements", run=migrate_chat_achievements)
    , Migration(version=31, name="raid_achievements", run=migrate_raid_achievements)
    , Migration(version=32, name="global_blessed_achievements", run=migrate_global_blessed_achievements)
    , Migration(version=33, name="channel_achievements", run=migrate_channel_achievements)
    , Migration(version=34, name="secret_command_achievements", run=migrate_secret_command_achievements)
    , Migration(version=35, name="community_achievements", run=migrate_community_achievements)
    , Migration(version=36, name="raid_progress_checkpoints", run=migrate_raid_progress_checkpoints)
    , Migration(version=37, name="chatter_profile_images", run=migrate_chatter_profile_images)
    , Migration(version=38, name="live_command_roll_limits", run=migrate_live_command_roll_limits)
    , Migration(version=39, name="command_slowmode", run=migrate_command_slowmode)
    , Migration(version=40, name="youtube_chat", run=migrate_youtube_chat)
    , Migration(version=41, name="viewer_queue_blacklist", run=migrate_viewer_queue_blacklist)
    , Migration(version=42, name="viewer_queue_display_names", run=migrate_viewer_queue_display_names)
    , Migration(version=43, name="pinned_chat_messages", run=migrate_pinned_chat_messages)
    , Migration(version=44, name="channel_protected_users", run=migrate_channel_protected_users)
    , Migration(version=45, name="unpublish_test_patch_note", run=migrate_unpublish_test_patch_note)
    , Migration(version=46, name="channel_quotes", run=migrate_channel_quotes)
    , Migration(version=47, name="compact_channel_quotes", run=migrate_compact_channel_quotes)
    , Migration(version=48, name="global_pets", run=migrate_global_pets)
    , Migration(version=49, name="pet_asset_path", run=migrate_pet_asset_path)
    , Migration(version=50, name="viewer_sessions", run=migrate_viewer_sessions)
)
