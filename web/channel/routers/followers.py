"""Follower-only directory. All Twitch and local reads use the signed-in channel."""
import asyncio
import logging
import math
import re
import time

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from twitchio.http import Route

from storage.followers import follower_metrics
from web.admin.auth import get_csrf_token
from web.channel.api_context import resolve_channel_api_context
from web.channel.auth import CHANNEL_USER_ID_KEY
from web.channel.routers.dashboard import raid_browser_cached_profiles, raid_browser_profiles, raid_browser_cached_request
from web.shared.common import templates
from web.state import get_bot, get_db

router = APIRouter()
LOGGER = logging.getLogger('RatBoomBot')
SORTS = {'name', 'roles', 'followed_at', 'points', 'label', 'messages', 'lifetime_points', 'watch_minutes', 'first_seen', 'last_seen', 'last_watched', 'first_redeems', 'check_ins', 'achievement_count', 'points_spent', 'raid_favorite'}
RANKS = {'mod', 'vip', 'subscriber', 'tier1', 'tier2', 'tier3'}
ROLE_PATHS = {'mod': 'moderation/moderators', 'vip': 'channels/vips', 'subscriber': 'subscriptions'}


async def collect(bot, channel_id, path, snapshot=None, *, publish_pages=False):
    rows, cursors, cursor = [], set(), None
    total = 0
    while True:
        params = {'broadcaster_id': channel_id, 'first': 100}
        if cursor:
            params['after'] = cursor
        payload = await asyncio.wait_for(bot._http.request_json(Route('GET', path, token_for=channel_id, params=params)), 20)
        data = payload.get('data', [])
        total = int(payload.get('total', len(rows) + len(data)))
        if path == 'channels/followers' and total and not data and not rows:
            raise ValueError('Reconnect Twitch with permission to read followers.')
        rows.extend(data)
        if snapshot is not None:
            snapshot.update(loaded=len(rows), total=total)
            if publish_pages:
                unique = {str(item['user_id']): item for item in rows}
                snapshot.update(followers=list(unique.values()), follower_ids=set(unique), metrics_at=0)
        cursor = payload.get('pagination', {}).get('cursor')
        if not cursor:
            return rows, total
        if cursor in cursors:
            raise ValueError('Twitch returned a repeated page. Please try again later.')
        cursors.add(cursor)


async def load_snapshot(bot, channel_id, snapshot):
    previous = (snapshot['followers'], snapshot['follower_ids'], snapshot['total'])
    async def load_role(role, path):
        try:
            entries, _ = await collect(bot, channel_id, path)
            members = {str(item['user_id']): item for item in entries}
        except Exception:
            members = None
            snapshot['warnings'].append(f'{role.title()} data unavailable. Reconnect Twitch to grant access, or try refreshing later.')
        snapshot['roles'] = {**snapshot['roles'], role: members}
    role_tasks = [asyncio.create_task(load_role(role, path)) for role, path in ROLE_PATHS.items()]
    try:
        followers, total = await collect(bot, channel_id, 'channels/followers', snapshot, publish_pages=not previous[0])
        unique = {str(item['user_id']): item for item in followers}
        snapshot.update(followers=list(unique.values()), follower_ids=set(unique), total=total, error='', metrics_at=0)
    except Exception as error:
        LOGGER.warning('[Followers] Directory load failed for %s (%s).', channel_id, type(error).__name__)
        snapshot['error'] = ('Reconnect Twitch to grant access to your follower list.'
            if getattr(error, 'status', None) in {401, 403} else str(error) if isinstance(error, ValueError)
            else 'Followers could not be refreshed. Please try again shortly.')
        snapshot.update(followers=previous[0], follower_ids=previous[1], total=previous[2], metrics_at=0)
        for task in role_tasks:
            task.cancel()
    finally:
        await asyncio.gather(*role_tasks, return_exceptions=True)
        snapshot.update(loading=False, refreshed=time.monotonic())


async def followed_channel_ids(bot, channel_id):
    """Include offline channels; reuse the daily following cache and in-flight requests."""
    user_ids, cursors, cursor = set(), set(), None
    while True:
        params = {'user_id': channel_id, 'first': 100}
        if cursor:
            params['after'] = cursor
        payload = await asyncio.wait_for(raid_browser_cached_request(bot, channel_id, 'channels/followed', params), 20)
        user_ids.update(str(item['broadcaster_id']) for item in payload.get('data', []))
        cursor = payload.get('pagination', {}).get('cursor')
        if not cursor:
            return user_ids
        if cursor in cursors:
            raise ValueError('Twitch returned a repeated following page.')
        cursors.add(cursor)


