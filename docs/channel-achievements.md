# Channel achievements

Version 11.0.0 adds a channel-scoped Achievements tab to each connected channel on a public chatter profile. Internal achievement IDs, thresholds, progress, unlocks, and rewards stay consistent across channels; each `ChannelProfile` can supply themed display names with `ChannelAchievementNames` from its `profile_details.py`.

| Progress type | Bronze / Silver / Gold / Platinum |
| --- | --- |
| Daily check-ins | 10 / 50 / 100 / 365 |
| Messages sent while live | 1,000 / 10,000 / 50,000 / 100,000 |
| Lifetime points earned | 25,000 / 250,000 / 1,250,000 / 5,000,000 |
| Gambling profit | 5,000 / 50,000 / 250,000 / 1,000,000 |
| Raid damage | 10,000 / 100,000 / 1,000,000 / 10,000,000 |
| Defeated bosses joined | 1 / 10 / 50 / 100 |
| Weapons purchased | 1 / 10 / 50 / 100 |
| Buffs purchased | 1 / 10 / 50 / 100 |
| Consumables purchased | 10 / 50 / 250 / 1,000 |

Every channel tier pays into that channel's loyalty balance: 500 for Bronze, 2,000 for Silver, 7,500 for Gold, and 25,000 for Platinum. `channel_achievement_rewards` is the immutable, uniquely keyed reward ledger. An unlock and its balance credit occur in the same SQLite transaction, and duplicate source updates cannot pay a tier twice. Achievement rewards do not increase lifetime-earned progress, preventing rewards from recursively unlocking the Point Collector line.

Migration 33 backfills progress-based unlocks and rewards from existing check-ins, lifetime earnings, gambling totals, raid damage, defeated encounters, and purchases. Live-message progress begins at version 11.0.0 because historical message totals do not identify whether the stream was live. The existing all-message statistic remains unchanged. Future messages increment `channel_live_messages` only while the channel has an active stream-log session.

Unlocks are permanent if source totals later decrease. Removing a channel hides its channel page but retains historical unlock and reward records. UAT should verify themed names, all filters, reward credits at each threshold, no duplicate payouts, offline messages not counting, and mobile achievement cards.
