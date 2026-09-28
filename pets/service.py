from dataclasses import dataclass
from typing import Any


LOYALTY_GAIN_PASSIVE = "loyalty_gain"
POC_BAT_ID = "dungeon_bat"
POC_LOYALTY_BONUS_BPS = 1_000


@dataclass(frozen=True)
class EquippedPet:
    user_pet_id: int
    pet_id: str
    display_name: str
    rarity: str
    sprite_path: str
    frame_count: int
    level: int
    xp: int
    max_level: int
    passive_type: str
    passive_value_bps: int

    @property
    def passive_percent(self) -> float:
        return self.passive_value_bps / 100

    @property
    def passive_percent_label(self) -> str:
        return f"{self.passive_percent:g}"


class PetService:
    def __init__(self, db):
        self.db = db

    async def setup(self) -> None:
        # Pet storage is created and seeded by database migrations.
        return None

    async def get_equipped_pet(self, user_id: str, connection=None) -> EquippedPet | None:
        query = """
            SELECT owned.id AS user_pet_id, definitions.id AS pet_id,
                   definitions.display_name, definitions.rarity,
                   definitions.sprite_path, definitions.frame_count,
                   definitions.max_level, owned.level, owned.xp,
                   owned.passive_type, owned.passive_value_bps
            FROM user_pet_loadouts AS loadouts
            JOIN user_pets AS owned ON owned.id = loadouts.user_pet_id
            JOIN pet_definitions AS definitions ON definitions.id = owned.pet_id
            WHERE loadouts.user_id = ?
            LIMIT 1
        """

        if connection is not None:
            row = await connection.fetchone(query, (str(user_id),))
        else:
            async with self.db.acquire() as managed_connection:
                row = await managed_connection.fetchone(query, (str(user_id),))

        return self._from_row(row) if row is not None else None

    async def loyalty_bonus(self, user_id: str, base_amount: int, connection=None) -> int:
        if base_amount <= 0:
            return 0

        pet = await self.get_equipped_pet(user_id, connection)

        if pet is None or pet.passive_type != LOYALTY_GAIN_PASSIVE:
            return 0

        return (int(base_amount) * pet.passive_value_bps) // 10_000

    async def grant_poc_bat(self, user_id: str) -> EquippedPet:
        user_id = str(user_id)

        async with self.db.acquire() as connection:
            await connection.execute("BEGIN")

            try:
                await connection.execute(
                    """
                    INSERT OR IGNORE INTO user_pets (
                        user_id, pet_id, level, xp, passive_type, passive_value_bps
                    )
                    VALUES (?, ?, 1, 0, ?, ?)
                    """,
                    (user_id, POC_BAT_ID, LOYALTY_GAIN_PASSIVE, POC_LOYALTY_BONUS_BPS)
                )
                owned = await connection.fetchone(
                    "SELECT id FROM user_pets WHERE user_id = ? AND pet_id = ?",
                    (user_id, POC_BAT_ID)
                )
                await connection.execute(
                    """
                    INSERT INTO user_pet_loadouts (user_id, user_pet_id)
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        user_pet_id = excluded.user_pet_id,
                        equipped_at = CURRENT_TIMESTAMP
                    """,
                    (user_id, int(owned["id"]))
                )
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise

        pet = await self.get_equipped_pet(user_id)

        if pet is None:
            raise RuntimeError("The POC pet was granted but could not be loaded.")

        return pet

    @staticmethod
    def _from_row(row: Any) -> EquippedPet:
        return EquippedPet(
            user_pet_id=int(row["user_pet_id"]),
            pet_id=str(row["pet_id"]),
            display_name=str(row["display_name"]),
            rarity=str(row["rarity"]),
            sprite_path=str(row["sprite_path"]),
            frame_count=int(row["frame_count"]),
            level=int(row["level"]),
            xp=int(row["xp"]),
            max_level=int(row["max_level"]),
            passive_type=str(row["passive_type"]),
            passive_value_bps=int(row["passive_value_bps"])
        )
