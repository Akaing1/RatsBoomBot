# Pets and passives

Pets belong to a chatter globally. One pet can be equipped at a time, and its passive applies in every channel. The Silly Bat remains available with its fixed 10% loyalty gain. The Explosive Rat is a Rare pet with a four-frame sprite.

Pet rarity and passive rarity are separate. Both use Common, Rare, and Ultra Rare tiers. A pet has one passive, chosen when it is first granted. The same pet can be equipped again without resetting its level or passive. Each chatter can own one of each pet type for now.

| Passive | Tier | Level 1 → level 50 | Effect |
| --- | --- | --- | --- |
| Boss Hunt Damage | Common | 10% → 20% | Extra damage on each Boss Hunt attack |
| Gamble Luck | Common | 5 → 10 percentage points | Added to the channel's gamble win chance, capped at 100% |
| Boss Hunt Profit | Common | 10% → 20% | Extra contribution and final hit point rewards |
| Rare Drop Luck | Rare | 1 → 5 percentage points | Added to the top contributor's mythical weapon roll |
| Kamikaze Luck | Rare | 5 → 10 percentage points | Added to the targeted `!kamikaze` hit chance |
| Second Chance | Ultra Rare | 10% fixed | Returns 10% of a lost `!gamble` bet; the result still counts as a loss |

The level increases linearly from the listed starting value to its maximum at level 50, in whole basis points. Level progression remains future work. Self-service acquisition is described below. The current grant tool can issue and equip a rat for a known Twitch identity:

```bash
python -m scripts.grant_poc_pet chatter_name --pet rat --passive raid_damage
```

Available `--passive` values are `loyalty_gain`, `raid_damage`, `gamble_odds`, `raid_profit`, `rare_drop_chance`, `kamikaze_odds`, and `gamble_loss_refund`. Regranting an owned rat equips the existing one; it does not replace its passive.

## Adding a pet

1. Put a transparent PNG sprite sheet in `assets/`, named after the pet (for example `Sleepy Fox.png`). Current pets use four equal 112 × 149 frames in a 448 × 149 strip. Align the feet/contact baseline and leave room for the whole sprite. Review an animated preview before publishing.
2. Add a **new** numbered migration in `storage/migrations/` inserting its stable ID, display name, rarity (`common`, `rare`, or `ultra_rare`), URL-encoded asset path, frame count, and maximum level into `pet_definitions`. Register it in `storage/migrations/__init__.py`. Never edit an already applied migration to rename or update a pet; add a new migration.
3. Add its ID to the allowed catalog in `pets/service.py` and optionally add a convenience grant method. Existing passives can be selected without adding new gameplay code.
4. Add a short selector to `scripts/grant_poc_pet.py` (Sleepy Fox uses `--pet fox`). The script runs migrations, grants ownership, and equips the pet without resetting an existing copy.
5. The global profile renders the sprite from the database. For custom timing, add a pet-specific class in `web/templates/public/chatter_profile.html` and its animation in `web/static/css/style.css`. Sleepy Fox uses a 2.4-second breathing cycle. Respect the existing reduced-motion rule.
6. Check fresh-database seeding, repeat grants, the profile render, and the animation. Run the tests and open a PR against the current release.

After deployment, grant Sleepy Fox with:

```bash
sudo -u rats-bot .venv/bin/python -m scripts.grant_poc_pet Ninjakaing --pet fox
```

Sleepy Fox is UR. Administrator grants still default to Boss Hunt Damage, like the rat, and `--passive` can select an existing passive. Self-service summons use the fixed passives below.

## Summoning (release 13)

- `!pets`: equipped pet, active passive, ticket count, and full collection link on the global profile / me page.
- `!pets buy ticket`, `!pets buy summon`, or `!pets buy summon ticket`: buy one global ticket for **50,000 loyalty points from the current channel**. Points must be enabled in that channel.
- `!pets summon` or `!pets summon ticket`: consume the oldest ticket. Tickets and ownership are global.
- `!pets equip <full pet name>`: equip an owned pet across all channels. The first summon auto-equips; later new pets leave the existing loadout alone.

| Pet | Rarity | Chance | Fixed summon passive | Duplicate refund |
| --- | --- | --- | --- | --- |
| Silly Bat | Common | 70% | Loyalty Gain: +10% earned loyalty points | 12,500 points |
| Explosive Rat | Rare | 20% | Kamikaze Luck: +5 percentage points hit chance | 25,000 points |
| Sleepy Fox | UR | 10% | Second Chance: 10% of lost gamble bets refunded | 50,000 points |

Duplicates return points to the ticket's original purchase channel, without loyalty bonuses or earned-point XP. Purchases and summons are atomic to prevent double spending. Existing granted pets retain their passives. No leveling, feeding, essence purchases, or passive rerolls are added here.

### UAT check

1. Give a test chatter at least 50,000 channel points using the channel's moderator points command.
2. Run each purchase alias and confirm exactly 50,000 points is deducted per ticket.
3. Run `!pets summon`, then `!pets`, and check the sprite and collection on the linked profile.
4. Obtain a second pet and run `!pets equip Explosive Rat` (or its full name). Check that it is equipped in another channel too.
5. Summon a duplicate and verify the refund against the table in the ticket's purchase channel, even if summoned elsewhere.
6. Confirm an empty balance cannot buy and an empty ticket inventory cannot summon.
