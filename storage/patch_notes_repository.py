import asqlite

async def list_notes(db: asqlite.Pool, published_only: bool = False):
    where = "WHERE published_at IS NOT NULL" if published_only else ""
    async with db.acquire() as c: return await c.fetchall(f"SELECT * FROM patch_notes {where} ORDER BY COALESCE(published_at, created_at) DESC")

async def get_note(db: asqlite.Pool, slug: str):
    async with db.acquire() as c: return await c.fetchone("SELECT * FROM patch_notes WHERE slug = ?", (slug,))

async def save_note(db: asqlite.Pool, slug: str, title: str, synopsis: str, body: str) -> None:
    async with db.acquire() as c:
        await c.execute("INSERT INTO patch_notes (slug,title,synopsis,body) VALUES (?,?,?,?) ON CONFLICT(slug) DO UPDATE SET title=excluded.title,synopsis=excluded.synopsis,body=excluded.body,updated_at=CURRENT_TIMESTAMP", (slug,title,synopsis,body)); await c.commit()

async def publish_note(db: asqlite.Pool, slug: str, version: str) -> None:
    async with db.acquire() as c: await c.execute("UPDATE patch_notes SET version=?, published_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE slug=?", (version,slug)); await c.commit()


async def update_note(db, slug: str, title: str, synopsis: str, body: str) -> bool:
    async with db.acquire() as connection:
        await connection.execute(
            "UPDATE patch_notes SET title=?, synopsis=?, body=?, updated_at=CURRENT_TIMESTAMP WHERE slug=?",
            (title, synopsis, body, slug),
        )
        changed = (await connection.fetchone("SELECT changes()"))[0] > 0
        await connection.commit()
        return changed


async def delete_note(db, slug: str) -> bool:
    async with db.acquire() as connection:
        await connection.execute("DELETE FROM patch_notes WHERE slug=?", (slug,))
        changed = (await connection.fetchone("SELECT changes()"))[0] > 0
        await connection.commit()
        return changed


async def create_note(db, slug: str, title: str, synopsis: str, body: str) -> bool:
    async with db.acquire() as connection:
        await connection.execute(
            "INSERT OR IGNORE INTO patch_notes (slug,title,synopsis,body) VALUES (?,?,?,?)",
            (slug, title, synopsis, body),
        )
        created = (await connection.fetchone("SELECT changes()"))[0] > 0
        await connection.commit()
        return created
