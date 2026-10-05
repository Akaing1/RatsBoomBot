# Adaptive mini-boss HP — v13.1.7

Each channel saves a base mini-boss tier: 10,000 / 20,000 / 35,000 / 50,000 / 70,000 HP. A quick clear with only a few participants no longer resets the channel to the smallest pool.

| Completed mini-boss result | Base adjustment |
| --- | --- |
| Defeat a boss above the base | Set the base to the defeated boss's tier, regardless of streams used |
| Defeat the base in one stream | Raise one tier |
| Defeat the base in two streams, twice consecutively | Raise one tier |
| Defeat the base in three streams | Hold |
| Defeat a boss below the base | Hold; reduce lower-tier spawn odds |
| Fail any mini boss, including moderator conclusion | Lower the base one tier |

The base is bounded at 10k and 70k. Any other mini-boss result breaks the consecutive two-stream-clear streak. Main bosses and tutorials do not affect mini difficulty or that streak. A clear with zero registered streams does not qualify as a fast base-tier clear.

| Lower-tier clears since the last base change | Below base | Base | Above base |
| --- | --- | --- | --- |
| 0 | 15% | 60% | 25% |
| 1 | 10% | 65% | 25% |
| 2 or more | 5% | 70% | 25% |

Only adjacent tiers can roll. At the lowest or highest base, the unavailable tier's probability goes to the base. Thus the initial 10k base rolls 10k at 75% or 20k at 25%. At the 70k base, normal odds are 50k at 15% or 70k at 85%. A base change resets both the streak and lower-tier suppression; reaching a boundary without changing the base does not reset suppression.

Migration 61 adds persistent per-channel difficulty storage. It leaves existing bosses, HP, rewards, and inventories intact. On first use, the base is initialized once from unique positive-damage contributors (including support) in the latest completed **mini** boss: 0–9 → 10k, 10–19 → 20k, 20–29 → 35k, 30–39 → 50k, 40+ → 70k. No mini history starts at 10k. Historical outcomes are not replayed.

Difficulty updates commit together with encounter resolution and reward accounting. Duplicate resolution cannot apply the adjustment twice, and a failed settlement rolls it back. Stream counts use registered raid streams; disabling Boss Hunt prevents stream registration. Saved difficulty survives restarts and feature toggles.

Boss type/name randomness and the mini-to-main cadence remain independent of HP selection. Manual mini spawns use the same weights and their results update difficulty, so UAT moderation can exercise the full system. Existing active bosses are never resized. Reward pools still derive from selected HP and the channel's configured points-per-HP rate.

For UAT, clear a 10k base mini in one registered stream: the saved base should become 20k and the next roll weights should be 10k/20k/35k = 15/60/25. Clearing subsequent 10k rolls changes those weights to 10/65/25 and then 5/70/25. Defeating a 35k roll sets the base to 35k and resets suppression; failing any mini lowers the saved base one tier. Selection logs include the base HP, eligible HP values, weights, and chosen HP.
