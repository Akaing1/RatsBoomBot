# Raid progress checkpoints and payouts — v11.4.0

Boss encounters reward the HP removed rather than selecting a reduced pool from a win/loss threshold. With the default `reward_points_per_hp=1.0`, 37,500 damage releases a 37,500-point base pool when the encounter resolves. A full clear releases the boss's full HP value.

The released pool uses the existing ranked mini-boss distribution: divide it evenly among contributors, then apply 1.50× to the top 15%, 1.25× through the top 30%, 1.10× through the top 50%, and 1.00× to everyone else. Rank bonuses mean the total credited points can exceed the one-point-per-HP base pool. Integer division can leave a small remainder undistributed.

Full clears continue to award the configured finishing bonus and run weapon drop rolls. An encounter that reaches its stream limit or is ended manually pays its damage-earned pool without a finishing bonus or drops. Zero damage pays zero points. Internal `defeated` and `failed` database statuses remain for compatibility; public history displays `Cleared` and `Concluded`.

Health progress announcements are persisted in `raid_boss_health_checkpoints` at 25%, 50%, and 75% damage. A restart cannot repeat a checkpoint. If one attack crosses several thresholds, all crossed thresholds are recorded and only the highest new checkpoint is announced, avoiding stacked Twitch announcements. A finishing attack does not add a checkpoint announcement beside the existing clear announcement.
