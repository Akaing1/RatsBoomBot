"""Combat and reward rules for the 2026 shared Mistletoe Mimic encounter."""

from dataclasses import dataclass
from datetime import UTC, datetime

START = datetime(2026, 12, 11, tzinfo=UTC)
END = datetime(2027, 1, 1, tzinfo=UTC)
MAX_HP = 1_000_000
MILESTONE_DAMAGE = 200_000


def milestones(hp: int) -> int:
    if not 0 <= hp <= MAX_HP:
        raise ValueError("Invalid Mimic HP")
    return (MAX_HP - hp) // MILESTONE_DAMAGE


@dataclass(frozen=True)
class Hit:
    remaining_hp: int
    credited_damage: int
    milestone_points_per_eligible_channel: int


def apply_hit(hp: int, damage: int) -> Hit:
    """Calculate the transition while the caller holds the shared encounter lock."""
    before = milestones(hp)
    if hp == 0 or damage <= 0:
        raise ValueError("An active Mimic and positive damage are required")
    credited = min(hp, damage)
    remaining = hp - credited
    crossed = milestones(remaining) - before
    return Hit(remaining, credited, crossed * 10_000)


@dataclass(frozen=True)
class FinaleReward:
    points_per_participating_channel: int
    global_pet_tickets: int
    guaranteed_mythicals: int
    extra_unowned_mythical_chance: float


def finale_reward(hp: int, global_rank: int) -> FinaleReward:
    """For one participant after victory or expiry. Rank is one-based."""
    if global_rank < 1:
        raise ValueError("Invalid contributor rank")
    top_ten_win = hp == 0 and global_rank <= 10
    return FinaleReward(
        points_per_participating_channel=milestones(hp) * 20_000 + (20_000 if top_ten_win else 0),
        global_pet_tickets=3 if top_ten_win else 2,
        guaranteed_mythicals=int(hp == 0),
        extra_unowned_mythical_chance=0.05 if top_ten_win else 0.0,
    )
