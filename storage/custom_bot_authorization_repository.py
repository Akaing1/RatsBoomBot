import hashlib
import secrets
from dataclasses import dataclass


AUTHORIZATION_LIFETIME_MINUTES = 15


@dataclass(frozen=True)
class CustomBotAuthorizationRequest:
    broadcaster_id: str
    expected_bot_user_id: str
    expected_bot_login: str
    expected_bot_display_name: str


def hash_authorization_state(state: str) -> str:
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


async def create_custom_bot_authorization_request(db, broadcaster_id: str, bot_user_id: str, bot_login: str, bot_display_name: str) -> str:
    state = f"custom_bot_{secrets.token_urlsafe(32)}"
    state_hash = hash_authorization_state(state)

    async with db.acquire() as connection:
        await connection.execute("DELETE FROM custom_bot_authorization_requests WHERE broadcaster_id = ? OR expires_at <= CURRENT_TIMESTAMP", (str(broadcaster_id),))
        await connection.execute(
            """
            INSERT INTO custom_bot_authorization_requests (
                state_hash, broadcaster_id, expected_bot_user_id, expected_bot_login,
                expected_bot_display_name, expires_at
            )
            VALUES (?, ?, ?, ?, ?, datetime('now', ?))
            """,
            (state_hash, str(broadcaster_id), str(bot_user_id), bot_login.lower(), bot_display_name, f"+{AUTHORIZATION_LIFETIME_MINUTES} minutes")
        )

    return state


async def get_custom_bot_authorization_request(db, state: str | None) -> CustomBotAuthorizationRequest | None:
    if not state:
        return None

    async with db.acquire() as connection:
        row = await connection.fetchone(
            """
            SELECT broadcaster_id, expected_bot_user_id, expected_bot_login, expected_bot_display_name
            FROM custom_bot_authorization_requests
            WHERE state_hash = ? AND used_at IS NULL AND expires_at > CURRENT_TIMESTAMP
            """,
            (hash_authorization_state(state),)
        )

    if row is None:
        return None

    return CustomBotAuthorizationRequest(
        broadcaster_id=str(row["broadcaster_id"]),
        expected_bot_user_id=str(row["expected_bot_user_id"]),
        expected_bot_login=str(row["expected_bot_login"]),
        expected_bot_display_name=str(row["expected_bot_display_name"])
    )


async def consume_custom_bot_authorization_request(db, state: str | None) -> CustomBotAuthorizationRequest | None:
    request = await get_custom_bot_authorization_request(db, state)

    if request is None or state is None:
        return None

    async with db.acquire() as connection:
        await connection.execute(
            """
            UPDATE custom_bot_authorization_requests
            SET used_at = CURRENT_TIMESTAMP
            WHERE state_hash = ? AND used_at IS NULL AND expires_at > CURRENT_TIMESTAMP
            """,
            (hash_authorization_state(state),)
        )
        changed = await connection.fetchone("SELECT changes() AS count")

    return request if int(changed["count"]) == 1 else None
