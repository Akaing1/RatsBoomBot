"""Historical migrations owned by core."""

from storage.migrations.model import Migration

from .v001_initial_schema import migrate as migrate_001
from .v002_redeem_stats import migrate as migrate_002
from .v003_administrators import migrate as migrate_003
from .v004_imported_redeem_totals import migrate as migrate_004
from .v005_redemption_activity import migrate as migrate_005
from .v006_second_redeem import migrate as migrate_006
from .v007_first_chat_shoutouts import migrate as migrate_007
from .v008_chatter_identities import migrate as migrate_008
from .v009_reklop_counter_700 import migrate as migrate_009
from .v010_viewer_queue_persistence import migrate as migrate_010
from .v012_custom_bot_identities import migrate as migrate_012
from .v013_chatter_profiles import migrate as migrate_013
from .v019_custom_bot_authorization_links import migrate as migrate_019
from .v021_patch_notes import migrate as migrate_021
from .v022_seed_crafting_patch_note import migrate as migrate_022
from .v037_chatter_profile_images import migrate as migrate_037
from .v038_live_command_roll_limits import migrate as migrate_038
from .v039_command_slowmode import migrate as migrate_039
from .v040_youtube_chat import migrate as migrate_040
from .v041_viewer_queue_blacklist import migrate as migrate_041
from .v042_viewer_queue_display_names import migrate as migrate_042
from .v043_pinned_chat_messages import migrate as migrate_043
from .v044_channel_protected_users import migrate as migrate_044
from .v045_unpublish_test_patch_note import migrate as migrate_045
from .v046_channel_quotes import migrate as migrate_046
from .v047_compact_channel_quotes import migrate as migrate_047
from .v050_viewer_sessions import migrate as migrate_050
from .v065_incoming_raid_recency import migrate as migrate_065
from .v067_follow_raid import migrate as migrate_067


from .v068_streamer_workspace import migrate as migrate_068

MIGRATIONS = (
    Migration(1, "initial_schema", migrate_001),
    Migration(2, "redeem_stats", migrate_002),
    Migration(3, "administrators", migrate_003),
    Migration(4, "imported_redeem_totals", migrate_004),
    Migration(5, "redemption_activity", migrate_005),
    Migration(6, "second_redeem", migrate_006),
    Migration(7, "first_chat_shoutouts", migrate_007),
    Migration(8, "chatter_identities", migrate_008),
    Migration(9, "reklop_counter_700", migrate_009),
    Migration(10, "viewer_queue_persistence", migrate_010),
    Migration(12, "custom_bot_identities", migrate_012),
    Migration(13, "chatter_profiles", migrate_013),
    Migration(19, "custom_bot_authorization_links", migrate_019),
    Migration(21, "patch_notes", migrate_021),
    Migration(22, "seed_crafting_patch_note", migrate_022),
    Migration(37, "chatter_profile_images", migrate_037),
    Migration(38, "live_command_roll_limits", migrate_038),
    Migration(39, "command_slowmode", migrate_039),
    Migration(40, "youtube_chat", migrate_040),
    Migration(41, "viewer_queue_blacklist", migrate_041),
    Migration(42, "viewer_queue_display_names", migrate_042),
    Migration(43, "pinned_chat_messages", migrate_043),
    Migration(44, "channel_protected_users", migrate_044),
    Migration(45, "unpublish_test_patch_note", migrate_045),
    Migration(46, "channel_quotes", migrate_046),
    Migration(47, "compact_channel_quotes", migrate_047),
    Migration(50, "viewer_sessions", migrate_050),
    Migration(65, "incoming_raid_recency", migrate_065),
    Migration(67, "follow_raid", migrate_067),
    Migration(68, "streamer_workspace", migrate_068),
)
