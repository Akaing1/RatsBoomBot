# Database migrations

The runner applies one global sequence to SQLite before services start. Feature folders organize ownership; they do not create independent databases or independent version counters.

| Folder | Ownership |
| --- | --- |
| `storage/migrations/core/` | Shared schema, channel settings, identities, queues, quotes, patch notes, sessions, raid browser |
| `storage/migrations/loyalty/` | Loyalty payouts, reward events, gambling totals and outcomes |
| `storage/migrations/achievements/` | Achievement schema and seeds |
| `storage/migrations/boss_hunts/` | Boss Hunt progression, crafting, rewards and historical repairs |
| `storage/migrations/pets/` | Pet catalog, ownership, passives, summons and repairs |

Each folder explicitly registers its migrations in `__init__.py`. The public registry at `storage/migrations/__init__.py` combines these lists and sorts by global version. Existing `MIGRATIONS` and `Migration` imports remain supported. Direct imports of historical migration modules now use their feature folder.

## Adding a migration

1. Check the latest target release branch and open migration PRs. Agree on the next global number in the PR before implementation; a number in an unmerged branch is only a proposed reservation. Never assign separate numbering per feature.
2. Add `vNNN_descriptive_name.py` to the owning folder with `async def migrate(connection)`. Register `Migration(NNN, "descriptive_name", migrate_function)` in that folder's `__init__.py`. Keep each feature list in version order.
3. Use the supplied connection for all SQL. The runner owns `BEGIN`, history insertion, commit and rollback; migration code must not commit, start its own transaction, or call external services. Keep historical SQL self-contained instead of importing mutable service logic.
4. Add upgrade tests with representative existing data, plus failure/rollback coverage for destructive transformations. Test a fresh database and a second startup. Run `python -m pytest -q tests/test_migration_registry.py tests/test_honey_hen.py` and affected feature tests.
5. Recheck numbering against the target branch before merging. If another PR used the proposed number, renumber only the migration that has never shipped or run on a shared database. Resolve deployed collisions with a new forward repair migration, never by editing recorded history.
6. Update the changelog and application version. Describe data changes and deployment requirements in the PR.

Registry validation rejects duplicate versions, gaps and invalid ordering before the runner opens the database. Tests also catch migration files omitted from registration. The runner refuses unknown database versions, gaps in applied history and unexpected names before applying pending work. These errors require a compatible application or a reviewed recovery, not deletion of history rows. The known version-64 `incoming_raid_recency` collision remains explicitly accepted because migration 66 repairs it without rewriting its history.

## Upgrades and recovery

Back up the database before deploying schema changes. Each migration and its history row commit together. A failed or cancelled migration rolls back; earlier successful migrations stay applied. Fix the failure and restart to resume. Application rollback is not schema rollback: if an older release does not understand the current schema, restore a matching backup or deploy a compatible forward fix.

Do not squash, rename or renumber applied migrations. Versions 1–67 retain their original identities and SQL behavior after the folder reorganization. A future baseline would need an explicit supported upgrade cutoff, verified schema/data equivalence, and a bridge for existing installations; simply deleting old files breaks that path.

## Remaining schema ownership work

Some service setup methods still create tables or transform legacy schemas. In particular, `PointsService._migrate_viewers_table_if_needed` converts the old shared viewers table. Move these transformations into new numbered migrations in a separate, tested change: cover both legacy and current table shapes and verify balances, identifiers and totals survive. Do not remove service setup SQL until every supported upgrade path and standalone service test uses the migration runner. New schema changes belong in numbered migrations.
