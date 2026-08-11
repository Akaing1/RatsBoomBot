from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from storage.migrations.v001_initial_schema import migrate as migrate_initial_schema
from storage.migrations.v002_redeem_stats import migrate as migrate_redeem_stats
from storage.migrations.v003_administrators import migrate as migrate_administrators

MigrationFunction = Callable[[Any], Awaitable[None]]


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    run: MigrationFunction


MIGRATIONS: tuple[Migration, ...] = (
    Migration(version=1, name="initial_schema", run=migrate_initial_schema),
    Migration(version=2, name="redeem_stats", run=migrate_redeem_stats),
    Migration(version=3, name="administrators", run=migrate_administrators)
)
