import argparse
import asyncio
from pathlib import Path

import asqlite

from bot.services.engagement.pets import PetService
from config.settings import settings
from storage.migration_runner import run_migrations


async def grant_pet(chatter: str) -> None:
    database_path = Path(settings.DATABASE_PATH)
    normalized = chatter.strip().removeprefix("@").strip()

    async with asqlite.create_pool(str(database_path)) as database:
        await run_migrations(database)

        async with database.acquire() as connection:
            identity = await connection.fetchone(
                """
                SELECT user_id, display_name
                FROM chatter_identities
                WHERE user_id = ? OR login = ? COLLATE NOCASE OR display_name = ? COLLATE NOCASE
                LIMIT 1
                """,
                (normalized, normalized, normalized)
            )

        if identity is None:
            raise SystemExit(f"No chatter identity found for '{chatter}'.")

        pet = await PetService(database).grant_poc_bat(str(identity["user_id"]))
        print(
            f"Equipped {pet.display_name} for {identity['display_name']} "
            f"with +{pet.passive_percent:g}% loyalty gain."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Grant and equip the UAT proof-of-concept pet.")
    parser.add_argument("chatter", help="Twitch login, display name, or user ID")
    arguments = parser.parse_args()
    asyncio.run(grant_pet(arguments.chatter))


if __name__ == "__main__":
    main()

