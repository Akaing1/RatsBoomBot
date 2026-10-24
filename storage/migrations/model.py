"""Migration contracts and validation shared by the registry and runner."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

MigrationFunction = Callable[[Any], Awaitable[None]]


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    run: MigrationFunction


def validate_migrations(migrations: Sequence[Migration]) -> None:
    """Require a complete, unique, ordered history before touching the database."""
    for expected_version, migration in enumerate(migrations, start=1):
        if migration.version != expected_version:
            raise ValueError(
                f"Expected migration {expected_version}, got {migration.version} "
                f"({migration.name}); check duplicate, missing, or unordered versions."
            )
        if not migration.name or not callable(migration.run):
            raise ValueError(f"Invalid migration registration: {migration.version}")
