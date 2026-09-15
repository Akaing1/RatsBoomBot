# Community achievements — v11.2.0

New channel achievements provide alternatives to daily check-ins. Regular tiers pay 500 / 2,000 / 7,500 / 25,000 channel points once per tier. Global badges still have no payout.

| Default name | Bronze | Silver | Gold | Platinum |
| --- | ---: | ---: | ---: | ---: |
| Part of the Furniture | 25 hours | 100 hours | 500 hours | 2,000 hours |
| See You Next Stream | 10 streams | 50 streams | 150 streams | 365 streams |
| Helping Hands | 500 damage | 2,000 damage | 5,000 damage | 10,000 damage |
| Built, Not Bought | 1 craft | 3 crafts | 5 crafts | 10 crafts |
| A Little TLC | 1 repair | 3 repairs | 5 repairs | 10 repairs |

Names can be themed through the five new `ChannelAchievementNames` fields in channel `profile_details.py` files. Existing profiles inherit defaults.

## Hidden channel badges

Each pays 25,000 points once and is hidden until unlocked:

- **By a Whisker:** finish a main or mini boss with exactly 1 HP before your attack.
- **Not Even Close:** your damaging attack leaves a main or mini boss at exactly 1 HP.
- **Perfectly Average:** the measured viewer rolls exactly 50% on stinky, smart, and lucky in the same channel, across any number of streams.
- **Character Development:** the measured viewer earns both opposite measurement badges for any one command in the same channel. Additional pairs do not pay again.

Tutorial bosses do not qualify for the HP badges or Helping Hands. Zero-damage attacks cannot earn an HP badge.

## Tracking and persistence

Migration 35 creates `community_achievement_progress` and `community_stream_visits`. There is no historical backfill or deployment-time payout for these new badges. Existing opposite measurement rolls can contribute to Character Development when a new qualifying measurement is recorded after deployment.

- Presence adds two minutes per unique `passive_point_payouts` entry while live. This estimates connected-chat presence, not video viewing, and depends on passive points being enabled and a successful chatter-list fetch. No offline time or downtime catch-up is credited.
- Distinct streams count each stream ID once per viewer/channel when sampled; restarts do not add another visit.
- Flag Bearer progress credits recorded bonus damage to the flag bearer, not the attacker.
- Crafting counts successful Refined/Masterwork crafts. Repairs count only restored durability, including shared Blessed weapons repaired using this channel's points.
- `raid_boss.py` records craft/repair progress in the same immediate transaction as payment and inventory changes. Attack HP is checked inside an immediate transaction. Failed or rolled-back actions cannot pay rewards.
- Database triggers unlock tiers and use the existing uniquely keyed reward ledger. Repeated activity cannot pay an earned tier again. Achievement rewards do not feed lifetime earnings.
- `AchievementService` adds the cards and converts stored presence minutes to displayed hours.

Point Collector now uses 25,000 / 250,000 / 1,250,000 / 5,000,000 globally and per channel, five times the gambling-profit requirements. Migration 35 only updates thresholds: existing unlocks and reward records remain intact.

## UAT checks

Verify names and Chat/Raids filters. Two live samples should add four minutes but one stream; offline time adds nothing. Exercise successful crafting and repair, then retry without materials or at full durability. Check the once-only reward and balance. Test exact 1 HP attacks on main and mini bosses and a near miss at 2 HP. Measure the same viewer across the three 50% rolls and an opposite pair; repeat to confirm no duplicate payout. Existing Point Collector holders should retain badges below the new requirements.
