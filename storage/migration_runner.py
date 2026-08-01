import logging
from typing import Any

import asqlite

from storage.migrations import MIGRATIONS, Migration

LOGGER = logging.getLogger("Bot")


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
    LOGGER.info("Applying database migration %s: %s", migration.version, migration.name)

    await connection.execute("BEGIN")

    try:
        await migration.run(connection)
        await record_migration(connection, migration)
        await connection.commit()
    except Exception:
        await connection.rollback()
        LOGGER.exception("Database migration %s failed: %s", migration.version, migration.name)
        raise

    LOGGER.info("Applied database migration %s: %s", migration.version, migration.name)


async def run_migrations(db: asqlite.Pool) -> None:
    async with db.acquire() as connection:
        await create_migration_table(connection)
        await connection.commit()

        applied_versions = await get_applied_versions(connection)

        for migration in MIGRATIONS:
            if migration.version in applied_versions:
                continue

            await run_migration(connection, migration)

    LOGGER.info("Database migrations are up to date.")