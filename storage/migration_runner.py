import logging
from time import perf_counter
from typing import Any

import asqlite

from storage.migrations import MIGRATIONS, Migration

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


async def run_migration(connection: Any, migration: Migration) -> None:
    started_at = perf_counter()

    LOGGER.info(
        "[Database] Applying migration %s: %s.",
        migration.version,
        migration.name
    )

    await connection.execute("BEGIN")

    try:
        await migration.run(connection)
        await record_migration(connection, migration)
        await connection.commit()
    except Exception:
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
    started_at = perf_counter()

    LOGGER.debug("[Database] Ensuring the migration history table exists.")

    async with db.acquire() as connection:
        await create_migration_table(connection)
        await connection.commit()

        applied_versions = await get_applied_versions(connection)
        pending_migrations = [migration for migration in MIGRATIONS if migration.version not in applied_versions]

        LOGGER.info(
            "[Database] Found %d registered migrations: %d applied, %d pending.",
            len(MIGRATIONS),
            len(applied_versions),
            len(pending_migrations)
        )

        for migration in pending_migrations:
            await run_migration(connection, migration)

    if not pending_migrations:
        LOGGER.info("[Database] Database migrations are up to date.")
        return

    LOGGER.info(
        "[Database] Applied %d pending migrations in %.3f seconds.",
        len(pending_migrations),
        perf_counter() - started_at
    )
