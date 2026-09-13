from contextlib import asynccontextmanager


@asynccontextmanager
async def immediate_transaction(connection):
    # Reserve the writer before reading balances: a deferred read snapshot
    # cannot always be upgraded after another connection commits a write.
    await connection.execute("BEGIN IMMEDIATE")
    try:
        yield
        await connection.commit()
    except BaseException:
        await connection.rollback()
        raise
