async def is_new_streamer(db, broadcaster_id):
    async with db.acquire() as connection:
        row = await connection.fetchone("SELECT 1 FROM tokens WHERE user_id = ?", (broadcaster_id,))
    return row is None


async def initialize_setup(db, broadcaster_id):
    async with db.acquire() as connection:
        await connection.execute(
            "INSERT OR IGNORE INTO streamer_setup (broadcaster_id) VALUES (?)",
            (broadcaster_id,),
        )


async def get_setup(db, broadcaster_id):
    if db is None:
        return None
    async with db.acquire() as connection:
        return await connection.fetchone("SELECT * FROM streamer_setup WHERE broadcaster_id = ?", (broadcaster_id,))


async def save_setup(db, current, *, step, status, moderator_confirmed, command_confirmed):
    async with db.acquire() as connection:
        await connection.execute(
            """UPDATE streamer_setup
               SET step = ?, status = ?, moderator_confirmed = ?, command_confirmed = ?
               WHERE broadcaster_id = ? AND step = ? AND status = ?
                 AND moderator_confirmed = ? AND command_confirmed = ?""",
            (step, status, moderator_confirmed, command_confirmed, current["broadcaster_id"],
             current["step"], current["status"], current["moderator_confirmed"], current["command_confirmed"]),
        )
