import logging
from dataclasses import dataclass

import asqlite


LOGGER = logging.getLogger("RatBoomBot")


@dataclass(frozen=True)
class Administrator:
    id: int
    username: str
    password_hash: str
    role: str
    is_enabled: bool
    created_at: str


def administrator_from_row(row) -> Administrator:
    return Administrator(
        id=int(row["id"]),
        username=str(row["username"]),
        password_hash=str(row["password_hash"]),
        role=str(row["role"]),
        is_enabled=bool(row["is_enabled"]),
        created_at=str(row["created_at"])
    )


async def get_administrator_by_username(db: asqlite.Pool, username: str) -> Administrator | None:
    query = """
    SELECT id, username, password_hash, role, is_enabled, created_at
    FROM administrators
    WHERE username = ?
    """

    LOGGER.debug(
        "[Administrators] Loading administrator account %s.",
        username
    )

    async with db.acquire() as connection:
        row = await connection.fetchone(query, (username,))

    if row is None:
        return None

    return administrator_from_row(row)


async def get_administrator_by_id(db: asqlite.Pool, administrator_id: int) -> Administrator | None:
    query = """
    SELECT id, username, password_hash, role, is_enabled, created_at
    FROM administrators
    WHERE id = ?
    """

    LOGGER.debug(
        "[Administrators] Loading administrator account %s.",
        administrator_id
    )

    async with db.acquire() as connection:
        row = await connection.fetchone(query, (administrator_id,))

    if row is None:
        return None

    return administrator_from_row(row)


async def list_administrators(db: asqlite.Pool) -> list[Administrator]:
    query = """
    SELECT id, username, password_hash, role, is_enabled, created_at
    FROM administrators
    ORDER BY
        CASE role
            WHEN 'owner' THEN 0
            ELSE 1
        END,
        username
    """

    LOGGER.debug("[Administrators] Loading administrator accounts.")

    async with db.acquire() as connection:
        rows = await connection.fetchall(query)

    administrators = [administrator_from_row(row) for row in rows]

    LOGGER.debug(
        "[Administrators] Loaded %d administrator accounts.",
        len(administrators)
    )

    return administrators


async def create_administrator(db: asqlite.Pool, username: str, password_hash: str, role: str = "admin") -> Administrator:
    query = """
    INSERT INTO administrators (username, password_hash, role)
    VALUES (?, ?, ?)
    """

    LOGGER.info(
        "[Administrators] Creating %s account %s.",
        role,
        username
    )

    async with db.acquire() as connection:
        await connection.execute(query, (username, password_hash, role))

    administrator = await get_administrator_by_username(db, username)

    if administrator is None:
        raise RuntimeError(f"Administrator account {username} could not be loaded after creation.")

    LOGGER.info(
        "[Administrators] Created account %s with ID %s.",
        username,
        administrator.id
    )

    return administrator


async def set_administrator_enabled(db: asqlite.Pool, administrator_id: int, is_enabled: bool) -> None:
    query = """
    UPDATE administrators
    SET is_enabled = ?
    WHERE id = ?
    """

    LOGGER.info(
        "[Administrators] Setting administrator %s enabled=%s.",
        administrator_id,
        is_enabled
    )

    async with db.acquire() as connection:
        await connection.execute(query, (int(is_enabled), administrator_id))

    LOGGER.info(
        "[Administrators] Updated administrator %s.",
        administrator_id
    )
