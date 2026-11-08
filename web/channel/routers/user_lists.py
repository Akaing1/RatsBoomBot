"""Portable user lists for the signed-in channel's console helpers."""
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from bot.profiles import get_active_profile
from web.admin.auth import validate_csrf_token
from web.channel.api_context import resolve_channel_api_context
from web.channel.auth import settings_actor
from web.state import get_bot

router = APIRouter()
LIST_KEYS = {'automaticShoutouts': 'automatic_shoutouts.users', 'incomingRaidBlacklist': 'automatic_shoutouts.blacklist'}
ALL_LISTS = {*LIST_KEYS, 'queueBlacklist'}


def exported_lists(context):
    profile = get_active_profile(str(context.broadcaster_id))
    if profile is None:
        raise ValueError('Channel settings are unavailable.')
    config = profile.automatic_shoutouts
    return {'automaticShoutouts': sorted(config.users.split()), 'incomingRaidBlacklist': sorted(config.blacklist.split()),
            'queueBlacklist': context.services.viewer_queue.list_blacklist(str(context.broadcaster_id))}


@router.get('/channel/api/user-lists')
async def export_user_lists(request: Request):
    context = resolve_channel_api_context(request, get_bot)
    if isinstance(context, JSONResponse):
        return context
    try:
        lists = exported_lists(context)
    except ValueError as error:
        return JSONResponse({'detail': str(error)}, status_code=503)
    return JSONResponse({'version': 1, 'channelId': str(context.broadcaster_id), 'lists': lists}, headers={'Cache-Control': 'no-store'})


@router.post('/channel/api/user-lists')
async def import_user_lists(request: Request):
    context = resolve_channel_api_context(request, get_bot)
    if isinstance(context, JSONResponse):
        return context
    validate_csrf_token(request, request.headers.get('X-CSRF-Token', ''))
    try:
        payload = await request.json()
        if not isinstance(payload, dict) or type(payload.get('version')) is not int or payload['version'] != 1:
            raise ValueError('Use a version 1 user-list export.')
        channel_id = str(context.broadcaster_id)
        if payload.get('channelId') != channel_id:
            raise ValueError('This export belongs to a different Twitch channel.')
        lists = payload.get('lists')
        replace = payload.get('replace', False)
        if not isinstance(lists, dict) or not lists or not lists.keys() <= ALL_LISTS or not isinstance(replace, bool):
            raise ValueError('Supply supported lists and a boolean replace option.')
        normalized = {}
        for name, users in lists.items():
            if not isinstance(users, list) or len(users) > (100 if name != 'queueBlacklist' else 1000):
                raise ValueError(f'{name} has too many entries or is not a list.')
            if any(not isinstance(user, str) or not re.fullmatch(r'[a-zA-Z0-9_]{1,25}', user) for user in users):
                raise ValueError(f'{name} contains an invalid Twitch username.')
            normalized[name] = sorted(set(user.casefold() for user in users))
        current = exported_lists(context)
        # Validate the merged lists before making any changes.
        for name in LIST_KEYS:
            if name in normalized and len(set(normalized[name]) | (set() if replace else set(current[name]))) > 100:
                raise ValueError(f'{name} supports up to 100 users after merging.')
        values = {LIST_KEYS[name]: users for name, users in normalized.items() if name in LIST_KEYS}
        if values:
            await context.services.profile_settings.import_automatic_shoutout_lists(channel_id, values, replace, settings_actor(request))
        if 'queueBlacklist' in normalized:
            queue = context.services.viewer_queue
            existing, incoming = set(queue.list_blacklist(channel_id)), set(normalized['queueBlacklist'])
            for user in sorted(incoming - existing):
                await queue.add_to_blacklist(channel_id, user)
            if replace:
                for user in sorted(existing - incoming):
                    await queue.remove_from_blacklist(channel_id, user)
    except (ValueError, TypeError) as error:
        return JSONResponse({'detail': str(error)}, status_code=400)
    return JSONResponse({'version': 1, 'channelId': channel_id, 'lists': exported_lists(context)}, headers={'Cache-Control': 'no-store'})
