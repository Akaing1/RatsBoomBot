"""Check the connected streamer's current grant against the OAuth request scopes."""
import httpx

from config.settings import settings


async def missing_channel_scopes(bot, channel_id: str) -> list[str]:
    required = set(settings.CHANNEL_SCOPES.split())
    token = (getattr(bot, 'tokens', {}).get(channel_id) or {}).get('token')
    if not token:
        return sorted(required)
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.get('https://id.twitch.tv/oauth2/validate', headers={'Authorization': f'OAuth {token}'})
    if response.status_code == 401:
        return sorted(required)
    response.raise_for_status()
    grant = response.json()
    if str(grant.get('user_id', '')) != channel_id or grant.get('client_id') != settings.CLIENT_ID:
        return sorted(required)
    scopes = grant.get('scopes')
    if not isinstance(scopes, list) or not all(isinstance(scope, str) for scope in scopes):
        raise ValueError('Invalid Twitch authorization response')
    return sorted(required - set(scopes))
