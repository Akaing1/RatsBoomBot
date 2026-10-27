import logging
from time import perf_counter
from typing import Any

import asqlite

from storage.migrations import MIGRATIONS, Migration, validate_migrations

LOGGER = logging.getLogger("RatBoomBot")


async def create_migration_table(connection: Any) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


async def get_applied_versions(connection: Any) -> set[int]:
    rows = await connection.fetchall(
        """
        SELECT version
        FROM schema_migrations
        ORDER BY version
        """
    )

    return {int(row["version"]) for row in rows}


async def record_migration(connection: Any, migration: Migration) -> None:
    await connection.execute(
        """
        INSERT INTO schema_migrations (version, name)
        VALUES (?, ?)
        """,
        (migration.version, migration.name)
    )


async def run_migration(connection: Any, migration: Migration, *, superseded_name: str | None = None) -> None:
    started_at = perf_counter()

    LOGGER.info(
        "[Database] Applying migration %s: %s.",
        migration.version,
        migration.name
    )

    await connection.execute("BEGIN")

    try:
        if superseded_name is not None:
            await connection.execute('DELETE FROM schema_migrations WHERE version = ? AND name = ?',
                (migration.version, superseded_name))
        await migration.run(connection)
        await record_migration(connection, migration)
        await connection.commit()
    except BaseException:
        await connection.rollback()

        LOGGER.exception(
            "[Database] Migration %s failed and was rolled back: %s.",
            migration.version,
            migration.name
        )
        raise

    LOGGER.info(
        "[Database] Applied migration %s in %.3f seconds: %s.",
        migration.version,
        perf_counter() - started_at,
        migration.name
    )


async def run_migrations(db: asqlite.Pool) -> None:
    validate_migrations(MIGRATIONS)
    started_at = perf_counter()

    LOGGER.debug("[Database] Ensuring the migration history table exists.")

    async with db.acquire() as connection:
        await create_migration_table(connection)
        await connection.commit()

        history = await connection.fetchall(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        )
        registered = {migration.version: migration for migration in MIGRATIONS}
        superseded = {}
        for expected_version, row in enumerate(history, start=1):
            version, name = int(row["version"]), row["name"]
            migration = registered.get(version)
            if migration is None:
                raise ValueError(f"Database migration {version} is unknown to this application; use a compatible release.")
            if version != expected_version:
                raise ValueError(f"Database migration history is missing version {expected_version}; restore or repair it before upgrading.")
            # A shipped development collision is repaired by migration 66;
            # its original history row intentionally remains unchanged.
            known_collision = (
                version == 64
                and migration.name == "honey_hen"
                and name == "incoming_raid_recency"
            )
            # The Followers branch used 71 before merging the channel-access release.
            # Reapply the real 71 transactionally; the existing index is retained by 75.
            follower_collision = (
                version == 71 and version == len(history)
                and name == 'follower_last_watched_index' and migration.name == 'channel_access'
                and registered.get(75) is not None and registered[75].name == 'follower_last_watched_index'
            )
            if follower_collision:
                superseded[version] = name
            if name != migration.name and not known_collision and not follower_collision:
                raise ValueError(f"Database migration {version} is named {name!r}, expected {migration.name!r}.")
        applied_versions = {int(row["version"]) for row in history}
        pending_migrations = [migration for migration in MIGRATIONS if migration.version not in applied_versions or migration.version in superseded]

        LOGGER.info(
            "[Database] Found %d registered migrations: %d applied, %d pending.",
            len(MIGRATIONS),
            len(applied_versions),
            len(pending_migrations)
        )

        for migration in pending_migrations:
            await run_migration(connection, migration, superseded_name=superseded.get(migration.version))

    if not pending_migrations:
        LOGGER.info("[Database] Database migrations are up to date.")
        return

    LOGGER.info(
        "[Database] Applied %d pending migrations in %.3f seconds.",
        len(pending_migrations),
        perf_counter() - started_at
    )
