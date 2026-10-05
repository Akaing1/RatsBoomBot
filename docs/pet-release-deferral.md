# Pets deferred to release 14

`release/14.0.0` preserves the pet implementation and all five sprite assets from release 13 before this removal. Continue pet work there.

Release 13 removes pet commands, service wiring, profile UI, assets, grant tooling and all gameplay bonuses. Existing numbered migrations remain unchanged to preserve schema history and UAT ownership, loadouts and paid tickets; they do not enable any pet gameplay. Do not delete these tables or renumber/reuse migrations.

When integrating release 13 fixes into release 14, explicitly restore the pet-removal commit after merging, while keeping unrelated fixes. A normal merge would otherwise carry the removal into release 14. Keep release 14's application version and pet tests. Validate both an existing UAT database and a fresh database before shipping pets.
