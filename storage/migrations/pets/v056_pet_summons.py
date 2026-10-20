"""Global summon tickets with channel-local payment and refund provenance."""


async def migrate(connection) -> None:
    await connection.execute("""
        CREATE TABLE pet_summon_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            broadcaster_id TEXT NOT NULL,
            purchased_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await connection.execute("CREATE INDEX pet_tickets_owner ON pet_summon_tickets(user_id, id)")
    await connection.execute("UPDATE pet_definitions SET rarity = 'rare' WHERE id = 'explosive_rat'")
    await connection.execute("UPDATE pet_definitions SET rarity = 'ultra_rare' WHERE id = 'sleepy_fox'")
