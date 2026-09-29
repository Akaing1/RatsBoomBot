# Pets and passives

Pets belong to a chatter globally. One pet can be equipped at a time, and its passive applies in every channel. The Silly Bat remains available with its fixed 10% loyalty gain. The Explosive Rat is a Common pet with a four-frame sprite.

Pet rarity and passive rarity are separate. Both use Common, Rare, and Ultra Rare tiers. A pet has one passive, chosen when it is first granted. The same pet can be equipped again without resetting its level or passive. Each chatter can own one of each pet type for now.

| Passive | Tier | Level 1 → level 50 | Effect |
| --- | --- | --- | --- |
| Boss Hunt Damage | Common | 10% → 20% | Extra damage on each Boss Hunt attack |
| Gamble Luck | Common | 5 → 10 percentage points | Added to the channel's gamble win chance, capped at 100% |
| Boss Hunt Profit | Common | 10% → 20% | Extra contribution and final hit point rewards |
| Rare Drop Luck | Rare | 1 → 5 percentage points | Added to the top contributor's mythical weapon roll |
| Kamikaze Luck | Rare | 5 → 10 percentage points | Added to the targeted `!kamikaze` hit chance |
| Second Chance | Ultra Rare | 10% fixed | Returns 10% of a lost `!gamble` bet; the result still counts as a loss |

The level increases linearly from the listed starting value to its maximum at level 50, in whole basis points. Progression and pet acquisition beyond the administrator grant are future work. The current grant tool can issue and equip a rat for a known Twitch identity:

```bash
python -m scripts.grant_poc_pet chatter_name --pet rat --passive raid_damage
```

Available `--passive` values are `loyalty_gain`, `raid_damage`, `gamble_odds`, `raid_profit`, `rare_drop_chance`, `kamikaze_odds`, and `gamble_loss_refund`. Regranting an owned rat equips the existing one; it does not replace its passive.
