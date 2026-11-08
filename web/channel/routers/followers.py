"""Follower-only directory. All Twitch and local reads use the signed-in channel."""
import asyncio
import logging
import math
import re
import time

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from twitchio.http import Route

from bot.shared.follower_names import ensure_follower_names, follower_names_state
from storage.followers import follower_metrics
from bot.profiles import get_active_profile
from web.admin.auth import get_csrf_token, validate_csrf_token
from web.channel.api_context import resolve_channel_api_context
from web.channel.auth import CHANNEL_USER_ID_KEY, settings_actor
from web.channel.routers.dashboard import raid_browser_cached_profiles, raid_browser_profiles, raid_browser_cached_request
from web.shared.common import templates
from web.state import get_bot, get_db

router = APIRouter()
LOGGER = logging.getLogger('RatBoomBot')
SORTS = {'name', 'roles', 'followed_at', 'points', 'label', 'messages', 'lifetime_points', 'watch_minutes', 'first_seen', 'last_seen', 'last_watched', 'first_redeems', 'check_ins', 'achievement_count', 'points_spent', 'raid_favorite', 'automatic_shoutout'}
RANKS = {'mod', 'vip', 'subscriber', 'tier1', 'tier2', 'tier3', 'partner'}
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
                snapshot.update(followers=list(unique.values()), follower_ids=set(unique))
        cursor = payload.get('pagination', {}).get('cursor')
        if not cursor:
            return rows, total
        if cursor in cursors:
            raise ValueError('Twitch returned a repeated page. Please try again later.')
        cursors.add(cursor)


