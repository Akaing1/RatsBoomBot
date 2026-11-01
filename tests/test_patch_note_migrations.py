import asqlite
import pytest

from storage.migrations.core.v021_patch_notes import migrate as create_patch_notes
from storage.migrations.core.v045_unpublish_test_patch_note import migrate as unpublish_test_patch_note


@pytest.mark.asyncio
async def test_test_patch_note_is_unpublished_without_being_deleted(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "patch-notes.db")) as database:
        async with database.acquire() as connection:
            await create_patch_notes(connection)
            await connection.execute(
                """
                INSERT INTO patch_notes (slug, title, synopsis, body, published_at)
                VALUES ('test-patch-notes', 'Test', 'Test synopsis', 'Test body', CURRENT_TIMESTAMP)
                """
            )

            await unpublish_test_patch_note(connection)

            row = await connection.fetchone(
                "SELECT slug, published_at FROM patch_notes WHERE slug = 'test-patch-notes'"
            )

    assert row is not None
    assert row["slug"] == "test-patch-notes"
    assert row["published_at"] is None


@pytest.mark.asyncio
async def test_release_16_notes_remain_a_draft_and_preserve_admin_edits(tmp_path):
    from storage.migrations.core.v076_release_16_draft import migrate, SLUG
    async with asqlite.create_pool(str(tmp_path / "release.db")) as db:
        async with db.acquire() as connection:
            await create_patch_notes(connection)
            await migrate(connection)
            row = await connection.fetchone("SELECT * FROM patch_notes WHERE slug = ?", (SLUG,))
            assert row["published_at"] is None
            assert row["discord_announced_at"] is None
            assert "## Pets join the community" in row["body"]
            assert "## Find your next raid" in row["body"]
            await connection.execute("UPDATE patch_notes SET body = 'Admin edits' WHERE slug = ?", (SLUG,))
            await migrate(connection)
            row = await connection.fetchone("SELECT body FROM patch_notes WHERE slug = ?", (SLUG,))
            assert row["body"] == "Admin edits"
