async def migrate(connection):
    await connection.execute("UPDATE pet_passive_definitions SET max_bps = 750 WHERE id = 'gamble_odds'")
