# Feature package boundaries

Loyalty points and viewer queues are optional product features, alongside pets and Boss Hunts. Their service implementations live in top-level Python packages within this repository. They share the application's database and deployment; they are not separately installed distributions or separate services.

| Package | Public API | Owns |
| --- | --- | --- |
| `loyalty` | `PointsService`, `PassivePointsService`, `PendingDuel` | Channel balances, transfers, earning bonuses, gambling, duels, reward tracking, passive stream payouts |
| `viewer_queue` | `ViewerQueueService`, `ViewerQueueState` | Channel queue membership/order, open state, display names, blacklist, persistence |
| `pets` | `PetService` | Global pet ownership, summons, equipment, passives |
| `rpg_minigame` | `RaidBossService` and configuration types | Boss Hunt encounters, inventory, crafting, loot, progression |

## Integration

`bot/services/container.py` imports feature services from their package roots and constructs them with the existing shared dependencies. The service attributes remain `points`, `passive_points`, `viewer_queue`, `pets`, and `raid_bosses`. Existing startup/shutdown ordering and feature switches are unchanged.

Twitch command adapters remain in `bot/shared/commands/`; channel overrides remain in `bot/channels/`. Stream/chat events and dashboard routes use the container's services. Put new feature behavior in the owning package and keep these integrations focused on input, permissions, and presentation.

Loyalty still uses shared channel profiles, application settings, TwitchIO, and the supplied bot/database, chatter-stats, pet, chat-identity, and feature-toggle dependencies. Viewer queue uses the supplied bot/database and SQLite persistence. This extraction establishes ownership within the application; it does not make loyalty an independent framework or remove its integration dependencies. Achievements retain their current location for now.

Import services from `loyalty` or `viewer_queue` in new application code. Implementation-specific tests can import `loyalty.service`, `loyalty.passive`, or `viewer_queue.service`. The former `bot.services.engagement.points`, `passive_points`, and `viewer_queue` modules and their engagement-package re-exports are removed; update external scripts that used those internal imports.

## Database ownership

All packages use the single migration runner and global migration history. Existing migrations remain in `storage/migrations/` with unchanged versions and registration. Loyalty migrations are already grouped under `storage/migrations/loyalty/`; existing viewer queue migrations remain in `storage/migrations/core/`. Moving a service does not require a database migration or reset.

The legacy viewers conversion and table creation in loyalty setup are unchanged by this extraction. Moving them into numbered migrations remains a separate task with data-preservation tests; see [the migration guide](migrations.md).

## Validation

Run the existing points, passive-points, viewer-queue, and integration tests after changing these packages. Verify rewards from pets/Boss Hunts and achievements as well as direct commands: these features share loyalty services. Check imports and service-container wiring when moving code, including module paths patched by tests.
