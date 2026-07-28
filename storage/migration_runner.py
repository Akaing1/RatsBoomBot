import logging
from collections.abc import Awaitable, Callable

import asqlite

from storage.migrations import MIGRATIONS

LOGGER = logging.getLogger("Bot")

MigrationFunction = Callable[
    [asqlite.Connection],
    Awaitable[None]
]


async def create_migration_table(connection: asqlite.Connection) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


async def get_applied_versions(connection: asqlite.Connection) -> set[int]:
    rows = await connection.fetchall(
        """
        SELECT version
        FROM schema_migrations
        ORDER BY version
        """
    )

    return {
        int(row["version"])
        for row in rows
    }


async def record_migration(connection: asqlite.Connection, version: int, name: str) -> None:
    await connection.execute(
        """
        INSERT INTO schema_migrations (
            version,
            name
        )
        VALUES (?, ?)
        """,
        (
            version,
            name
        )
    )


async def run_migration(connection: asqlite.Connection, version: int, name: str, migration: MigrationFunction) -> None:
    LOGGER.info(
        "Applying database migration %s: %s",
        version,
        name
    )

    await connection.execute("BEGIN")

    try:
        await migration(connection)

        await record_migration(
            connection,
            version,
            name
        )

        await connection.commit()

    except Exception:
        await connection.rollback()

        LOGGER.exception(
            "Database migration %s failed: %s",
            version,
            name
        )

        raise

    LOGGER.info(
        "Applied database migration %s: %s",
        version,
        name
    )


async def run_migrations(db: asqlite.Pool) -> None:
    async with db.acquire() as connection:
        await create_migration_table(
            connection
        )

        await connection.commit()

        applied_versions = await get_applied_versions(
            connection
        )

        for version, name, migration in MIGRATIONS:
            if version in applied_versions:
                continue

            await run_migration(
                connection,
                version,
                name,
                migration
            )

    LOGGER.info(
        "Database migrations are up to date."
    )
