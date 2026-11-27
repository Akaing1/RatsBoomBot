"""Track the latest global watch interval credited to a viewer's pet."""


async def migrate(connection):
    await connection.execute("ALTER TABLE user_pet_loadouts ADD COLUMN last_xp_interval INTEGER")
