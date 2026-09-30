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

Sleepy Fox is Common and defaults to Boss Hunt Damage, like the rat. `--passive` can select an existing passive. Self-service summons and leveling are still future work.
