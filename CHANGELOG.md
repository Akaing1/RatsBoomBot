# Changelog

Release history reconstructed from the repository's published GitHub releases and linked pull requests on 2026-10-19. Dates below are GitHub publication dates in UTC. Published release notes are retained below, including contributor credits and comparison links; they describe historical behavior, not necessarily today's behavior.

Only published releases receive dated version headings. Intermediate development versions may appear in PR titles without having a separate published release. In particular, the v7 milestone was included in v8.0.0. Release-branch names are planning milestones, not proof that a version has shipped.

## Unreleased — release/15.0.0

The latest published release is [v14.2.2](https://github.com/Akaing1/RatsBoomBot/releases/tag/v14.2.2). The current working application version is 15.3.3; it is not yet a published release.

- Store broadcaster Riot identities exclusively in dashboard database settings; clear confirmed obsolete IDs and request re-evaluation without overwriting newer edits.

- Add sustained Twitch-disconnection recovery and diagnostic logging, bound web shutdown, back off 7TV transport failures, and handle announcement permissions/missing League summoners without repetitive tracebacks. Application version 15.3.3.

- Raid browser with discovery filters, compatibility ranking, favorites and team views, stream/video previews, and shared preview chat ([PR #387](https://github.com/Akaing1/RatsBoomBot/pull/387), merged into the release branch).
- Reusable chat composer, autocomplete, emote picker/input, cross-platform message merging, platform-specific delivery errors, and dashboard controls ([PR #387](https://github.com/Akaing1/RatsBoomBot/pull/387)).
- Shared outgoing-raid state, countdown/cancellation behavior and Follow raid; incoming-raid recency and migrations 65–67, including the Honey Hen migration-collision repair ([PR #387](https://github.com/Akaing1/RatsBoomBot/pull/387)).
- Pet API and administrator tool naming cleanup, removal of obsolete prototype exports, and refreshed project documentation; application version bumped to 14.2.3 ([PR #388](https://github.com/Akaing1/RatsBoomBot/pull/388), merged into the release branch).
- Separate local-development guide, complete published release history, and an explicit no-license notice ([PR #388](https://github.com/Akaing1/RatsBoomBot/pull/388)).

- Group migrations by feature, validate registry and applied history, cover cancellation rollback, and document the migration workflow; application version bumped to 15.0.0. Historical migration versions and behavior are preserved.

- Extract loyalty balances, gambling, duels, and passive payouts into `loyalty/`, and persistent viewer queues into `viewer_queue/`; update service wiring and imports without changing behavior or database history. Application version bumped to 15.0.1.

- Add the Moderation card’s **For You** flip side with private saved notes and persistent personal reminder timers, including overdue popups on return; migration 68 and application version 15.1.0.

- Refine the For You card: add the tab divider, simplify timers to Minutes : Seconds with themed step controls, and remove redundant labels/footer; application version 15.1.1.

- Consolidate duplicated command context/permission helpers and seven dashboard read-endpoint guards, preserving authentication and session behavior; add contract tests and a focused maintenance review. Application version 15.1.2.

- Move kamikaze into the utility command package and category, update help and public documentation, and preserve its existing cooldowns, protection rules, pet bonuses, and achievements; application version 15.1.3.

- Simplify the personal timer to one Start/Cancel button, show remaining time beneath the duration inputs, and use a single pizza-ready popup message; application version 15.1.4.

- Center the personal timer popup message and acknowledgement button; application version 15.1.5.

- Combine Features and Customization into a settings notebook with eight categories, right-side SVG tabs, mobile navigation, expandable groups, and unsaved-change indicators. Existing save endpoints and legacy links remain supported; application version 15.2.0.

- Expand Settings to the full dashboard workspace, align form and card styling with Overview, and arrange timer messages into responsive cards; application version 15.2.1.

- Match For You to Settings styling, remove explanatory text and displayed timestamps, and add note titles, editing, deletion, and ordering with automatic untitled numbering; application version 15.3.1.

- Add For You with shared current notes, per-stream/offline-day note archives, and searchable channel quote management; preserve existing notes and protect quote identities during renumbering. Application version 15.3.0.

- Remove the duplicate Loyalty Points sidebar page, retire unused Features/Customization/Loyalty templates, and consolidate settings redirects while preserving old bookmarks and form submissions; application version 15.2.4.

- Reorganize Settings categories, move protection and YouTube into General, keep raid preferences with Stream Events, conditionally show enabled game data, simplify Timers and Loyalty Points, and align message controls and input styling; application version 15.2.3.

- Move Settings category tabs to the top and replace separate enable buttons with status switches beside their related settings; application version 15.2.2.

For future releases, summarize changes here as they merge. When publishing, move the applicable notes under the actual released version and publication date, retaining source links. Do not create release entries from branch names or version bumps alone.

## [v14.2.2](https://github.com/Akaing1/RatsBoomBot/releases/tag/v14.2.2) — 2026-10-15

**Release scope clarification:** This is the published pets release, including the pet system preserved from release-13 development, the eight-pet Common collection, YouTube reliability fixes, and dashboard updates. The earlier pet development and deferral appear in the v13.1.8 history below; see [PR #370](https://github.com/Akaing1/RatsBoomBot/pull/370) and [PR #386](https://github.com/Akaing1/RatsBoomBot/pull/386).

### What's Changed
* Merge release 13 fixes into release 14 while preserving pets by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/375
* Fix YouTube chat watcher stopping after token refresh errors by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/376
* Fix dashboard labels, metadata sizing, and scrollbars by @minamichimaa in https://github.com/Akaing1/RatsBoomBot/pull/378
* Keep YouTube chat connected through token expiry and temporary failures by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/377
* Prevent YouTube account mixups during authorization and refresh by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/379
* Fix YouTube message parsing and reconnect interruptions by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/380
* Add Witch's Cat with Gamble Luck by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/381
* Add Dog of the Sun with Raid Profit by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/382
* Add Honey Hen with Loyalty Gain by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/383
* Fix pets UAT deployment and collection sprites; bump to 14.2.1 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/384
* Fix corrupted cat sprite and align pet cards (14.2.2) by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/385
* Release/14.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/386


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v13.1.9...v14.2.2

## [v13.1.9](https://github.com/Akaing1/RatsBoomBot/releases/tag/v13.1.9) — 2026-10-05

### What's Changed
* Fix raid attacks and payouts after pet deferral by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/374


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v13.1.8...v13.1.9

## [v13.1.8](https://github.com/Akaing1/RatsBoomBot/releases/tag/v13.1.8) — 2026-10-05

**Release scope clarification:** The generated history includes pet development PRs, but [PR #370](https://github.com/Akaing1/RatsBoomBot/pull/370) removed pet gameplay from this release and preserved it for release 14. Existing pet records and numbered migrations were retained. The list below is development history, not a claim that every intermediate feature shipped.

### What's Changed
* Add global pet proof of concept by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/318
* Fix deployed bat sprite path by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/319
* Add chatter sign-in and profile links for !stats and !me by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/320
* Show owner view on signed-in chatter profile URLs by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/321
* Send homepage sign-in to chatter profiles and cancel back home by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/322
* Center channel profile back link and remove duplicate account button by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/323
* Add per-channel raid shop in chatter profiles by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/324
* Add channel-specific Gamble tab to chatter profiles by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/325
* Let streamers enable raid bosses from the channel dashboard by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/335
* Add customizable main and mini boss names to channel dashboard by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/336
* Refactor RPG minigame and pets into root packages by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/337
* Give Boss Hunt its own streamer dashboard tab by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/338
* Refactor/root minigames 13 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/339
* Show current Boss Hunt leaderboard below encounter activity by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/340
* Add Explosive Rat and tiered pet passives by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/341
* Repair Explosive Rat seed on upgraded UAT databases by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/342
* Use approved Explosive Rat tail loop and rename Silly Bat by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/343
* Fix duplicate tails in Explosive Rat animation by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/344
* Use approved Explosive Rat redraw by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/345
* Refresh pet sprite when a new version deploys by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/346
* Give Explosive Rat a gentle breathing and blinking idle by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/347
* Add Sleepy Fox pet with breathing animation by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/348
* Add loyalty-point pet summon tickets and global collection by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/349
* Fix/update pet reply by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/350
* Move pets into a tab and summon by rarity pool by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/351
* Anchor and simplify pet Rates dropdown by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/352
* Use channel loyalty currency names in pet responses by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/353
* Update pet wording tests and keep equip responsive during slowmode by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/354
* Add Horned Wolf pet and four-frame profile sprite by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/355
* Control dashboard preview playback with Twitch player by @minamichimaa in https://github.com/Akaing1/RatsBoomBot/pull/356
* Update Horned Wolf with synced breathing and tail animation by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/357
* Refine Horned Wolf pixel art and idle animation by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/358
* Add Common Royal Raven with bonus raid rewards by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/359
* Fix Twitch preview visibility and require manual playback by @minamichimaa in https://github.com/Akaing1/RatsBoomBot/pull/360
* Disable Boss Hunt events and announcements when raid commands are disabled by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/362
* Fix mobile dashboard layout and card interactions by @minamichimaa in https://github.com/Akaing1/RatsBoomBot/pull/361
* Fix first mobile dashboard card transition by @minamichimaa in https://github.com/Akaing1/RatsBoomBot/pull/363
* Animate dashboard activity feeds and highlight new entries by @minamichimaa in https://github.com/Akaing1/RatsBoomBot/pull/366
* Add persistent user and message-type filters to combined chat by @minamichimaa in https://github.com/Akaing1/RatsBoomBot/pull/367
* Adapt mini-boss HP and spawn odds to raid results by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/368
* Feature/navigation hover labels by @minamichimaa in https://github.com/Akaing1/RatsBoomBot/pull/369
* Defer pets to release 14 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/370
* Improve chat composer and platform-specific filters by @minamichimaa in https://github.com/Akaing1/RatsBoomBot/pull/372
* Improve category picker artwork and search results by @minamichimaa in https://github.com/Akaing1/RatsBoomBot/pull/371
* Merge pull request #371 from Akaing1/feature/category-picker-improvements

Improve category picker artwork and search results by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/373


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v12.3.3...v13.1.8

## [v12.3.3](https://github.com/Akaing1/RatsBoomBot/releases/tag/v12.3.3) — 2026-09-28

### What's Changed
* Add global quotes command by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/315
* Reduce YouTube delay in shared chat by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/316
* Keep quote numbers contiguous after removal by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/317
* Show gamble win rate on channel and global chatter profiles by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/326
* Show gamble wins and losses on profile cards by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/327
* Handle passive point permission failures and YouTube quota exhaustion by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/328
* Fix responsive dashboard layout and navigation by @minamichimaa in https://github.com/Akaing1/RatsBoomBot/pull/329
* Restore viewer queue interactions after responsive dashboard merge by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/332
* Fix dashboard activity, mobile scrolling, and queue interactions by @minamichimaa in https://github.com/Akaing1/RatsBoomBot/pull/333
* Release/12.2.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/334


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v12.3.2...v12.3.3

## [v12.3.2](https://github.com/Akaing1/RatsBoomBot/releases/tag/v12.3.2) — 2026-09-25

### What's Changed
* Feature/dashboard responsive layout and mobile navigation by @minamichimaa in https://github.com/Akaing1/RatsBoomBot/pull/308
* Fix desktop dashboard stacking regression by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/309
* Add chat display controls and bump to v12.3.2 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/310
* Fix admin dashboard grid and darken chat command toggle by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/311
* Fix admin overview sizing at normal browser zoom by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/312
* Release/12.2.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/313


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v12.3.1...v12.3.2

## [v12.3.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v12.3.1) — 2026-09-22

### What's Changed
* Fix/desktop dashboard resolution by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/306
* Release/12.2.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/307


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v12.3.0...v12.3.1

## [v12.3.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v12.3.0) — 2026-09-22

### What's Changed
* Refresh public landing page by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/294
* Update landing dashboard preview by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/295
* Polish dashboard panels and stream title/category editing by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/296
* Standardize admin dashboard and add read-only chat by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/297
* Align admin channel dashboard and activity panels by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/298
* Align admin channel pages with dashboard layout by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/299
* Fix admin overview spacing and sidebar collapse sizing by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/300
* Feature/video player by @minamichimaa in https://github.com/Akaing1/RatsBoomBot/pull/301
* Fix/dashboard adjustments by @minamichimaa in https://github.com/Akaing1/RatsBoomBot/pull/302
* Merge pull request #302 from Akaing1/fix/dashboard-adjustments

Fix/dashboard adjustments by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/303
* Bump version to v12.3.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/304
* Release/12.2.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/305


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v12.2.1...v12.3.0

## [v12.2.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v12.2.1) — 2026-09-21

### What's Changed
* Add protected user dashboard management by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/288
* Normalize raid item command input by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/289
* Guide users to grouped gamble commands by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/291
* Expand League chat commands by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/292
* Release/12.2.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/293


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v12.2.0...v12.2.1

## [v12.2.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v12.2.0) — 2026-09-20

### What's Changed
* Standardize command metadata and globalize roulette by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/286
* Release/12.2.0 by @minamichimaa in https://github.com/Akaing1/RatsBoomBot/pull/287

### New Contributors
* @minamichimaa made their first contribution in https://github.com/Akaing1/RatsBoomBot/pull/287

**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v12.0.0...v12.2.0

## [v12.0.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v12.0.0) — 2026-09-20

### What's Changed
* v12.0.0: Add combined Twitch and YouTube chat dashboard by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/277
* Remove avatars from combined chat by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/278
* Hide cached chat avatar placeholders by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/279
* Add combined-chat replies and dashboard workspace by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/280
* Add combined-chat replies and dashboard workspace by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/281
* Fix offline chat replies and compact dashboard cards by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/282
* Fix chat API authorization and compact dashboard rows by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/283
* Refine dashboard chat input and activity filtering by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/284
* Release/12.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/285


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v11.6.5...v12.0.0

## [v11.6.5](https://github.com/Akaing1/RatsBoomBot/releases/tag/v11.6.5) — 2026-09-18

### What's Changed
* v11.6.5: Split community response feature toggles by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/275
* Release/11.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/276


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v11.6.4...v11.6.5

## [v11.6.4](https://github.com/Akaing1/RatsBoomBot/releases/tag/v11.6.4) — 2026-09-18

### What's Changed
* v11.6.4: Add configurable condensed gifted-sub responses by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/273
* Release/11.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/274


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v11.6.3...v11.6.4

## [v11.6.3](https://github.com/Akaing1/RatsBoomBot/releases/tag/v11.6.3) — 2026-09-18

### What's Changed
* v11.6.3: Currency defaults and channel-specific command aliases by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/271
* Release/11.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/272


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v11.6.2...v11.6.3

## [v11.6.2](https://github.com/Akaing1/RatsBoomBot/releases/tag/v11.6.2) — 2026-09-18

### What's Changed
* v11.6.2: Add command latency diagnostics for channel comparison by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/269
* Release/11.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/270


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v11.6.1...v11.6.2

## [v11.6.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v11.6.1) — 2026-09-18

### What's Changed
* v11.6.0: Shared viewer command slowmode by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/264
* v11.6.0: Add loyalty point name and response customization by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/265
* Fix standard commands for channels without code profiles by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/266
* v11.6.1: Simplify loyalty customization and default responses by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/267
* Release/11.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/268


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v11.5.3...v11.6.1

## [v11.5.3](https://github.com/Akaing1/RatsBoomBot/releases/tag/v11.5.3) — 2026-09-17

### What's Changed
* v11.5.3: Fix raid announcements and selling locks by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/262
* Release/11.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/263


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v11.5.2...v11.5.3

## [v11.5.2](https://github.com/Akaing1/RatsBoomBot/releases/tag/v11.5.2) — 2026-09-17

### What's Changed
* v11.5.0: Add global chatter levels and Twitch avatars by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/256
* v11.5.1: Fix chatter profiles and add project support by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/257
* Add Ko-fi support section to the landing page by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/258
* Move landing-page support panel below Discord by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/259
* v11.5.2: Count only first live measurement rolls by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/260
* Release/11.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/261


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v11.4.1...v11.5.2

## [v11.4.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v11.4.1) — 2026-09-17

### What's Changed
* v11.4.0: Reward raid progress and announce boss health checkpoints by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/253
* v11.4.1: Keep tutorial raids active until defeated by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/254
* Release/11.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/255


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v11.3.4...v11.4.1

## [v11.3.4](https://github.com/Akaing1/RatsBoomBot/releases/tag/v11.3.4) — 2026-09-16

### What's Changed
* Fix/milky raidboss names by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/251
* Release/11.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/252


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v11.3.3...v11.3.4

## [v11.3.3](https://github.com/Akaing1/RatsBoomBot/releases/tag/v11.3.3) — 2026-09-16

### What's Changed
* v11.3.3: Add Meinya's Overclocked weapon names by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/249
* Release/11.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/250


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v11.3.2...v11.3.3

## [v11.3.2](https://github.com/Akaing1/RatsBoomBot/releases/tag/v11.3.2) — 2026-09-16

### What's Changed
* Bump version to v11.3.2 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/248


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v11.3.1...v11.3.2

## [v11.3.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v11.3.1) — 2026-09-16

### What's Changed
* v11.3.0: Scale mini-boss HP by previous raid contributors by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/246
* Release/11.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/247


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v11.2.0...v11.3.1

## [v11.2.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v11.2.0) — 2026-09-15

### What's Changed
* v11.2.0: Community achievements by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/242
* Release/11.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/245


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v11.1.1...v11.2.0

## [v11.1.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v11.1.1) — 2026-09-15

### What's Changed
* remove override from meinya by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/244


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v11.1.0...v11.1.1

## [v11.1.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v11.1.0) — 2026-09-15

### What's Changed
* v11.1.0 — Secret command achievements and gambling streaks by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/241
* Release/11.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/243


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v11.0.0...v11.1.0

## [v11.0.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v11.0.0) — 2026-09-15

### What's Changed
* Add channel-specific achievements and rewards by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/239
* Release/11.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/240


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v10.0.3...v11.0.0

## [v10.0.3](https://github.com/Akaing1/RatsBoomBot/releases/tag/v10.0.3) — 2026-09-14

### What's Changed
* Flatten raid contribution payouts (10.0.3) by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/238


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v10.0.2...v10.0.3

## [v10.0.2](https://github.com/Akaing1/RatsBoomBot/releases/tag/v10.0.2) — 2026-09-14

### What's Changed
* Rebalance Ancient Pact (10.0.2) by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/236
* Release/10.0.2 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/237


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v10.0.1...v10.0.2

## [v10.0.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v10.0.1) — 2026-09-14

### What's Changed
* Render Markdown in patch note overview synopses (10.0.1) by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/234
* Release/10.0.1 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/235


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v10.0.0...v10.0.1

## [v10.0.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v10.0.0) — 2026-09-14

### What's Changed
* Add hidden achievements and global Blessed Unique weapons (10.0.0) by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/232
* Release/10.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/233


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v9.8.0...v10.0.0

## [v9.8.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v9.8.0) — 2026-09-14

### What's Changed
* Share one rotation for timer messages and announcements (9.8.0) by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/231


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v9.7.1...v9.8.0

## [v9.7.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v9.7.1) — 2026-09-13

### What's Changed
* Fix Milky basic weapon price and Valkyrie Boost name (9.7.1) by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/230


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v9.7.0...v9.7.1

## [v9.7.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v9.7.0) — 2026-09-13

### What's Changed
* Configure Milky raid loadout and customizable item names (9.7.0) by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/228


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v9.6.1...v9.7.0

## [v9.6.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v9.6.1) — 2026-09-13

### What's Changed
* Add global and channel viewer achievements (9.4.0) by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/221
* Polish achievement cards and filters (9.4.1) by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/222
* Center milestone requirements and categorize achievements (9.4.2) by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/223
* Add global points and gambling achievements (9.5.0) by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/224
* Add raid damage and purchase achievements (9.6.0) by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/225
* Fix purchase locking and make Familiar Face global (9.6.1) by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/226
* Release v9.6.1: viewer achievements and purchase fixes by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/227


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v9.3.4...v9.6.1

## [v9.3.4](https://github.com/Akaing1/RatsBoomBot/releases/tag/v9.3.4) — 2026-09-13

### What's Changed
* Handle accounts without ranked champion data (9.3.4) by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/219
* Release/9.3.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/220


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v9.3.3...v9.3.4

## [v9.3.3](https://github.com/Akaing1/RatsBoomBot/releases/tag/v9.3.3) — 2026-09-12

### What's Changed
* Persist refreshed OAuth tokens to the database by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/212
* v9.3.1: Simplify dashboard and add live raid summary by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/213
* v9.3.2: Clean up admin UI and limit total stream logs by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/214
* Move social-link setters into the !set command group by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/215
* Replace admin channel tabs with a Customization switch by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/216
* Fix League feature overrides and offline error visibility (9.3.3) by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/217
* Release/9.3.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/218


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v9.3.0...v9.3.3

## [v9.3.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v9.3.0) — 2026-09-12

### What's Changed
* Fix passive points and improve VIP authorization diagnostics by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/210
* Release/9.3.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/211


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v9.2.2...v9.3.0

## [v9.2.2](https://github.com/Akaing1/RatsBoomBot/releases/tag/v9.2.2) — 2026-09-12

### What's Changed
* Fix points command reward ordering by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/208
* Release/9.2.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/209


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v9.2.1...v9.2.2

## [v9.2.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v9.2.1) — 2026-09-10

### What's Changed
* Fix Meinya's Announcement to display correct youtube url by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/206
* Release/9.2.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/207


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v9.2.0...v9.2.1

## [v9.2.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v9.2.0) — 2026-09-10

### What's Changed
* Isolate the UAT Twitch adapter port by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/198
* Recover safely from invalid stored OAuth tokens by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/199
* Deploy release pull requests to UAT by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/200
* Show complete chatter raid inventory and placements by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/202
* Use chat defaults for blank bot scopes by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/203
* Prepare RatsBoomBot v9.2.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/204
* Release RatsBoomBot v9.2.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/205


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v9.1.0...v9.2.0

## [v9.1.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v9.1.0) — 2026-09-08

### What's Changed
* Add isolated UAT deployment environment by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/197


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v9.0.5...v9.1.0

## [v9.0.5](https://github.com/Akaing1/RatsBoomBot/releases/tag/v9.0.5) — 2026-09-08

### What's Changed
* Add basic weapon drops and weapon selling by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/196


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v9.0.4...v9.0.5

## [v9.0.4](https://github.com/Akaing1/RatsBoomBot/releases/tag/v9.0.4) — 2026-09-08

### What's Changed
* Rebalance recurring point earnings by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/195


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v9.0.3...v9.0.4

## [v9.0.3](https://github.com/Akaing1/RatsBoomBot/releases/tag/v9.0.3) — 2026-09-08

### What's Changed
* Release/9.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/194


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v9.0.2...v9.0.3

## [v9.0.2](https://github.com/Akaing1/RatsBoomBot/releases/tag/v9.0.2) — 2026-09-08

### What's Changed
* Release/9.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/193


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v9.0.1...v9.0.2

## [v9.0.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v9.0.1) — 2026-09-07

### What's Changed
* Add Blessed Unique raid weapons by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/191
* Release/9.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/192


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v9.0.0...v9.0.1

## [v9.0.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v9.0.0) — 2026-09-07

### What's Changed
* Fix/rpg patch bug fixes by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/183
* Track gambling losses for RatsBoomBot by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/184
* Add additive raid damage and ALL weapon support by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/185
* Add Lucky Dice and The Fool's Card by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/186
* Add Ancient Pact global raid buff by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/187
* Add Flag Bearer's Will raid buff by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/188
* Add Overclocked raid weapons and Overdrive by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/189
* Release/9.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/190


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.10.16...v9.0.0

## [v8.10.16](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.10.16) — 2026-09-07

### What's Changed
* Feature/vip and lurk update by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/181
* Feature/blessing and potions update by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/182


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.10.15...v8.10.16

## [v8.10.15](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.10.15) — 2026-09-05

### What's Changed
* Feature/vip and lurk update by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/180


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.10.14...v8.10.15

## [v8.10.14](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.10.14) — 2026-09-05

### What's Changed
* Fix raid rewards and add VIP redeem by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/179


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.10.13...v8.10.14

## [v8.10.13](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.10.13) — 2026-09-04

### What's Changed
* Add rank-based raid reward payouts by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/178


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.10.12...v8.10.13

## [v8.10.12](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.10.12) — 2026-09-04

### What's Changed
* Remove final-hit mythical drop roll by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/177


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.10.11...v8.10.12

## [v8.10.11](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.10.11) — 2026-09-04

### What's Changed
* Require active streams for raid buffs by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/176


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.10.10...v8.10.11

## [v8.10.10](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.10.10) — 2026-09-04

### What's Changed
* Scale cheer points by bits donated by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/175


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.10.9...v8.10.10

## [v8.10.9](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.10.9) — 2026-09-04

### What's Changed
* Add homepage Discord and business contact links by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/174


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.10.8...v8.10.9

## [v8.10.8](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.10.8) — 2026-09-04

### What's Changed
* Fix/default command bugfix by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/173


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.10.7...v8.10.8

## [v8.10.7](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.10.7) — 2026-09-04

### What's Changed
* Fix passive loyalty point payouts by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/172


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.10.6...v8.10.7

## [v8.10.6](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.10.6) — 2026-09-04

### What's Changed
* Feature/dashboard minor tweaks by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/171


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.10.5...v8.10.6

## [v8.10.5](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.10.5) — 2026-09-03

### What's Changed
* Minor dashboard and raid lifecycle tweaks by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/170


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.10.4...v8.10.5

## [v8.10.4](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.10.4) — 2026-09-03

### What's Changed
* Feature/dashboard minor tweaks by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/169


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.10.3...v8.10.4

## [v8.10.3](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.10.3) — 2026-09-03

### What's Changed
* Fix Patch Notes composer layout by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/168


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.10.2...v8.10.3

## [v8.10.2](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.10.2) — 2026-09-03

### What's Changed
* Fix Discord status updates on Raspberry Pi by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/167


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.10.1...v8.10.2

## [v8.10.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.10.1) — 2026-09-03

### What's Changed
* Fix Discord status updates and seed patch notes by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/166


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.10.0...v8.10.1

## [v8.10.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.10.0) — 2026-09-03

### What's Changed
* Add dashboard-managed patch notes by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/165


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.9.3...v8.10.0

## [v8.9.3](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.9.3) — 2026-09-03

### What's Changed
* Add persistent Discord bot status card by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/164


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.9.2...v8.9.3

## [v8.9.2](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.9.2) — 2026-09-03

### What's Changed
* Fix Discord deployment message formatting by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/163


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.9.1...v8.9.2

## [v8.9.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.9.1) — 2026-09-03

### What's Changed
* Notify Discord after production deployments by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/162


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.9.0...v8.9.1

## [v8.9.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.9.0) — 2026-09-03

### What's Changed
* Add curated homepage What’s New panel by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/161


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.8.3...v8.9.0

## [v8.8.3](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.8.3) — 2026-09-02

### What's Changed
* Simplify raid crafting commands by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/160


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.8.2...v8.8.3

## [v8.8.2](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.8.2) — 2026-09-02

### What's Changed
* Move loot lookup under raid commands by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/159


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.8.1...v8.8.2

## [v8.8.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.8.1) — 2026-09-02

### What's Changed
* Add raid unequip command and dedicated help routing by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/158


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.8.0...v8.8.1

## [v8.8.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.8.0) — 2026-09-02

### What's Changed
* Add raid crafting progression and combat buffs by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/157


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.7.2...v8.8.0

## [v8.7.2](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.7.2) — 2026-09-02

### What's Changed
* Align custom bot account controls by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/156


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.7.1...v8.7.2

## [v8.7.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.7.1) — 2026-09-02

### What's Changed
* Add one-time custom bot authorization links by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/155


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.7.0...v8.7.1

## [v8.7.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.7.0) — 2026-09-02

### What's Changed
* Add streamer-managed premium bot OAuth by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/154


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.6.1...v8.7.0

## [v8.6.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.6.1) — 2026-09-02

### What's Changed
* Fix public raid page history query by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/153


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.6.0...v8.6.1

## [v8.6.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.6.0) — 2026-09-02

### What's Changed
* Add public channel raid guides by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/152


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.5.3...v8.6.0

## [v8.5.3](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.5.3) — 2026-09-02

### What's Changed
* Move public Help route and collapse raid leaderboard by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/151


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.5.2...v8.5.3

## [v8.5.2](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.5.2) — 2026-09-02

### What's Changed
* Fix Ahriman cleanup and redesign public Help page by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/150


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.5.1...v8.5.2

## [v8.5.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.5.1) — 2026-09-01

### What's Changed
* Remove complete Ahirman test run and clarify raid leaderboard by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/149


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.5.0...v8.5.1

## [v8.5.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.5.0) — 2026-09-01

### What's Changed
* Add Meinya roulette and remove remaining test raid by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/148


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.4.0...v8.5.0

## [v8.4.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.4.0) — 2026-09-01

### What's Changed
* Polish chatter profiles and add passive point earnings by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/147


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.3.1...v8.4.0

## [v8.3.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.3.1) — 2026-09-01

### What's Changed
* Organize chatter profiles and expand raid stats by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/146


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.3.0...v8.3.1

## [v8.3.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.3.0) — 2026-09-01

### What's Changed
* Add public chatter profiles and statistics by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/145


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.2.3...v8.3.0

## [v8.2.3](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.2.3) — 2026-09-01

### What's Changed
* Remove dashboard restart control by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/144


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.2.2...v8.2.3

## [v8.2.2](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.2.2) — 2026-09-01

### What's Changed
* Prevent Bad Gateway during dashboard restarts by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/143


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.2.1...v8.2.2

## [v8.2.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.2.1) — 2026-08-31

### What's Changed
* Automate production deployment and improve dashboard restarts by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/142


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.2.0...v8.2.1

## [v8.2.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.2.0) — 2026-08-31

### What's Changed
* Add premium custom bot identities by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/141


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.1.2...v8.2.0

## [v8.1.2](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.1.2) — 2026-08-31

### What's Changed
* Invalidate cached stylesheets after deployments by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/140


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.1.1...v8.1.2

## [v8.1.1](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.1.1) — 2026-08-31

### What's Changed
* Expand timer settings card to full width by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/139


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.1.0...v8.1.1

## [v8.1.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.1.0) — 2026-08-31

### What's Changed
* Add moderator stream game and title commands by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/135
* Add streamer customization guardrails by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/136
* Add separate timer message editor by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/137
* Automate version validation and GitHub releases by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/138


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v8.0.0...v8.1.0

## [v8.0.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v8.0.0) — 2026-08-31

### RatsBoomBot v8.0.0 — Raid Bosses

RatsBoomBot v8.0.0 introduces a complete community raid-boss system alongside major improvements to channel onboarding, persistence, logging, announcements, dashboards, and game integrations.

This release includes all development since v6.0.0, including the League features that represented the internal v7.0.0 milestone.

### Raid Bosses

Viewers can now work together across multiple streams to defeat channel-themed bosses using loyalty points, weapons, consumables, and one attack per stream.

#### Boss progression

* Tutorial bosses introduce each community to the system.
* Mini bosses appear during normal progression.
* Main bosses gain an increasing chance to appear after three mini bosses and are guaranteed after five.
* Bosses persist across their configured number of streams.
* Each channel can define themed boss names, balance, rewards, and feature availability.
* Automatic bosses warn the channel 10 minutes before appearing and spawn 30 minutes after the stream starts.

#### Combat and equipment

* Base attacks with configurable damage.
* Melee, ranged, and magic weapon types.
* Type-matching weapon bonuses.
* Weapon durability and repairs.
* Power potions.
* Critical hits.
* Starter and unique weapon drops.
* Duplicate tutorial rewards reroll when possible.
* Viewers who already own every starter weapon receive a points reward instead.

#### Rewards and commands

* Contribution-based loyalty-point payouts.
* Final-hit bonuses.
* Top-contributor and unique-weapon reward chances.
* Raid leaderboards and encounter statistics.
* `!loot` shows a viewer’s earnings from their latest completed raid.
* Raid shop, inventory, equipment, potion, and repair commands.
* Successful defeats are delivered as green Twitch announcements.

#### Scheduling and announcements

* Boss spawn messages are sent as Twitch announcements from RatsBoomBot.
* Raid reminders begin 45 minutes after a boss appears and repeat every 60 minutes.
* Each reminder also requires 20 new channel messages, preventing reminders from interrupting inactive chats.
* Spawn deadlines, reminder deadlines, warning state, and chat progress persist through bot restarts.
* Announcement failures safely fall back to normal bot chat messages.

### League of Legends

The League milestone introduced:

* OP.GG-backed champion commands.
* Champion summaries and recent ranked-match information.
* Community League account registration.
* Rank and ladder tracking.
* Profile-controlled League integrations.
* Dedicated League database storage.
* League commands for the Barbatos profile.

### Channel and Profile Improvements

* Database-backed profile onboarding.
* Streamer-controlled integration toggles.
* Administrator controls for profile integrations.
* Additional channel profiles and custom commands.
* Profile-specific points commands and currency names.
* Profile-specific ad-warning messages.
* Ad countdowns formatted as minutes and seconds.
* Public command pages showing each channel’s currently enabled commands.
* A new public RatsBoomBot landing page.
* Improved dashboard help and customization pages.
* Private shared counters for selected channels.

### Persistence and Reliability

* Viewer queues now retain their open state, members, and order after restarts.
* Raid bosses, rewards, inventory, progression, and scheduler state are stored in SQLite.
* Added versioned migrations for persistent viewer queues and raid-boss storage.
* Stream sessions and channel logs resume after bot restarts.
* Deployment backups and rollback protection remain in place.
* Background raid and reminder tasks are safely cancelled or restored during service lifecycle changes.

### Logging and Moderation

* Runtime logs are focused on application and service health.
* Channel-specific activity is routed to persistent per-stream logs.
* Viewer-queue mutations are recorded as channel events.
* Sery_Bot moderation events now include the moderator, affected account, action, reason, duplicate status, and processing failures.
* Fixed Sery_Bot configuration loading so moderation events are no longer lost before logging.

### Additional Fixes

* Added support for `!points give` as a moderator points-award command.
* Improved outgoing raids and incoming raid responses.
* Improved shoutout targeting and queue behavior.
* Added safer profile and command feature controls.
* Expanded command-help coverage.
* Improved admin runtime controls and restart feedback.
* Added numerous regression tests covering raids, queues, profiles, moderation, points, dashboards, and announcements.

### Upgrade Notes

* Database migrations run automatically during startup.
* Deploy this release while configured channels are offline so all raid schedules begin under the new persistent scheduler.
* Existing viewer queues, raid progress, points, inventory, and OAuth data are preserved.
* Twitch announcements fall back to normal chat if announcement authorization is unavailable.

### Release Scope

This release contains 118 commits since v6.0.0 and represents the largest feature expansion since RatsBoomBot’s platform foundation.

**Full Changelog:** https://github.com/Akaing1/RatsBoomBot/compare/v6.0.0...v8.0.0

## [v6.0.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v6.0.0) — 2026-08-20

### What's Changed
* Release/4.0.0 local by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/27
* Release/4.3.3 local by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/35
* Release/5.3.6 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/38
* Feature/template profile by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/39
* Feature/meinyas features by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/40
* Feature/retry logic shoutouts by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/41
* Release/5.4.2 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/42
* update deploy version by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/43
* Release/5.4.2 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/44
* Feature/kamikaze update by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/45
* Release/5.4.4 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/46
* update meinya commands by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/47
* command name typo fix by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/48
* Feature/meinya commands by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/49
* db migration by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/50
* Feature/db migration by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/51
* init Milky_GalaxyVT profile by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/52
* Feature/milkygalaxyvt profile creation by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/53
* web app bug fix by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/54
* update channel dash by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/55
* add wxlfii command by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/56
* add wxlfii command by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/57
* connect milky profile by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/58
* Release/5.6.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/59
* Feature/setup milky profile by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/60
* bug fix - misimported feature by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/61
* Feature/redeem activity enhancement by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/62
* update css ref by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/63
* update admin dash - same change by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/64
* fix proportions by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/65
* update scroll by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/66
* Feature/major refactoring by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/67
* large scale refactor of services by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/68
* large scale refactor of redirect uri by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/69
* adding overwatch commands by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/70
* comment out req for testing by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/71
* fix typo by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/72
* uncomment out game check by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/73
* Feature/steohanyy profile setup by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/74
* add outgoing raid commands by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/75
* add clips functionality by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/76
* bug fix by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/77
* updating milkys profile by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/78
* updating milkys daily name by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/79
* Feature/finish init milky profile by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/80
* Feature/finish init milky profile by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/81
* set up dev account by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/82
* setting up dev acct by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/83
* add reklop first chat shoutout by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/84
* added logging enhancements by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/85
* change req to get instead of post by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/86
* MILKY BUG FIX by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/87
* fix logging by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/88
* Feature/logging enhancements by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/89
* Feature/logging enhancements by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/90
* Release/6.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/91
* update timeout by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/92
* Feature/qol updates by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/94
* fix username issue by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/95
* ad announcement update by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/96


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v5.3.6...v6.0.0

## [v5.3.6](https://github.com/Akaing1/RatsBoomBot/releases/tag/v5.3.6) — 2026-08-11

### RatsBoomBot v5.3.6 — First Official Release

RatsBoomBot is a multi-channel Twitch chatbot built with Python, TwitchIO, FastAPI, and SQLite. This release marks the first official, production-deployed version of the project.

### Features

* Multi-channel Twitch chat support
* Browser-based bot and broadcaster OAuth
* Channel-specific profiles, messages, commands, timers, and point themes
* Per-channel feature, command-group, and individual command controls
* Loyalty points, leaderboards, gambling, and viewer duels
* Viewer queues with moderator commands and dashboard controls
* Daily and first channel-point redeems
* Follow, subscription, raid, redeem, stream, and ad events
* Social-link commands and rotating announcements
* Persistent counters and per-stream text logs
* Shared commands for utilities, moderation, shoutouts, settings, and queues
* SQLite-backed tokens, settings, points, counters, redeems, and migrations
* Structured runtime logging and automated tests

### Web Dashboards

* Protected administrator dashboard
* Twitch-authenticated channel-owner dashboard
* Broadcaster connection and OAuth management
* Runtime, database, and connected-channel status
* Feature and command configuration
* Viewer-queue inspection and removal
* Stream-log browser
* Owner-managed administrator accounts
* Signed sessions, CSRF protection, secure cookies, and OAuth state validation

### Deployment

RatsBoomBot runs continuously on a Raspberry Pi as a systemd service. Its dashboard is publicly available through a secure Cloudflare Tunnel with HTTPS at:

https://dashboard.ratsboombot.com/

This release is currently intended for Ninjakaing and a small group of invited streamers. It is not yet a public, self-service bot platform.

## [v4.3.3](https://github.com/Akaing1/RatsBoomBot/releases/tag/v4.3.3) — 2026-08-06

### What's Changed
* Feature/bugfix kamikaze command by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/28
* Feature/bot detection by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/29
* Feature/shoutout queue by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/30
* shoutout queue update by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/31
* add enhancements to viewer q by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/32
* Feature/minor tweaks by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/33
* Feature/styling cleanup by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/34


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v3.0.0...v4.3.3

## [v3.0.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v3.0.0) — 2026-07-29

### What's Changed
* Feature/unit test suite by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/25
* Feature/db migration by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/26


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v2.0.0...v3.0.0

## [v2.0.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v2.0.0) — 2026-07-12

### What's Changed
* refactor so that discord and youtube are non global by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/21
* Feature/web auth init by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/22
* add stats to redeems by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/23
* Feature/detailed logging by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/24


**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/compare/v1.0.0...v2.0.0

## [v1.0.0](https://github.com/Akaing1/RatsBoomBot/releases/tag/v1.0.0) — 2026-07-08

### What's Changed
* duel commands added by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/1
* Feature/fun commands by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/2
* Feature/counter commands by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/3
* pull discord and yt info from env file. easier for other to configure by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/4
* created sub and follower messages by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/5
* Feature/kamikaze command by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/6
* enhanced bread command to allow you to see others bread stash by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/7
* Feature/revert start up changes by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/8
* Release/1.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/9
* Feature/broadcaster implementation by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/10
* Feature/viewer queue impl by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/11
* Feature/viewer queue impl by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/12
* Feature/redeem impl by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/13
* Feature/installation by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/14
* bug fix with kamikaze command by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/15
* working with subscriptions by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/16
* refactor points commands to non global by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/17
* refactored db subscriptions to be non global by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/18
* Release/1.0.0 by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/19
* Develop by @Akaing1 in https://github.com/Akaing1/RatsBoomBot/pull/20

### New Contributors
* @Akaing1 made their first contribution in https://github.com/Akaing1/RatsBoomBot/pull/1

**Full Changelog**: https://github.com/Akaing1/RatsBoomBot/commits/v1.0.0
