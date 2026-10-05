"""Persistent, per-channel mini-boss difficulty and weighted HP selection."""
from dataclasses import dataclass

HP_TIERS = (10000, 20000, 35000, 50000, 70000)


@dataclass(frozen=True)
class MiniDifficulty:
    base_tier: int = 0
    two_stream_streak: int = 0
    lower_clears: int = 0

    def rolls(self) -> tuple[tuple[int, ...], tuple[int, ...]]:
        lower = max(5, 15 - 5 * self.lower_clears)
        weights = {self.base_tier: 75 - lower}
        # At either boundary, add the unavailable probability to the base.
        for tier, weight in ((self.base_tier - 1, lower), (self.base_tier + 1, 25)):
            index = min(len(HP_TIERS) - 1, max(0, tier))
            weights[index] = weights.get(index, 0) + weight
        return tuple(HP_TIERS[tier] for tier in sorted(weights)), tuple(weights[tier] for tier in sorted(weights))

    def after_result(self, hp: int, defeated: bool, streams: int) -> "MiniDifficulty":
        base = self.base_tier
        streak = 0
        lower = self.lower_clears
        if not defeated:
            base = max(0, base - 1)
        elif hp > HP_TIERS[base]:
            base = min(range(len(HP_TIERS)), key=lambda index: abs(HP_TIERS[index] - hp))
        elif hp < HP_TIERS[base]:
            lower = min(2, lower + 1)
        elif streams == 1:
            base = min(len(HP_TIERS) - 1, base + 1)
        elif streams == 2:
            streak = self.two_stream_streak + 1
            if streak >= 2:
                base = min(len(HP_TIERS) - 1, base + 1)
                streak = 0
        if base != self.base_tier:
            return MiniDifficulty(base)
        return MiniDifficulty(base, streak, lower)


async def load_difficulty(connection, broadcaster_id: str) -> MiniDifficulty:
    channel = str(broadcaster_id)
    row = await connection.fetchone("SELECT * FROM raid_mini_difficulty WHERE broadcaster_id = ?", (channel,))
    if row is None:
        # Bootstrap once from participation; subsequent results never reset it.
        previous = await connection.fetchone(
            """SELECT COUNT(DISTINCT user_id) AS contributors FROM raid_boss_contributions
               WHERE damage > 0 AND event_id = (
                   SELECT id FROM raid_boss_events WHERE broadcaster_id = ?
                   AND boss_tier = 'mini' AND status IN ('defeated', 'failed')
                   ORDER BY id DESC LIMIT 1)""", (channel,)
        )
        base = min(len(HP_TIERS) - 1, int(previous['contributors']) // 10)
        await connection.execute(
            "INSERT INTO raid_mini_difficulty (broadcaster_id, base_tier) VALUES (?, ?) ON CONFLICT DO NOTHING",
            (channel, base),
        )
        row = await connection.fetchone("SELECT * FROM raid_mini_difficulty WHERE broadcaster_id = ?", (channel,))
    return MiniDifficulty(int(row['base_tier']), int(row['two_stream_streak']), int(row['lower_clears']))


async def save_difficulty(connection, broadcaster_id: str, state: MiniDifficulty) -> None:
    await connection.execute(
        "UPDATE raid_mini_difficulty SET base_tier = ?, two_stream_streak = ?, lower_clears = ? WHERE broadcaster_id = ?",
        (state.base_tier, state.two_stream_streak, state.lower_clears, str(broadcaster_id)),
    )
