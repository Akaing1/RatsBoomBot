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
