# Release 10.0.0: hidden achievements and global blessed weapons

Feature PRs target `release/10.0.0` for UAT. Merge the release into `master` after
testing; this feature does not deploy itself.

- Collecting the Stones: collect all five distinct Blessed Unique weapons.
- Rat Exterminator: 100 confirmed kamikaze hits against another chatter, summed
  across channels. Protected callers' successful hits count. Self-targets,
  misses, protected-target backfires, and Twitch timeout failures do not count.

Both achievements are hidden until earned and have one Platinum tier. Their
icons use the existing SVG badge system. Existing inventory and recorded drops
qualify for the collection achievement; historical unlock dates are unknown.
Kamikaze progress begins at deployment. Message IDs deduplicate success records.

Migration 32 consolidates Blessed Unique ownership under the empty broadcaster
scope in `raid_boss_inventory`. Duplicate channel copies become one shared weapon
with the highest remaining durability. Original reward records remain associated
with their source channels. Other weapon tiers and consumables stay channel-local.

Viewers equip shared blessed weapons independently in each raid-enabled channel.
Durability is shared; repairing with the current channel's points repairs the same
weapon everywhere. Duplicate drops retain existing refill behavior. These weapons
remain unsellable. Attack and repair operations serialize within the bot service
so simultaneous channel attacks cannot both use the last durability charge.
This assumes one running bot process per database, as in the current deployment.

The raid service routes inventory reads, attacks, flag-bearer durability, drops,
equipment, and repairs through the shared scope. Channel stats include shared
weapons. Migration changes require matching version 10 code: do not roll back to
version 9 code alone after migration; restore a matching pre-release database backup.

UAT checks: equip one blessed weapon in two channels, attack in both and inspect
shared durability, repair with one channel's points, verify an ordinary weapon
stays local, and confirm hidden cards appear only at their thresholds.
