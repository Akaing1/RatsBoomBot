from math import isqrt

from bot.services.channels.achievements import ACHIEVEMENT_TIER_XP


RAID_TIER_XP = {"tutorial": 25, "mini": 50, "main": 100}
LEVEL_CURVE_BASE = 500


class ChatterLevelService:

    def __init__(self, db):
        self.db = db

    async def get_global_level(self, user_id: str) -> dict[str, int]:
        user_id = str(user_id)
        achievement_query = "SELECT tier, COUNT(*) AS unlocks FROM achievement_unlocks WHERE user_id = ? GROUP BY tier"
        raid_query = """
        SELECT events.boss_tier, COUNT(DISTINCT events.id) AS clears
        FROM raid_boss_events AS events
        WHERE events.status = 'defeated'
          AND EXISTS (
              SELECT 1 FROM raid_boss_contributions AS contributions
              WHERE contributions.event_id = events.id AND contributions.user_id = ?
          )
        GROUP BY events.boss_tier
        """

        async with self.db.acquire() as connection:
            achievement_rows = await connection.fetchall(achievement_query, (user_id,))
            raid_rows = await connection.fetchall(raid_query, (user_id,))

        achievement_xp = sum(ACHIEVEMENT_TIER_XP.get(int(row["tier"]), 0) * int(row["unlocks"]) for row in achievement_rows)
        raid_xp = sum(RAID_TIER_XP.get(str(row["boss_tier"]), 0) * int(row["clears"]) for row in raid_rows)
        return self.calculate(achievement_xp, raid_xp)

    @staticmethod
    def calculate(achievement_xp: int, raid_xp: int) -> dict[str, int]:
        achievement_xp = max(0, int(achievement_xp))
        raid_xp = max(0, int(raid_xp))
        total_xp = achievement_xp + raid_xp
        level = isqrt(total_xp // LEVEL_CURVE_BASE) + 1
        level_start = LEVEL_CURVE_BASE * (level - 1) ** 2
        next_level_at = LEVEL_CURVE_BASE * level ** 2
        current_xp = total_xp - level_start
        xp_required = next_level_at - level_start

        return {
            "level": level,
            "total_xp": total_xp,
            "achievement_xp": achievement_xp,
            "raid_xp": raid_xp,
            "current_xp": current_xp,
            "xp_required": xp_required,
            "next_level_at": next_level_at,
            "percent": min(100, round(current_xp * 100 / xp_required))
        }
