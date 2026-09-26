import hashlib
import secrets
import time

from config.settings import settings


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_viewer_session(db, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    async with db.acquire() as connection:
        await connection.execute("DELETE FROM viewer_sessions WHERE expires_at <= ?", (now,))
        await connection.execute(
            "INSERT INTO viewer_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (_hash(token), str(user_id), now + settings.CHANNEL_SESSION_MAX_AGE_SECONDS),
        )
    return token


async def valid_viewer_session(db, user_id: str, token: str | None) -> bool:
    if not token:
        return False
    async with db.acquire() as connection:
        row = await connection.fetchone(
            "SELECT 1 FROM viewer_sessions WHERE token_hash = ? AND user_id = ? AND expires_at > ?",
            (_hash(token), str(user_id), int(time.time())),
        )
    return row is not None


async def claim_viewer_action(db, user_id: str, token: str, *, interval: int = 2) -> bool:
    now = int(time.time())
    async with db.acquire() as connection:
        row = await connection.fetchone(
            """UPDATE viewer_sessions SET last_action_at = ?
               WHERE token_hash = ? AND user_id = ? AND expires_at > ?
                 AND (last_action_at IS NULL OR last_action_at <= ?)
               RETURNING token_hash""",
            (now, _hash(token), str(user_id), now, now - interval),
        )
    return row is not None


async def revoke_viewer_session(db, token: str | None) -> None:
    if token:
        async with db.acquire() as connection:
            await connection.execute("DELETE FROM viewer_sessions WHERE token_hash = ?", (_hash(token),))
