# Viewer achievements

Version 9.4.0 adds permanent achievement tiers to the Achievements tab on public global chatter profiles reached through !stats.

| Achievement | Scope | Bronze / Silver / Gold / Platinum |
| --- | --- | --- |
| Community Explorer | Global unique channels with a positive daily check-in total | 1 / 5 / 10 / 25 |
| Daily Regular | Global daily check-in total | 10 / 50 / 250 / 1,000 |
| Familiar Face | Daily check-ins in one channel | 10 / 50 / 100 / 365 |

FIRST and SECOND do not count as daily check-ins. Imported daily totals and recorded daily claims are combined, matching the existing stats page. Zero-count imports do not count as visits. Twitch user and broadcaster IDs identify progress across name changes.

Migration 29 stores the thresholds and backfills eligible tiers. Historical and imported unlocks have a NULL unlocked_at (displayed as historical/date unknown); recorded_at captures when the bot recorded them. New daily inserts use the claim timestamp. SQLite triggers record unlocks in the same transaction as the claim or import, including standalone import tools. The primary key prevents duplicates. Removing or reducing source totals does not revoke earned tiers; current progress can consequently be lower than an earned milestone.

AchievementService reads progress and permanent unlocks without mutating data on public page requests. SVG templates use currentColor to inherit tier styling. Text labels also distinguish tiers. Public profile pages refresh progress on page reload.

Unlocks are silent and have no point, XP, or combat rewards. XP, channel levels, raid awards, and leaderboards are on standby. Their rules and reward amounts are provisional and must be revisited before implementation. Raid/crafting achievements and raid refactoring are outside this release.

UAT: verify historical badges, empty profiles, repeated check-ins in one channel, distinct-channel milestones, all three filters, and mobile layout. Confirm a new qualifying daily claim unlocks once with a timestamp and that FIRST/SECOND do not advance it.
