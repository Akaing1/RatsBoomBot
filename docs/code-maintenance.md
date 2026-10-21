# Code maintenance review

This pass compared Python function bodies for exact duplication (functions of at least 12 lines), inspected repeated dashboard request checks, and ranked large functions. Historical migrations were excluded from deduplication: their independence preserves upgrade behavior.

## Consolidated in 15.1.2

- `bot/shared/commands/helpers.py` owns broadcaster resolution, chatter lookup, moderator/broadcaster checks, and permission-denial logging. Channel components, settings, viewer queue, and shoutouts reuse it. Existing public helper names and component methods still resolve, avoiding unnecessary caller changes.
- `web/channel/api_context.py` owns the shared session/runtime/connected-channel checks for seven dashboard JSON read endpoints. Existing 401/503/404 responses, error text, and disconnected-channel session cleanup remain unchanged. The runtime provider is passed explicitly so request-time resolution and test substitution still work.
- Contract tests cover fallback lookup order, moderator/owner permissions, missing context, and error behavior for every migrated read endpoint.

## Next focused refactors

| Location | Finding | Suggested boundary |
| --- | --- | --- |
| `web/channel/routers/dashboard.py`, `channel_raid_browser` | Roughly 400 lines combining discovery, filtering, ranking, caching, and response assembly | Extract discovery/ranking helpers with fixtures for the current ordering and pagination behavior |
| `rpg_minigame/service.py`, `_attack` | Roughly 280 lines combining combat calculation, persistence, rewards, and messages | Separate pure combat calculations first; retain transaction boundaries and payout tests |
| `bot/shared/commands/mod_actions.py`, `kamikaze` | Roughly 200 lines mixing permissions, protection rules, random outcomes, and moderation calls | Extract outcome/rule evaluation without changing moderator restoration behavior |
| `loyalty/service.py`, `setup` and `_migrate_viewers_table_if_needed` | Service startup still owns schema creation and legacy conversion | Move to numbered migrations after testing legacy/current shapes and balance preservation |
| Remaining dashboard write and streaming routes | Similar-looking guards have different CSRF, logout, and response behavior | Migrate only after documenting each contract; do not mechanically replace all guards |

Large functions are maintenance hotspots, not proof of a bug. Likewise, similar SQL or command handlers can encode different rules. Prefer consolidating behavior with matching contracts over reducing line counts alone. Keep future fixes incremental and run affected integration tests plus CI before merging.
