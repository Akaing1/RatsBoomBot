async def migrate(connection):
    await connection.execute("UPDATE pet_passive_definitions SET max_bps = 1500 WHERE id = 'loyalty_gain'")
    await connection.execute("""
        CREATE TABLE pet_loyalty_remainders (
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            remainder INTEGER NOT NULL CHECK (remainder BETWEEN 0 AND 9999),
            PRIMARY KEY (broadcaster_id, user_id)
        )
    """)
