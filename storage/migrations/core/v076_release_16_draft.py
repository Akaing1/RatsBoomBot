"""Seed the combined release notes as an unpublished, editable admin draft."""
from pathlib import Path

SLUG = "pets-raids-and-your-community-dashboard"
TITLE = "Pets, raids, and your community dashboard"
SYNOPSIS = "Catch up on pets and raid discovery, then explore refreshed profiles, moderator dashboards, For You, and simpler settings in our combined v15–16 update."


async def migrate(connection) -> None:
    body = (Path(__file__).resolve().parents[3] / "docs" / "release_16_community_dashboard.md").read_text(encoding="utf-8")
    await connection.execute(
        "INSERT OR IGNORE INTO patch_notes (slug, title, synopsis, body, version) VALUES (?, ?, ?, ?, ?)",
        (SLUG, TITLE, SYNOPSIS, body.partition("\n\n")[2], "16.1.24"),
    )