def snapshot_for(bot, channel_id):
    cache = getattr(bot, '_followers_directory_cache', None)
    if cache is None:
        cache = bot._followers_directory_cache = {}
    if channel_id not in cache:
        for key in list(cache):
            if not cache[key]['loading'] and time.monotonic() - cache[key]['refreshed'] > 600:
                del cache[key]
        cache[channel_id] = dict(followers=[], follower_ids=set(), roles={}, total=0, loaded=0, refreshed=0,
            loading=False, warnings=[], error='', metrics_at=0, metrics_generation=0, metrics={}, metrics_lock=asyncio.Lock(),
            following_ids=set(), following_error='', following_expires=0, following_lock=asyncio.Lock())
    return cache[channel_id]


async def cached_following(bot, channel_id, snapshot):
    """Reuse parsed IDs briefly; Twitch responses retain their shared daily cache."""
    async with snapshot['following_lock']:
        if time.monotonic() >= snapshot['following_expires']:
            try:
                ids = await followed_channel_ids(bot, channel_id)
            except Exception as error:
                detail = ('Reconnect Twitch to enable mutual followers.' if getattr(error, 'status', None) in {401, 403}
                    else 'Mutual followers are temporarily unavailable. Please try again shortly.')
                snapshot.update(following_ids=set(), following_error=detail, following_expires=time.monotonic() + 30)
            else:
                snapshot.update(following_ids=ids, following_error='', following_expires=time.monotonic() + 60)
    return snapshot['following_ids'], snapshot['following_error']


@router.get('/channel/followers')
async def followers_page(request: Request):
    if not request.session.get(CHANNEL_USER_ID_KEY):
        return RedirectResponse('/connect', status_code=303)
    context = resolve_channel_api_context(request, get_bot)
    if isinstance(context, JSONResponse):
        return RedirectResponse('/channel', status_code=303)
    return templates.TemplateResponse(request=request, name='channel/followers.html', context={
        'active_page': 'followers', 'broadcaster': context.broadcaster, 'channel_id': str(context.broadcaster_id), 'csrf_token': get_csrf_token(request)})


@router.get('/channel/api/followers/profiles')
async def follower_profiles(request: Request, ids: str = Query('', max_length=2600)):
    context = resolve_channel_api_context(request, get_bot)
    if isinstance(context, JSONResponse):
        return context
    user_ids = list(dict.fromkeys(ids.split(',')))
    if not 1 <= len(user_ids) <= 100 or any(not re.fullmatch(r'[0-9]{1,25}', user_id) for user_id in user_ids):
        return JSONResponse({'detail': 'Supply up to 100 follower IDs.'}, status_code=400)
    channel_id, bot = str(context.broadcaster_id), context.runtime_bot
    snapshot = getattr(bot, '_followers_directory_cache', {}).get(channel_id)
    if snapshot is None or not set(user_ids) <= snapshot['follower_ids']:
        return JSONResponse({'detail': 'Load this channel’s followers before requesting their pictures.'}, status_code=403)
    channels = [{'id': user_id} for user_id in user_ids]
    profiles = await raid_browser_profiles(bot, channel_id, channels)
    _, missing = raid_browser_cached_profiles(bot, channel_id, channels)
    if missing:
        return JSONResponse({'detail': 'Profile pictures are temporarily unavailable.'}, status_code=503)
    return JSONResponse({'profiles': [{'id': user_id, 'profile_image_url': str(profiles.get(user_id, {}).get('profile_image_url') or '')}
        for user_id in user_ids]}, headers={'Cache-Control': 'no-store'})


