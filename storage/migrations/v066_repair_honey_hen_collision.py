"""Recover Honey Hen when the development raid migration occupied version 64."""

from storage.migrations.v064_honey_hen import migrate as migrate_honey_hen


async def migrate(connection) -> None:
    # Direct schema bootstraps have no recorded version collision to repair.
    history_exists = await connection.fetchone(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    )
    if not history_exists:
        return
    collision = await connection.fetchone(
        "SELECT 1 FROM schema_migrations WHERE version = 64 AND name = ?",
        ("incoming_raid_recency",),
    )
    if not collision:
        return
    existing = await connection.fetchone(
        "SELECT 1 FROM pet_definitions WHERE id = ?", ("honey_hen",)
    )
    if not existing:
        await migrate_honey_hen(connection)
