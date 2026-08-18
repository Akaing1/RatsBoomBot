import asyncio
from getpass import getpass
from pathlib import Path

import asqlite

from config.settings import settings
from storage.admin_repository import create_administrator, get_administrator_by_username, list_administrators
from storage.migration_runner import run_migrations
from web.shared.passwords import hash_password


MINIMUM_PASSWORD_LENGTH = 12


async def create_owner() -> None:
    database_path = Path(settings.DATABASE_PATH)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    async with asqlite.create_pool(str(database_path)) as database:
        await run_migrations(database)

        administrators = await list_administrators(database)

        if any(administrator.role == "owner" for administrator in administrators):
            print("An owner account already exists.")
            return

        username = input("Owner username: ").strip().lower()

        if not username:
            print("Username cannot be empty.")
            return

        existing_administrator = await get_administrator_by_username(database, username)

        if existing_administrator is not None:
            print(f"Administrator account '{username}' already exists.")
            return

        password = getpass("Owner password: ")
        confirmed_password = getpass("Confirm owner password: ")

        if password != confirmed_password:
            print("Passwords do not match.")
            return

        if len(password) < MINIMUM_PASSWORD_LENGTH:
            print(f"Password must be at least {MINIMUM_PASSWORD_LENGTH} characters.")
            return

        password_hash = hash_password(password)
        administrator = await create_administrator(database, username, password_hash, role="owner")

        print(f"Owner account '{administrator.username}' created successfully.")


def main() -> None:
    asyncio.run(create_owner())


if __name__ == "__main__":
    main()