@router.get('/channel/api/followers')
async def followers_api(request: Request, page: int = Query(1, ge=1), page_size: int = Query(25),
        sort: str = 'followed_at', direction: str = 'desc', search: str = Query('', max_length=100),
        rank: list[str] | None = Query(None), mutual: bool = False, refresh: bool = False,
        raid_favorites: bool = False, favorites: str = Query('', max_length=2600)):
    context = resolve_channel_api_context(request, get_bot)
    if isinstance(context, JSONResponse):
        return context
    selected_roles = set(rank or []) - {''}
    favorite_ids = set(favorites.split(',')) if favorites else set()
    if len(favorite_ids) > 100 or any(not re.fullmatch(r'[0-9]{1,25}', value) for value in favorite_ids):
        return JSONResponse({'detail': 'Invalid raid favorites.'}, status_code=400)
    if page_size not in {10, 25, 50, 100} or sort not in SORTS or direction not in {'asc', 'desc'} or not selected_roles <= RANKS:
        return JSONResponse({'detail': 'Invalid table options.'}, status_code=400)
    db = get_db()
    if db is None:
        return JSONResponse({'detail': 'Follower statistics are temporarily unavailable.'}, status_code=503)
    channel_id, bot = str(context.broadcaster_id), context.runtime_bot
    snapshot = snapshot_for(bot, channel_id)
    age = time.monotonic() - snapshot['refreshed']
    if not snapshot['loading'] and (not snapshot['refreshed'] or age >= 300 or (refresh and age >= 30)):
        snapshot.update(loading=True, loaded=0, error='', warnings=[])
        snapshot['task'] = asyncio.create_task(load_snapshot(bot, channel_id, snapshot))
    followers = snapshot['followers']
    roles = snapshot['roles']
    if not snapshot['loading'] and any(roles.get('subscriber' if role.startswith('tier') else role) is None for role in selected_roles):
        return JSONResponse({'detail': 'This roles filter is unavailable until Twitch role data can be loaded.'}, status_code=503)
    followed_ids = set()
    following_warning = ''
    if followers:
        followed_ids, following_warning = await cached_following(bot, channel_id, snapshot)
        if mutual and following_warning:
            return JSONResponse({'detail': following_warning}, status_code=503)
    async with snapshot['metrics_lock']:
        if followers and time.monotonic() - snapshot['metrics_at'] >= 15:
            snapshot['metrics'] = await follower_metrics(db, channel_id, [str(item['user_id']) for item in followers])
            snapshot['metrics_generation'] += 1
            snapshot['metrics_at'] = time.monotonic() if followers is snapshot['followers'] else 0
    generation = (id(followers), id(roles), snapshot['metrics_generation'], snapshot['following_expires'])
    if snapshot.get('table_generation') != generation:
        snapshot.update(table_generation=generation, table_results={})
    options = (sort, direction, search.casefold(), frozenset(selected_roles), mutual, raid_favorites, frozenset(favorite_ids))
    cached_rows = snapshot['table_results'].get(options)
    if cached_rows is None:
        cached_rows = build_table_rows(followers, snapshot['metrics'], roles, followed_ids, selected_roles,
            favorite_ids, mutual, raid_favorites, search.casefold(), sort, direction)
        if len(snapshot['table_results']) >= 4:
            snapshot['table_results'].pop(next(iter(snapshot['table_results'])))
        snapshot['table_results'][options] = cached_rows
    pages = max(1, math.ceil(len(cached_rows) / page_size)); page = min(page, pages)
    warnings = list(snapshot['warnings'])
    if following_warning:
        warnings.append(following_warning)
    return JSONResponse(dict(rows=cached_rows[(page - 1) * page_size:page * page_size], page=page, pages=pages,
        count=len(cached_rows), total=snapshot['total'], loading=snapshot['loading'], loaded=snapshot['loaded'],
        error=snapshot['error'], warnings=warnings), headers={'Cache-Control': 'no-store'})


def build_table_rows(followers, metrics, roles, followed_ids, selected_roles, favorite_ids,
        mutual, raid_favorites, search_text, sort, direction):
    """Filter and sort once per data generation; paging only slices the result."""
    rows = []
    for follower in followers:
        user_id = str(follower['user_id'])
        if (raid_favorites and user_id not in favorite_ids) or (mutual and user_id not in followed_ids):
            continue
        labels, ranks = [], []
        for role, text in [('mod', 'Mod'), ('vip', 'VIP'), ('subscriber', 'Subscriber')]:
            members = roles.get(role)
            if members is not None and user_id in members:
                ranks.append(role)
                if role == 'subscriber':
                    tier = str(members[user_id].get('tier', ''))
                    if tier in {'1000', '2000', '3000'}:
                        ranks.append(f'tier{tier[0]}'); text = f'Sub tier {tier[0]}'
                labels.append(text)
        if user_id in followed_ids:
            ranks.append('mutual')
            labels.append('Mutual')
        row = dict(metrics.get(user_id, {}), user_id=user_id, login=follower.get('user_login', ''),
            name=follower.get('user_name') or follower.get('user_login', ''), followed_at=follower.get('followed_at'),
            ranks=ranks, role_labels=labels, label=' · '.join(labels) or 'Follower', raid_favorite=user_id in favorite_ids)
        if selected_roles and not selected_roles.intersection(ranks):
            continue
        if search_text and search_text not in f"{row['name']} {row['login']} {row['label']}".casefold():
            continue
        rows.append(row)
    rows.sort(key=lambda row: (row['name'].casefold(), row['user_id']))
    if sort == 'roles':
        rows.sort(key=lambda row: (len(row['role_labels']), *(role in row['ranks'] for role in ('mod', 'vip', 'mutual', 'tier3', 'tier2', 'tier1'))), reverse=direction == 'desc')
        return rows
    present = [row for row in rows if row.get(sort) is not None]
    missing = [row for row in rows if row.get(sort) is None]
    present.sort(key=lambda row: row[sort].casefold() if isinstance(row[sort], str) else row[sort], reverse=direction == 'desc')
    return present + missing
