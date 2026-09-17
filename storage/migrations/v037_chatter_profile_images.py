"""Cache Twitch profile images used by public chatter profiles."""


async def migrate(connection):
    await connection.execute("ALTER TABLE chatter_identities ADD COLUMN profile_image_url TEXT")
    await connection.execute("ALTER TABLE chatter_identities ADD COLUMN profile_image_updated_at TEXT")
