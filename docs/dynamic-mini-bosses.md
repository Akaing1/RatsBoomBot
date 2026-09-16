# Dynamic mini-boss HP — v11.3.0

Mini bosses select uniformly at random from the pool unlocked by unique contributors in the previous completed raid in the same channel.

| Previous contributors | Eligible HP |
| --- | --- |
| 0–9 | 10,000 |
| 10–19 | 10,000 / 20,000 |
| 20–29 | 10,000 / 20,000 / 35,000 |
| 30–39 | 10,000 / 20,000 / 35,000 / 50,000 |
| 40+ | 10,000 / 20,000 / 35,000 / 50,000 / 70,000 |

The latest completed main or mini raid counts, whether defeated or expired (`failed`). Tutorials are excluded. A contributor must have positive recorded attack or Flag Bearer bonus damage. Count by user ID, so multiple attacks, name changes, and attack/support overlap cannot inflate participation. A raid with no contributors, or no previous qualifying raid, gives the 10,000 HP pool.

The one-active-raid-per-channel constraint makes descending event ID the completion ordering for normal raid lifecycle operations. Existing history supplies the count, so no migration or new tracking table is required. Manually spawned mini bosses use the same selection rules.

Main-boss cadence, random boss names/types, encounter duration, and main/tutorial HP are unchanged. Active bosses retain their saved HP. Reward pools still derive from the selected HP using the channel's `reward_points_per_hp`; contribution multipliers are unchanged.

`RaidBossService.previous_raid_contributors` reads the shared attack/support contribution view. `mini_boss_hp_pool` selects eligible tiers and `spawn` draws with `random.choice`. The former `mini_hp_min/max/step` settings are removed, including Meinya's overrides, because the new tiers are not evenly spaced. Spawn logs include broadcaster, previous contributor count, eligible HP, and selected HP.

For UAT, check the logged pool against the previous completed encounter's unique contributors, then confirm the new mini boss's HP and reward pool. A first mini boss after only tutorial history should have 10,000 HP.
