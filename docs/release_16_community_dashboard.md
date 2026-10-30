# Pets, raids, and your community dashboard

This combined update catches up on pets and the raid browser, includes the changes from the impromptu v15 rollout, and brings together the dashboard and moderator improvements through v16.

## A dashboard for your moderator team

Streamers can now grant dashboard access to trusted people without sharing their own account.

- **Moderators** can open the channel Overview, follow chat and stream activity, use supported moderation controls, and leave notes for the streamer. Twitch chat replies use the moderator’s own connected account.
- **Super moderators** also get Settings, Ads Manager, and the full For You workspace, including notes, quotes, and clips.
- Streamers can add people, change their role, or revoke access from Moderator access. Revoked users see an Unauthorized page when returning to the mod dashboard.
- Your Mod Bar on **My account** lists the channels you can help manage. Moderator navigation keeps account access, channel tools, and the channel switcher separate.
- Reauthorization prompts help streamers and moderators reconnect when their Twitch or YouTube connection needs attention. Signing in or canceling channel authorization no longer sends users to admin sign-in.

## Find your next raid

The **Raid Browser** brings live-channel discovery into the dashboard. Filter candidates, preview streams, and choose where to send your community without jumping between tabs.

Starting a raid from the browser now follows the bot’s `!startraid` flow, including its messages and validation.

The Followers page adds sortable follower information and raid favorites to help with channel discovery.

## Pets join the community

Collect animated companions and equip a pet whose passive follows you across channels. The collection includes Common, Rare, and Ultra Rare pets with bonuses for loyalty, gambling, Boss Hunt damage, or raid rewards, depending on the pet.

- Open your collection with `!pets` or `!pets collection`.
- Buy a summon ticket with `!pets buy ticket`, then use `!pets summon`.
- Equip a companion with `!pets equip <pet>`.
- Your Pets tab shows your collection, animated artwork, rarity, and passive details.

## Your For You workspace

**For You** now brings three tools together:

- **Notes:** create, rename, reorder, and delete saved notes. Moderator notes are available to the streamer here too.
- **Quotes:** browse and manage your channel’s saved quotes. Use `!quote [random|number]`, `!quote add <message>`, or `!quote remove <number>` in chat, subject to command permissions.
- **Clips:** browse channel clips, watch them in the page, and download clips. Date ranges include the last 24 hours, 7 days, 1 month, and all time, with all time selected by default.

Clip filters apply as you select them. Search and sorting operate on loaded clips; load more to expand the results. The clip count shows how many have loaded, and the filter panel stays close as you browse.

The Overview’s personal timer also has simpler countdown controls and a clearer completion popup.

## A refreshed home for chatters

`!me` opens your main account profile. `!stats` opens your profile for the community you’re currently chatting in.

- Refreshed stats, achievements, pet collections, and Boss Hunt history make your progress easier to explore.
- Tabs now follow **Overview, Achievements, Pets, Boss Hunt** where available.
- Channel profiles combine Shop, Craft, and Gamble in **Activity**.
- The same updated layouts carry through to public profiles and individual community profiles.
- A right-side Communities panel shows your five most recently interacted-with channels, with an option to expand the rest. “Most Visited” replaces “Favorite” in account stats.
- Community profiles, Help, and Boss Hunt pages link together through a shared header, so you can explore without returning to chat for another command.

## Settings that are easier to find

Settings now has category navigation and a search finder on the right, leaving more space for the controls themselves.

- Related switches and messages sit together, with expandable input fields and short descriptions.
- Command groups explain their included commands. The overall Commands switch stays simple.
- Daily, First, Second, and VIP redeems have individual switches and their own settings cards.
- Timers have a creation area and a saved list with **Configure** controls. Each timer has its own enabled state; color choices appear only for announcements.
- **Follow Raids By Default** lives alongside raid messages, while Pets and Boss Hunt have separate control panels.
- Connections adds saved TikTok, X, Ko-Fi, and VGen URLs. YouTube chat setup is above Protected Users, and OBS browser sources are at the bottom of General.
- Blank supported message fields fall back to the channel default, keeping the page free of extra reset buttons.

## More live tools and clearer guides

- Polls and predictions can be managed from the dashboard, with live updates, summaries, and history, where Twitch eligibility and authorization allow them.
- The channel Help page has searchable command cards and clearer usage information.
- Boss Hunt’s channel page has a refreshed layout for boss progress, equipment, rewards, and the guide.
- Mini-boss difficulty adapts to participation and how quickly bosses are defeated, with easier tiers becoming less common as a community progresses.
- When an undefeated main boss expires with some damage dealt but less than 25% of its HP, the reward pool is at least **10% of its total HP**. This is a pool for the payout calculation, not a guaranteed amount for each attacker.

## Fixes and work behind the scenes

- Improved YouTube chat renewal and replay protection, including preventing a burst of old YouTube messages from resurfacing during busy Twitch chat.
- Fixed dashboard chat composition behavior that could leave a successfully sent message in the input during rapid sends.
- Improved clip loading, date handling, and dashboard authorization errors.
- Preserved the Mod Bar when returning from a community profile and made headers and navigation more consistent across public pages.
- Reorganized database migrations and shared service code, including loyalty and viewer queue packages, to make future maintenance easier.
- Added performance history for reviewing resource usage over time.
