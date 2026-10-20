"""Historical migrations owned by achievements."""

from storage.migrations.model import Migration

from .v029_achievements import migrate as migrate_029
from .v030_chat_achievements import migrate as migrate_030
from .v031_raid_achievements import migrate as migrate_031
from .v032_global_blessed_achievements import migrate as migrate_032
from .v033_channel_achievements import migrate as migrate_033
from .v034_secret_command_achievements import migrate as migrate_034
from .v035_community_achievements import migrate as migrate_035


MIGRATIONS = (
    Migration(29, "achievements", migrate_029),
    Migration(30, "chat_achievements", migrate_030),
    Migration(31, "raid_achievements", migrate_031),
    Migration(32, "global_blessed_achievements", migrate_032),
    Migration(33, "channel_achievements", migrate_033),
    Migration(34, "secret_command_achievements", migrate_034),
    Migration(35, "community_achievements", migrate_035),
)
