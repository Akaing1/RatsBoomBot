from dataclasses import dataclass
from secrets import randbelow
from typing import Any

from pets.passives import GAMBLE_LOSS_REFUND, GAMBLE_ODDS, LOYALTY_GAIN, PASSIVES, RAID_DAMAGE, scaled_bps
from storage.transactions import immediate_transaction

LOYALTY_GAIN_PASSIVE = LOYALTY_GAIN
POC_BAT_ID = "dungeon_bat"
RAT_ID = "explosive_rat"
FOX_ID = "sleepy_fox"
POC_LOYALTY_BONUS_BPS = 1_000
TICKET_PRICE = 50_000
SUMMON_PASSIVES = {POC_BAT_ID: GAMBLE_ODDS, RAT_ID: LOYALTY_GAIN, FOX_ID: RAID_DAMAGE}
RARITY_WEIGHTS = (("common", 70), ("rare", 20), ("ultra_rare", 10))
DUPLICATE_REFUNDS = {"common": 12_500, "rare": 25_000, "ultra_rare": 50_000}



@dataclass(frozen=True)
class SummonResult:
    pet_id: str
    display_name: str
    rarity: str
    duplicate: bool
    refund: int
    refund_channel: str
    equipped: bool


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
    passive_rarity: str
    passive_name: str
    passive_max_bps: int

    @property
    def effective_passive_bps(self) -> int:
        return scaled_bps(self.passive_value_bps, self.passive_max_bps, self.level, self.max_level)

    @property
    def passive_percent(self) -> float:
        return self.effective_passive_bps / 100

    @property
    def passive_percent_label(self) -> str:
        return f"{self.passive_percent:g}"

    @property
    def passive_description(self) -> str:
        return PASSIVES[self.passive_type].description


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
                   owned.passive_type, owned.passive_value_bps,
                   passives.display_name AS passive_name,
                   passives.rarity AS passive_rarity,
                   passives.max_bps AS passive_max_bps
            FROM user_pet_loadouts AS loadouts
            JOIN user_pets AS owned ON owned.id = loadouts.user_pet_id
            JOIN pet_definitions AS definitions ON definitions.id = owned.pet_id
            JOIN pet_passive_definitions AS passives ON passives.id = owned.passive_type
            WHERE loadouts.user_id = ?
            LIMIT 1
        """

        if connection is not None:
            row = await connection.fetchone(query, (str(user_id),))
        else:
            async with self.db.acquire() as managed_connection:
                row = await managed_connection.fetchone(query, (str(user_id),))

        return self._from_row(row) if row is not None else None

    async def get_collection(self, user_id: str) -> list[EquippedPet]:
        async with self.db.acquire() as connection:
            rows = await connection.fetchall("""
            SELECT owned.id AS user_pet_id, definitions.id AS pet_id,
                   definitions.display_name, definitions.rarity,
                   definitions.sprite_path, definitions.frame_count,
                   definitions.max_level, owned.level, owned.xp,
                   owned.passive_type, owned.passive_value_bps,
                   passives.display_name AS passive_name,
                   passives.rarity AS passive_rarity,
                   passives.max_bps AS passive_max_bps
            FROM user_pets AS owned
            JOIN pet_definitions AS definitions ON definitions.id = owned.pet_id
            JOIN pet_passive_definitions AS passives ON passives.id = owned.passive_type
            WHERE owned.user_id = ?
            ORDER BY definitions.display_name
            """, (str(user_id),))
        return [self._from_row(row) for row in rows]

    async def _summon_pools(self, connection) -> dict[str, list[Any]]:
        rows = await connection.fetchall(
            "SELECT id, display_name, rarity FROM pet_definitions ORDER BY display_name"
        )
        return {
            rarity: [row for row in rows if row["rarity"] == rarity and row["id"] in SUMMON_PASSIVES]
            for rarity, _ in RARITY_WEIGHTS
        }

    async def get_summon_rates(self) -> list[dict[str, Any]]:
        async with self.db.acquire() as connection:
            pools = await self._summon_pools(connection)
        total_weight = sum(weight for rarity, weight in RARITY_WEIGHTS if pools[rarity])
        return [
            {
                "rarity": rarity,
                "base_percent": weight,
                "effective_percent": weight * 100 / total_weight if pools[rarity] and total_weight else 0,
                "pets": [
                    {
                        "pet_id": str(row["id"]),
                        "display_name": str(row["display_name"]),
                        "percent": weight * 100 / total_weight / len(pools[rarity]),
                    }
                    for row in pools[rarity]
                ],
            }
            for rarity, weight in RARITY_WEIGHTS
        ]

    async def ticket_count(self, user_id: str) -> int:
        async with self.db.acquire() as connection:
            row = await connection.fetchone(
                "SELECT COUNT(*) AS count FROM pet_summon_tickets WHERE user_id = ?",
                (str(user_id),),
            )
        return int(row["count"])

    async def buy_ticket(self, broadcaster_id: str, user_id: str) -> int:
        broadcaster_id, user_id = str(broadcaster_id), str(user_id)
        async with self.db.acquire() as connection:
            async with immediate_transaction(connection):
                row = await connection.fetchone(
                    "SELECT points FROM viewers WHERE broadcaster_id = ? AND user_id = ?",
                    (broadcaster_id, user_id),
                )
                if row is None or int(row["points"]) < TICKET_PRICE:
                    raise ValueError("You need 50,000 loyalty points in this channel to buy a summon ticket.")
                await connection.execute(
                    "UPDATE viewers SET points = points - ? WHERE broadcaster_id = ? AND user_id = ?",
                    (TICKET_PRICE, broadcaster_id, user_id),
                )
                await connection.execute(
                    "INSERT INTO pet_summon_tickets (user_id, broadcaster_id) VALUES (?, ?)",
                    (user_id, broadcaster_id),
                )
                balance = int(row["points"]) - TICKET_PRICE
        return balance

    async def summon(self, user_id: str, username: str) -> SummonResult:
        user_id = str(user_id)
        async with self.db.acquire() as connection:
            async with immediate_transaction(connection):
                ticket = await connection.fetchone(
                    "SELECT id, broadcaster_id FROM pet_summon_tickets WHERE user_id = ? ORDER BY id LIMIT 1",
                    (user_id,),
                )
                if ticket is None:
                    raise ValueError("You have no summon tickets. Buy one with !pets buy ticket (50,000 points).")
                pools = await self._summon_pools(connection)
                available = [(rarity, weight) for rarity, weight in RARITY_WEIGHTS if pools[rarity]]
                if not available:
                    raise ValueError("No pets are available to summon right now. Your ticket has been kept.")
                roll = randbelow(sum(weight for _, weight in available))
                for rarity, weight in available:
                    if roll < weight:
                        break
                    roll -= weight
                definition = pools[rarity][randbelow(len(pools[rarity]))]
                pet_id = str(definition["id"])
                passive = SUMMON_PASSIVES[pet_id]
                refund = DUPLICATE_REFUNDS[rarity]
                owned = await connection.fetchone("SELECT id FROM user_pets WHERE user_id = ? AND pet_id = ?", (user_id, pet_id))
                duplicate = owned is not None
                equipped = False
                source = str(ticket["broadcaster_id"])
                if duplicate:
                    # Refund purchased points directly, without earned-point bonuses or XP.
                    await connection.execute(
                        """INSERT INTO viewers (broadcaster_id, user_id, username, points)
                           VALUES (?, ?, ?, ?) ON CONFLICT(broadcaster_id, user_id)
                           DO UPDATE SET points = viewers.points + excluded.points""",
                        (source, user_id, username, refund),
                    )
                else:
                    await connection.execute(
                        """INSERT INTO user_pets (user_id, pet_id, level, xp, passive_type, passive_value_bps)
                           VALUES (?, ?, 1, 0, ?, ?)""",
                        (user_id, pet_id, passive, PASSIVES[passive].min_bps),
                    )
                    owned = await connection.fetchone("SELECT id FROM user_pets WHERE user_id = ? AND pet_id = ?", (user_id, pet_id))
                    equipped = await self.get_equipped_pet(user_id, connection) is None
                    if equipped:
                        await connection.execute("INSERT INTO user_pet_loadouts (user_id, user_pet_id) VALUES (?, ?)", (user_id, owned["id"]))
                await connection.execute("DELETE FROM pet_summon_tickets WHERE id = ?", (ticket["id"],))
                result = SummonResult(pet_id, str(definition["display_name"]), rarity, duplicate, refund if duplicate else 0, source, equipped)
        return result

    async def equip(self, user_id: str, name: str) -> EquippedPet:
        collection = await self.get_collection(str(user_id))
        name = name.strip().casefold()
        pet = next((pet for pet in collection if name in {pet.pet_id.casefold(), pet.display_name.casefold()}), None)
        if pet is None:
            raise ValueError("You don't own that pet. Use its full name from your collection.")
        async with self.db.acquire() as connection:
            async with immediate_transaction(connection):
                await connection.execute(
                    """INSERT INTO user_pet_loadouts (user_id, user_pet_id) VALUES (?, ?)
                       ON CONFLICT(user_id) DO UPDATE SET user_pet_id = excluded.user_pet_id,
                       equipped_at = CURRENT_TIMESTAMP""", (str(user_id), pet.user_pet_id),
                )
        return pet

    async def loyalty_bonus(self, user_id: str, base_amount: int, connection=None) -> int:
        if base_amount <= 0:
            return 0

        return (int(base_amount) * await self.bonus_bps(user_id, LOYALTY_GAIN_PASSIVE, connection)) // 10_000

    async def bonus_bps(self, user_id: str, passive_type: str, connection=None) -> int:
        pet = await self.get_equipped_pet(user_id, connection)
        return pet.effective_passive_bps if pet is not None and pet.passive_type == passive_type else 0

    async def gamble_win_chance(self, user_id: str, base_chance: float) -> float:
        from pets.passives import GAMBLE_ODDS
        return min(1.0, base_chance + await self.bonus_bps(user_id, GAMBLE_ODDS) / 10_000)

    async def gamble_loss_refund(self, user_id: str, bet: int, connection=None) -> int:
        return (bet * await self.bonus_bps(user_id, GAMBLE_LOSS_REFUND, connection)) // 10_000

    async def grant_poc_bat(self, user_id: str) -> EquippedPet:
        return await self.grant_pet(user_id, POC_BAT_ID, GAMBLE_ODDS)

    async def grant_rat(self, user_id: str, passive_type: str = LOYALTY_GAIN) -> EquippedPet:
        return await self.grant_pet(user_id, RAT_ID, passive_type)

    async def grant_fox(self, user_id: str, passive_type: str = RAID_DAMAGE) -> EquippedPet:
        return await self.grant_pet(user_id, FOX_ID, passive_type)

    async def grant_pet(self, user_id: str, pet_id: str, passive_type: str) -> EquippedPet:
        if pet_id not in {POC_BAT_ID, RAT_ID, FOX_ID} or passive_type not in PASSIVES:
            raise ValueError("Unknown pet or passive.")

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
                    (user_id, pet_id, passive_type, PASSIVES[passive_type].min_bps)
                )
                owned = await connection.fetchone(
                    "SELECT id FROM user_pets WHERE user_id = ? AND pet_id = ?",
                    (user_id, pet_id)
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
            raise RuntimeError("The pet was granted but could not be loaded.")

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
            passive_value_bps=int(row["passive_value_bps"]),
            passive_name=str(row["passive_name"]),
            passive_rarity=str(row["passive_rarity"]),
            passive_max_bps=int(row["passive_max_bps"])
        )