async def load_snapshot(bot, channel_id, snapshot, *, refresh_followers=False):
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
    following_task = start_following_load(bot, channel_id, snapshot)
    if following_task:
        role_tasks.append(following_task)
    try:
        names = follower_names_state(bot, channel_id)
        if not refresh_followers and names['task'] and not names['loaded']:
            await asyncio.shield(names['task'])
        if not refresh_followers and names['loaded']:
            followers = list(names['users'].values())
            total = len(followers)
            snapshot.update(loaded=total)
        else:
            before = dict(names['users'])
            followers, total = await collect(bot, channel_id, 'channels/followers', snapshot, publish_pages=not previous[0])
            during_load = {key: row for key, row in names['users'].items() if before.get(key) is not row}
            names['users'] = {**{str(row['user_id']): row for row in followers}, **during_load}
            names['loaded'] = True
            names['refreshed'] = time.monotonic()
            followers = list(names['users'].values())
            total = max(total, len(followers))
        unique = {str(item['user_id']): item for item in followers}
        snapshot.update(followers=list(unique.values()), follower_ids=set(unique), total=total, error='')
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
        names = getattr(bot, '_follower_names_cache', {}).get(channel_id, {})
        known = list(names.get('users', {}).values())
        cache[channel_id] = dict(followers=known, follower_ids={str(row['user_id']) for row in known}, roles={}, total=len(known), loaded=len(known), refreshed=0,
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


def start_following_load(bot, channel_id, snapshot):
    if time.monotonic() < snapshot['following_expires']:
        return None
    task = snapshot.get('following_task')
    if task is None or task.done():
        task = snapshot['following_task'] = asyncio.create_task(cached_following(bot, channel_id, snapshot))
    return task


@router.get('/channel/followers')
async def followers_page(request: Request):
    if not request.session.get(CHANNEL_USER_ID_KEY):
        return RedirectResponse('/connect', status_code=303)
    context = resolve_channel_api_context(request, get_bot)
    if isinstance(context, JSONResponse):
        return RedirectResponse('/channel', status_code=303)
    ensure_follower_names(context.runtime_bot, str(context.broadcaster_id))
    return templates.TemplateResponse(request=request, name='channel/followers.html', context={
        'active_page': 'followers', 'broadcaster': context.broadcaster, 'channel_id': str(context.broadcaster_id), 'csrf_token': get_csrf_token(request)})


def shoutout_config(channel_id):
    profile = get_active_profile(channel_id)
    config = profile.automatic_shoutouts if profile else None
    return config if config and (config.interactions or config.raid) else None


@router.post('/channel/api/followers/automatic-shoutout')
async def update_follower_shoutout(request: Request, user_id: str = Form(...), enabled: bool = Form(...), csrf_token: str = Form(...)):
    context = resolve_channel_api_context(request, get_bot)
    if isinstance(context, JSONResponse):
        return context
    validate_csrf_token(request, csrf_token)
    channel_id = str(context.broadcaster_id)
    if not shoutout_config(channel_id):
        return JSONResponse({'detail': 'Enable automatic shoutouts in settings first.'}, status_code=409)
    snapshot = getattr(context.runtime_bot, '_followers_directory_cache', {}).get(channel_id)
    member = next((row for row in snapshot['followers'] if str(row['user_id']) == user_id), None) if snapshot else None
    if member is None or not member.get('user_login'):
        return JSONResponse({'detail': 'Load this follower before changing automatic shoutouts.'}, status_code=404)
    try:
        await context.services.profile_settings.set_automatic_shoutout_user(channel_id, member['user_login'], enabled, settings_actor(request))
    except ValueError as error:
        return JSONResponse({'detail': str(error)}, status_code=400)
    return JSONResponse({'enabled': enabled}, headers={'Cache-Control': 'no-store'})


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
    try:
        profiles = await raid_browser_profiles(bot, channel_id, channels, strict=True)
    except Exception:
        return JSONResponse({'detail': 'Profile pictures are temporarily unavailable.'}, status_code=503)
    return JSONResponse({'profiles': [{'id': user_id, 'profile_image_url': str(profiles.get(user_id, {}).get('profile_image_url') or ''),
        'is_partner': profiles.get(user_id, {}).get('broadcaster_type') == 'partner'}
        for user_id in user_ids]}, headers={'Cache-Control': 'no-store'})


def start_partner_load(bot, channel_id, snapshot):
    task = snapshot.get('partner_task')
    if task and not task.done():
        return task
    if snapshot['loading']:
        return None
    if time.monotonic() < snapshot.get('partner_expires', 0) and (snapshot.get('partner_error') or all(
            str(row['user_id']) in snapshot.get('partner_checked', ()) for row in snapshot['followers'])):
        return None
    members = list(snapshot['followers'])
    async def load():
        try:
            partners = {}
            for offset in range(0, len(members), 100):
                batch = [{'id': str(row['user_id'])} for row in members[offset:offset + 100]]
                profiles = await raid_browser_profiles(bot, channel_id, batch, strict=True)
                partners.update({user_id: profile for user_id, profile in profiles.items() if profile.get('broadcaster_type') == 'partner'})
            snapshot['roles'] = {**snapshot['roles'], 'partner': partners}
            snapshot.update(partner_error='', partner_expires=time.monotonic() + 86400,
                            partner_checked={str(row['user_id']) for row in members})
        except Exception:
            LOGGER.warning('[Followers] Partner status unavailable for %s.', channel_id, exc_info=True)
            snapshot.update(partner_error='Partner status is temporarily unavailable. Please try again shortly.', partner_expires=time.monotonic() + 60)
    snapshot['partner_task'] = asyncio.create_task(load())
    return snapshot['partner_task']


@router.get('/channel/api/followers')
async def followers_api(request: Request, page: int = Query(1, ge=1), page_size: int = Query(25),
        sort: str = 'followed_at', direction: str = 'desc', search: str = Query('', max_length=100),
        rank: list[str] | None = Query(None), mutual: bool = False, refresh: bool = False,
        raid_favorites: bool = False, favorites: str = Query('', max_length=2600), automatic_shoutouts: bool = False):
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
    ensure_follower_names(bot, channel_id)
    snapshot = snapshot_for(bot, channel_id)
    age = time.monotonic() - snapshot['refreshed']
    if not snapshot['loading'] and (not snapshot['refreshed'] or age >= 300 or (refresh and age >= 30)):
        snapshot.update(loading=True, loaded=len(snapshot['followers']), error='', warnings=[])
        if refresh:
            snapshot['metrics_at'] = 0
        names = follower_names_state(bot, channel_id)
        refresh_names = (refresh and age >= 30) or (names['loaded'] and time.monotonic() - names.get('refreshed', 0) >= 86400)
        snapshot['task'] = asyncio.create_task(load_snapshot(bot, channel_id, snapshot, refresh_followers=refresh_names))
    followers = snapshot['followers']
    following_task = start_following_load(bot, channel_id, snapshot)
    if following_task and (mutual or sort in {'roles', 'label'}):
        await asyncio.shield(following_task)
    async with snapshot['metrics_lock']:
        expired = not snapshot['metrics_at'] or time.monotonic() - snapshot['metrics_at'] >= 15
        metric_ids = [str(item['user_id']) for item in followers if expired or str(item['user_id']) not in snapshot['metrics']]
        if metric_ids:
            metrics = await follower_metrics(db, channel_id, metric_ids)
            snapshot['metrics'] = metrics if expired else {**snapshot['metrics'], **metrics}
            snapshot['metrics_generation'] += 1
            if expired:
                snapshot['metrics_at'] = time.monotonic()
    roles = snapshot['roles']
    partner_task = start_partner_load(bot, channel_id, snapshot) if 'partner' in selected_roles else None
    if 'partner' in selected_roles and snapshot.get('partner_error') and not partner_task:
        return JSONResponse({'detail': snapshot['partner_error']}, status_code=503)
    if not snapshot['loading'] and any(roles.get('subscriber' if role.startswith('tier') else role) is None for role in selected_roles - {'partner'}):
        return JSONResponse({'detail': 'This roles filter is unavailable until Twitch role data can be loaded.'}, status_code=503)
    followed_ids = snapshot['following_ids']
    following_warning = snapshot['following_error']
    if mutual and following_warning:
        return JSONResponse({'detail': following_warning}, status_code=503)
    profiles, _ = raid_browser_cached_profiles(bot, channel_id, [{'id': str(row['user_id'])} for row in followers])
    partner_ids = set(roles.get('partner') or ())
    for user_id, profile in profiles.items():
        if profile.get('broadcaster_type') == 'partner':
            partner_ids.add(user_id)
        else:
            partner_ids.discard(user_id)
    partner_known = set(profiles) | set(snapshot.get('partner_checked', ()))
    config = shoutout_config(channel_id)
    shoutout_users = frozenset(config.users.casefold().split()) if config else frozenset()
    generation = (id(followers), id(roles), snapshot['metrics_generation'], snapshot['following_expires'], frozenset(partner_ids), frozenset(partner_known), shoutout_users)
    if snapshot.get('table_generation') != generation:
        snapshot.update(table_generation=generation, table_results={})
    options = (sort, direction, search.casefold(), frozenset(selected_roles), mutual, raid_favorites, frozenset(favorite_ids), automatic_shoutouts)
    cached_rows = snapshot['table_results'].get(options)
    if cached_rows is None:
        cached_rows = build_table_rows(followers, snapshot['metrics'], roles, followed_ids, selected_roles,
            favorite_ids, mutual, raid_favorites, search.casefold(), sort, direction, partner_ids, partner_known, shoutout_users, automatic_shoutouts)
        if len(snapshot['table_results']) >= 4:
            snapshot['table_results'].pop(next(iter(snapshot['table_results'])))
        snapshot['table_results'][options] = cached_rows
    pages = max(1, math.ceil(len(cached_rows) / page_size)); page = min(page, pages)
    warnings = list(snapshot['warnings'])
    if following_warning:
        warnings.append(following_warning)
    return JSONResponse(dict(rows=cached_rows[(page - 1) * page_size:page * page_size], page=page, pages=pages,
        count=len(cached_rows), total=snapshot['total'], loading=snapshot['loading'] or bool(partner_task and not partner_task.done()) or bool(following_task and not following_task.done()) or followers is not snapshot['followers'] or roles is not snapshot['roles'], loaded=snapshot['loaded'],
        error=snapshot['error'], warnings=warnings, automatic_shoutouts_enabled=config is not None), headers={'Cache-Control': 'no-store'})


def build_table_rows(followers, metrics, roles, followed_ids, selected_roles, favorite_ids,
        mutual, raid_favorites, search_text, sort, direction, partner_ids=(), partner_known=(), shoutout_users=(), automatic_shoutouts=False):
    """Filter and sort once per data generation; paging only slices the result."""
    rows = []
    for follower in followers:
        user_id = str(follower['user_id'])
        whitelisted = follower.get('user_login', '').casefold() in shoutout_users
        if automatic_shoutouts and not whitelisted:
            continue
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
        if user_id in partner_ids:
            ranks.append('partner')
            labels.append('Partner')
        row = dict(metrics.get(user_id, {}), user_id=user_id, login=follower.get('user_login', ''),
            name=follower.get('user_name') or follower.get('user_login', ''), followed_at=follower.get('followed_at'),
            ranks=ranks, role_labels=labels, label=' · '.join(labels) or 'Follower', raid_favorite=user_id in favorite_ids,
            is_partner=(user_id in partner_ids) if user_id in partner_ids or user_id in partner_known else None, automatic_shoutout=whitelisted)
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
