from storage.migrations.v001_initial_schema import (
    migrate as migrate_initial_schema
)
from storage.migrations.v002_redeem_stats import (
    migrate as migrate_redeem_stats
)

MIGRATIONS = [
    (
        1,
        "initial_schema",
        migrate_initial_schema
    ),
    (
        2,
        "redeem_stats",
        migrate_redeem_stats
    )
]