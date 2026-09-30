# Pets and passives

Pets belong to a chatter globally. One pet can be equipped at a time, and its passive applies in every channel. The Silly Bat has Gamble Luck (+5 percentage points to gamble win chance). The Little Rat is a Common pet with a four-frame sprite.

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
3. Add its ID and fixed passive to `SUMMON_PASSIVES` in `pets/service.py`, add its ID to the allowed grant catalog, and optionally add a convenience grant method. The summon pool and Rates popup then use its seeded rarity automatically. Existing passives can be selected without adding new gameplay code.
4. Add a short selector to `scripts/grant_poc_pet.py` (Sleepy Fox uses `--pet fox`). The script runs migrations, grants ownership, and equips the pet without resetting an existing copy.
5. The global profile renders the sprite from the database. For custom timing, add a pet-specific class in `web/templates/public/chatter_profile.html` and its animation in `web/static/css/style.css`. Sleepy Fox uses a 2.4-second breathing cycle. Respect the existing reduced-motion rule.
6. Check fresh-database seeding, repeat grants, the profile render, and the animation. Run the tests and open a PR against the current release.

After deployment, grant Sleepy Fox with:

```bash
sudo -u rats-bot .venv/bin/python -m scripts.grant_poc_pet Ninjakaing --pet fox
```

Sleepy Fox is Common. Administrator grants use the fixed mappings below by default; `--passive` can override them for testing. Self-service summons use the fixed passives below.

## Summoning (release 13)

- `!pets`: equipped pet, active passive, ticket count, and full collection link on the global profile / me page.
- `!pets buy ticket`, `!pets buy summon`, or `!pets buy summon ticket`: buy one global ticket for **50,000 loyalty points from the current channel**. Points must be enabled in that channel.
- `!pets summon` or `!pets summon ticket`: consume the oldest ticket. Tickets and ownership are global.
- `!pets equip <full pet name>`: equip an owned pet across all channels. The first summon auto-equips; later new pets leave the existing loadout alone.

| Pet | Rarity | Chance | Fixed summon passive | Duplicate refund |
| --- | --- | --- | --- | --- |
| Silly Bat | Common | 25% | Gamble Luck: +5 percentage points win chance | 12,500 points |
| Little Rat | Common | 25% | Loyalty Gain: +10% earned loyalty points | 12,500 points |
| Sleepy Fox | Common | 25% | Boss Hunt Damage: +10% damage | 12,500 points |
| Horned Wolf | Common | 25% | Boss Hunt Damage: +10% damage | 12,500 points |

Summons first roll rarity with 70% Common / 20% Rare / 10% UR weights, excluding empty tiers and normalizing the remaining weights. They then choose uniformly within that rarity. All four pets are Common, so currently Common is 100% and each pet has a 25% chance. The Pets tab has an expandable Rates popup anchored to the Rates control, showing the standard rarity rates and the available pets in each tier. The rat keeps its stable internal ID and sprite URL after being renamed Little Rat. Migration 58 aligns previously owned UAT pets with these fixed mappings without changing equipment, level, or XP.

Duplicates return points to the ticket's original purchase channel, without loyalty bonuses or earned-point XP. Purchases and summons are atomic to prevent double spending. Existing pets are aligned with the selected mappings on migration. No leveling, feeding, essence purchases, or passive rerolls are added here.

### UAT check

1. Give a test chatter at least 50,000 channel points using the channel's moderator points command.
2. Run each purchase alias and confirm exactly 50,000 points is deducted per ticket.
3. Run `!pets summon`, then `!pets`, and check the sprite and collection on the linked profile.
4. Obtain a second pet and run `!pets equip Little Rat` (or its full name). Check that it is equipped in another channel too.
5. Summon a duplicate and verify the refund against the table in the ticket's purchase channel, even if summoned elsewhere.
6. Confirm an empty balance cannot buy and an empty ticket inventory cannot summon.

### Horned Wolf preview

Migration 59 adds Horned Wolf with the approved four-frame artwork in `assets/Horned Wolf.png`. The profile plays the strip using its existing CSS sprite animation at a 2.4-second cycle; no generated GIF or procedural breathing warp is used. Frames are packed into equal cells with a shared ground baseline.

Grant and equip it for UAT preview: `sudo -u rats-bot .venv/bin/python -m scripts.grant_poc_pet <tester_login> --pet wolf`. An owned wolf can also be equipped with `!pets equip Horned Wolf`.
