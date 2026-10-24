"""One globally ordered migration history, organized by feature ownership."""

from storage.migrations import achievements, boss_hunts, core, loyalty, pets
from storage.migrations.model import Migration, MigrationFunction, validate_migrations

MIGRATION_GROUPS = (core, loyalty, achievements, boss_hunts, pets)
MIGRATIONS: tuple[Migration, ...] = tuple(sorted(
    (migration for group in MIGRATION_GROUPS for migration in group.MIGRATIONS),
    key=lambda migration: migration.version,
))
validate_migrations(MIGRATIONS)

__all__ = ["MIGRATIONS", "Migration", "MigrationFunction", "validate_migrations"]
