import asyncio
import json
from dataclasses import asdict, replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import asqlite
import pytest
from starlette.requests import Request

from bot.profiles import AutomaticShoutouts, ChannelProfile, FirstChatShoutout, activate_profile, clear_profiles
from bot.services.channels.profile_settings import ProfileSettingsService, PROFILE_SETTINGS_BY_KEY
from bot.services.stream import automatic_shoutouts as module
from bot.services.stream.automatic_shoutouts import AutomaticShoutoutService
from bot.services.stream.first_chat_shoutouts import FirstChatShoutoutService
from bot.services.stream.shoutouts import ShoutoutService


@pytest.fixture
def env():
    clear_profiles()
    shoutouts = SimpleNamespace(enqueue=Mock(return_value=(True, "queued", 1)), send_chat_message=AsyncMock(return_value=True))
    bot = SimpleNamespace(bot_id="999", _http=SimpleNamespace(request_json=AsyncMock()), services=SimpleNamespace(
        features=SimpleNamespace(is_enabled=Mock(return_value=True)),
        chat_identity=SimpleNamespace(sender_id=lambda channel: "998")))
    service = AutomaticShoutoutService(bot, shoutouts)
    bot.services.automatic_shoutouts = service
    seen = set()
    async def mark_seen(*, broadcaster_id, stream_id, user_id, username):
        key = (broadcaster_id, stream_id, user_id)
        if key in seen:
            return False
        seen.add(key)
        return True
    async def forget_seen(*, broadcaster_id, stream_id, user_id):
        seen.discard((broadcaster_id, stream_id, user_id))
    bot.services.first_chat_shoutouts = SimpleNamespace(get_live_stream_id=AsyncMock(return_value='stream-1'),
        mark_seen=AsyncMock(side_effect=mark_seen), forget_seen=AsyncMock(side_effect=forget_seen))
    def configure(**values):
        config = replace(AutomaticShoutouts(), **{'users': 'alice', **values})
        activate_profile("1", ChannelProfile(channel_name="owner", automatic_shoutouts=config))
        return config
    configure()
    yield bot, service, shoutouts, configure
    clear_profiles()


@pytest.mark.asyncio
@pytest.mark.parametrize("trigger", ["raid", "chat", "redeem", "subscription", "gift", "bits", "streak"])
async def test_each_enabled_trigger_uses_shared_outputs(env, trigger):
    bot, service, shoutouts, configure = env
    configure(**{trigger: 1})
    assert await service.handle("1", "2", "alice", trigger, 10)
    shoutouts.enqueue.assert_called_once_with(broadcaster_id="1", user_id="2", username="alice", requested_by=f"auto:{trigger}")
    assert shoutouts.send_chat_message.await_count == 1
    bot._http.request_json.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "following", "partner", "team", "list"])
async def test_all_selected_requirements_must_match(env, failure):
    bot, service, shoutouts, configure = env
    configure(require_following=1, require_partner=1, require_team=1, require_list=1, users="bob" if failure == "list" else "alice")
    async def response(route):
        if route.path == "channels/followed":
            assert route.params == {"user_id": "1", "broadcaster_id": "2"}
            return {"data": [] if failure == "following" else [{"broadcaster_id": "2"}]}
        if route.path == "users":
            return {"data": [{"id": "2", "broadcaster_type": "affiliate" if failure == "partner" else "partner"}]}
        return {"data": [{"id": "other" if failure == "team" and route.params["broadcaster_id"] == "2" else "shared"}]}
    bot._http.request_json.side_effect = response
    assert await service.handle("1", "2", "alice", "raid", 10) is (failure is None)
    assert shoutouts.enqueue.call_count == (0 if failure else 1)


@pytest.mark.asyncio
async def test_blacklist_overrides_list_and_does_not_fetch_metadata(env):
    bot, service, shoutouts, configure = env
    configure(require_list=1, users="alice", require_partner=1, blacklist="ALICE")
    assert not await service.handle("1", "2", "alice", "raid", 100)
    bot._http.request_json.assert_not_awaited()
    shoutouts.enqueue.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('trigger', ['chat', 'redeem', 'subscription', 'gift', 'bits', 'streak'])
async def test_whitelist_interactions_ignore_raid_requirements_and_blacklist(env, trigger):
    bot, service, shoutouts, configure = env
    configure(**{trigger: 1}, users='ALICE', blacklist='alice', require_following=1, require_partner=1, require_team=1)
    assert await service.handle('1', '2', 'alice', trigger, 100)
    bot._http.request_json.assert_not_awaited()
    shoutouts.enqueue.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('trigger', ['chat', 'redeem', 'subscription', 'gift', 'bits', 'streak'])
async def test_interaction_requires_whitelist_membership_even_with_no_raid_requirements(env, trigger):
    bot, service, shoutouts, configure = env
    configure(**{trigger: 1}, users='bob')
    assert not await service.handle('1', '2', 'alice', trigger, 100)
    bot._http.request_json.assert_not_awaited()
    bot.services.first_chat_shoutouts.get_live_stream_id.assert_not_awaited()
    shoutouts.enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_raid_does_not_require_whitelist_unless_selected(env):
    _, service, _, configure = env
    configure(users='')
    assert await service.handle('1', '2', 'alice', 'raid', 20)


@pytest.mark.asyncio
@pytest.mark.parametrize('first,second', [('raid', 'chat'), ('chat', 'raid')])
async def test_raid_and_whitelist_share_once_per_stream_limit(env, first, second):
    _, service, shoutouts, configure = env
    configure(chat=1)
    assert await service.handle('1', '2', 'alice', first, 20)
    assert not await service.handle('1', '2', 'alice', second, 20)
    assert shoutouts.send_chat_message.await_count == 1


@pytest.mark.asyncio
async def test_failed_delivery_releases_stream_reservation(env):
    bot, service, shoutouts, configure = env
    configure(chat=1, native=0)
    shoutouts.send_chat_message.return_value = False
    assert not await service.handle('1', '2', 'alice', 'chat')
    bot.services.first_chat_shoutouts.forget_seen.assert_awaited_once()
    shoutouts.send_chat_message.return_value = True
    assert await service.handle('1', '2', 'alice', 'chat')


@pytest.mark.asyncio
async def test_once_per_stream_marker_survives_restart_and_resets_for_new_stream(env, tmp_path):
    bot, service, shoutouts, configure = env
    configure(chat=1)
    logs = SimpleNamespace(active_sessions={'1': SimpleNamespace(stream_id='stream-1')})
    async with asqlite.create_pool(str(tmp_path / 'markers.db')) as db:
        markers = FirstChatShoutoutService(bot, db, shoutouts, logs)
        await markers.setup()
        bot.services.first_chat_shoutouts = markers
        assert await service.handle('1', '2', 'alice', 'raid', 20)
        restarted = AutomaticShoutoutService(bot, shoutouts)
        assert not await restarted.handle('1', '2', 'alice', 'chat')
        logs.active_sessions['1'] = SimpleNamespace(stream_id='stream-2')
        assert await restarted.handle('1', '2', 'alice', 'chat')
        assert not await restarted.handle('1', '2', 'alice', 'raid', 20)
    assert shoutouts.send_chat_message.await_count == 2


@pytest.mark.asyncio
async def test_no_live_stream_does_not_reserve_or_send(env):
    bot, service, shoutouts, configure = env
    configure(chat=1)
    bot.services.first_chat_shoutouts.get_live_stream_id.return_value = None
    assert not await service.handle('1', '2', 'alice', 'chat')
    bot.services.first_chat_shoutouts.mark_seen.assert_not_awaited()
    shoutouts.enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_thresholds_and_once_per_stream_across_triggers(env, monkeypatch):
    bot, service, shoutouts, configure = env
    now = [10.0]
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: now[0]))
    configure(minimum_viewers=10)
    assert not await service.handle("1", "2", "alice", "raid", 9)
    # A raid viewer threshold does not exclude eligible chatters.
    assert await service.handle("1", "2", "alice", "chat")
    assert not await service.handle("1", "2", "alice", "raid", 10)
    now[0] += 3600
    assert not await service.handle("1", "2", "alice", "bits", 100)
    bot.services.first_chat_shoutouts.get_live_stream_id.return_value = 'stream-2'
    assert await service.handle("1", "2", "alice", "bits", 100)
    assert shoutouts.enqueue.call_count == 2


@pytest.mark.asyncio
async def test_metadata_reads_are_cached_and_shared(env):
    bot, service, _, configure = env
    config = configure(require_partner=1)
    bot._http.request_json.return_value = {"data": [{"broadcaster_type": "partner"}]}
    assert all(await asyncio.gather(*(service.eligible("1", "2", "alice", config) for _ in range(5))))
    assert bot._http.request_json.await_count == 1
    assert await service.eligible("1", "2", "alice", config)
    assert bot._http.request_json.await_count == 1


@pytest.mark.asyncio
async def test_lookup_failure_is_closed_and_briefly_cached(env):
    bot, service, shoutouts, configure = env
    configure(require_partner=1)
    bot._http.request_json.side_effect = RuntimeError("unavailable")
    assert not await service.handle("1", "2", "alice", "raid", 10)
    assert not await service.handle("1", "2", "alice", "raid", 10)
    assert bot._http.request_json.await_count == 1
    shoutouts.enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_settings_changed_during_lookup_cancel_the_shoutout(env):
    bot, service, shoutouts, configure = env
    configure(require_partner=1)
    started, release = asyncio.Event(), asyncio.Event()
    async def lookup(route):
        started.set(); await release.wait()
        return {"data": [{"broadcaster_type": "partner"}]}
    bot._http.request_json.side_effect = lookup
    task = asyncio.create_task(service.handle("1", "2", "alice", "raid", 10))
    await started.wait()
    configure(raid=0)
    release.set()
    assert not await task
    shoutouts.enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_simultaneous_events_only_send_once(env):
    _, service, shoutouts, configure = env
    configure(chat=1, subscription=1, redeem=1)
    results = await asyncio.gather(*(service.handle("1", "2", "alice", trigger) for trigger in ["chat", "subscription", "redeem"]))
    assert results.count(True) == 1
    assert shoutouts.send_chat_message.await_count == 1


@pytest.mark.asyncio
async def test_raid_blacklist_covers_queued_raids_but_not_whitelist_or_first_chat(env):
    bot, _, _, configure = env
    queue = ShoutoutService(bot)
    assert queue.enqueue("1", "2", "alice", "auto:raid")[0]
    configure(blacklist="alice")
    queue.send_native_shoutout = AsyncMock()
    await queue.process_broadcaster_queue("1")
    queue.send_native_shoutout.assert_not_awaited()
    assert not queue.queues["1"]
    # Manual moderator shoutouts remain available.
    assert queue.enqueue("1", "2", "alice", "moderator")[0]
    assert queue.enqueue("1", "3", "alice", "auto:chat")[0]
    assert queue.enqueue("1", "4", "alice", "first-chat")[0]
    assert not queue.enqueue("1", "5", "alice", "auto:raid")[0]
    first_chat = FirstChatShoutoutService(bot, None, queue, None)
    first_chat.get_configured_user = Mock(return_value=FirstChatShoutout(user_id='2', username='alice'))
    first_chat.get_live_stream_id = AsyncMock(return_value='stream-1')
    first_chat.mark_seen = AsyncMock(return_value=True)
    queue.send_chat_message = AsyncMock(return_value=True)
    assert await first_chat.handle_message(broadcaster_id="1", user_id="2", username="alice")
    queue.send_chat_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_disabled_anonymous_and_self_events_are_ignored(env):
    bot, service, shoutouts, _ = env
    for target, trigger in [("None", "raid"), ("1", "raid"), ("999", "raid"), ("998", "raid"), ("2", "chat")]:
        assert not await service.handle("1", target, "someone", trigger, 100)
    bot.services.features.is_enabled.return_value = False
    assert not await service.handle("1", "2", "alice", "raid", 100)
    shoutouts.enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_custom_messages_and_output_switches(env):
    _, service, shoutouts, configure = env
    configure(native=0, raid_message="Thanks {username} for {viewer_count} viewers")
    assert await service.handle("1", "2", "alice", "raid", 20)
    shoutouts.enqueue.assert_not_called()
    assert shoutouts.send_chat_message.call_args.args[2] == "Thanks {username} for {viewer_count} viewers"
    assert shoutouts.send_chat_message.call_args.kwargs["viewer_count"] == 20


@pytest.mark.asyncio
async def test_settings_persist_and_are_channel_scoped(tmp_path):
    clear_profiles()
    try:
        async with asqlite.create_pool(str(tmp_path / "settings.db")) as db:
            service = ProfileSettingsService(db)
            await service.setup()
            for channel in ["1", "2"]:
                base = ChannelProfile(channel_name=channel)
                activate_profile(channel, base); service.apply_overrides(channel, base)
            await service.set_override("1", "automatic_shoutouts.raid", "0", "owner")
            await service.set_override("1", "automatic_shoutouts.users", "@Alice, BOB\nalice", "owner")
            loaded = ProfileSettingsService(db); await loaded.setup()
            assert loaded.overrides["1"]["automatic_shoutouts.raid"] == 0
            assert loaded.overrides["1"]["automatic_shoutouts.users"] == "alice\nbob"
            assert "2" not in loaded.overrides
    finally:
        clear_profiles()


@pytest.mark.parametrize("key,value", [("raid", "true"), ("minimum_viewers", "-1"), ("users", "not a username"), ("raid_message", "{username.__class__}")])
def test_invalid_settings_are_rejected(key, value):
    with pytest.raises(ValueError):
        ProfileSettingsService.validate_value(PROFILE_SETTINGS_BY_KEY[f"automatic_shoutouts.{key}"], value)


@pytest.mark.asyncio
async def test_bulk_settings_save_together_and_reject_invalid_changes(tmp_path):
    async with asqlite.create_pool(str(tmp_path / "bulk.db")) as db:
        service = ProfileSettingsService(db)
        await service.setup()
        values = {f"automatic_shoutouts.{key}": str(value) for key, value in asdict(AutomaticShoutouts()).items()}
        values.update({"automatic_shoutouts.chat": "1", "automatic_shoutouts.users": "@Alice,BOB"})
        await service.set_automatic_shoutouts("1", values, "owner")
        loaded = ProfileSettingsService(db)
        await loaded.setup()
        assert loaded.overrides["1"]["automatic_shoutouts.chat"] == 1
        assert loaded.overrides["1"]["automatic_shoutouts.users"] == "alice\nbob"
        previous = loaded.overrides["1"].copy()
        for invalid in ({**values, "automatic_shoutouts.minimum_viewers": "-1"}, {"automatic_shoutouts.chat": "0"}):
            with pytest.raises(ValueError):
                await service.set_automatic_shoutouts("1", invalid, "owner")
        await loaded.load_overrides()
        assert loaded.overrides["1"] == previous
        assert service.overrides["1"] == previous


@pytest.mark.asyncio
async def test_bulk_endpoint_uses_last_checkbox_value_and_channel_identity(monkeypatch):
    from starlette.datastructures import FormData
    from web.channel.routers import dashboard
    service = SimpleNamespace(set_automatic_shoutouts=AsyncMock())
    monkeypatch.setattr(dashboard, "get_bot", lambda: SimpleNamespace(services=SimpleNamespace(profile_settings=service)))
    monkeypatch.setattr(dashboard, "validate_csrf_token", Mock())
    monkeypatch.setattr(dashboard, "current_channel_id", lambda request: "1")
    monkeypatch.setattr(dashboard, "settings_actor", lambda request: "owner")
    request = Request({"type": "http", "path": "/channel/customization", "headers": []})
    request._form = FormData([("automatic_shoutouts.chat", "0"), ("automatic_shoutouts.chat", "1"), ("automatic_shoutouts.raid", "0"), ("broadcaster_id", "other")])
    response = await dashboard.update_channel_customization(request, "automatic_shoutouts", "", "save", "csrf")
    assert response.status_code == 303
    service.set_automatic_shoutouts.assert_awaited_once_with("1", {"automatic_shoutouts.chat": "1", "automatic_shoutouts.raid": "0"}, "owner")


@pytest.mark.asyncio
async def test_watch_streak_event_routes_only_own_channel_notifications(env):
    from bot.shared.events.chat import ChatEvents
    bot, _, _, _ = env
    bot.services.automatic_shoutouts = SimpleNamespace(handle=AsyncMock(return_value=False))
    bot.services.live_chat = Mock()
    payload = SimpleNamespace(broadcaster=SimpleNamespace(id="1"), chatter=SimpleNamespace(id="2", name="alice"), notice_type="watch_streak")
    await ChatEvents(bot).event_chat_notification(payload)
    bot.services.automatic_shoutouts.handle.assert_awaited_once_with("1", "2", "alice", "streak", 0)
    payload.notice_type = "shared_chat_watch_streak"
    await ChatEvents(bot).event_chat_notification(payload)
    assert bot.services.automatic_shoutouts.handle.await_count == 1


@pytest.mark.asyncio
async def test_subscription_events_trigger_independently_of_response_messages(env):
    from bot.shared.events.community import CommunityEvents
    bot, _, _, _ = env
    calls = AsyncMock(return_value=False)
    bot.services.automatic_shoutouts = SimpleNamespace(handle=calls)
    bot.services.stream_logs = Mock()
    bot.services.features.is_enabled.return_value = False
    payload = SimpleNamespace(broadcaster=SimpleNamespace(id="1", name="owner"), user=SimpleNamespace(id="2", name="alice"), gift=False, total=3, cumulative_months=12, streak_months=3)
    events = CommunityEvents(bot)
    await events.event_subscription(payload)
    await events.event_subscription_gift(payload)
    await events.event_subscription_message(payload)
    assert [call.args[3] for call in calls.call_args_list] == ["subscription", "gift", "subscription", "streak"]
    calls.reset_mock(); payload.gift = True
    await events.event_subscription(payload)
    calls.assert_not_awaited()


@pytest.mark.asyncio
async def test_incoming_raid_shoutouts_do_not_depend_on_welcome_messages(env, monkeypatch):
    from bot.shared.events.raids import RaidEvents
    bot, _, _, _ = env
    bot.services.automatic_shoutouts = SimpleNamespace(handle=AsyncMock(return_value=True))
    bot.services.stream_logs = Mock(); bot.services.db = object()
    bot.services.features.is_enabled.return_value = False
    monkeypatch.setattr("bot.shared.events.raids.record_incoming_raid", AsyncMock())
    await RaidEvents(bot).handle_raid(SimpleNamespace(from_broadcaster=SimpleNamespace(id="2", name="alice"), to_broadcaster=SimpleNamespace(id="1", name="owner"), viewer_count=20))
    bot.services.automatic_shoutouts.handle.assert_awaited_once_with("1", "2", "alice", "raid", 20)


@pytest.mark.asyncio
async def test_user_autocomplete_is_authenticated_and_scoped_to_channel(env, tmp_path, monkeypatch):
    from storage.migrations.core.v008_chatter_identities import migrate
    from web.channel.routers import dashboard
    bot, service, _, _ = env
    async with asqlite.create_pool(str(tmp_path / "users.db")) as db:
        async with db.acquire() as connection:
            await migrate(connection)
            await connection.execute("INSERT INTO chatter_identities(user_id,login,display_name) VALUES ('2','alice','Alice'),('3','alicia','Alicia')")
            await connection.execute("INSERT INTO chatter_channel_observations(broadcaster_id,user_id) VALUES ('1','2'),('other','3')")
        bot.services.db = db
        bot.services.broadcasters = SimpleNamespace(get_broadcasters=lambda: {"1": object()})
        bot._http.request_json.return_value = {"data": []}
        monkeypatch.setattr(dashboard, "get_bot", lambda: bot)
        request = Request({"type": "http", "session": {"channel_user_id": "1"}})
        response = await dashboard.automatic_shoutout_users(request, "ali")
        assert [user["login"] for user in json.loads(response.body)["users"]] == ["alice"]
        anonymous = Request({"type": "http", "session": {}})
        assert (await dashboard.automatic_shoutout_users(anonymous, "ali")).status_code == 401


def test_controls_render_under_stream_events():
    from tests.test_settings_book import settings_context
    from web.shared.common import templates
    try:
        context, _, _ = settings_context("events")
        html = templates.env.get_template("channel/settings.html").render(**context)
        assert 'data-setting-key="automatic_shoutouts.raid"' in html
        assert 'data-setting-key="automatic_shoutouts.minimum_viewers"' in html
        assert html.count('<div data-shoutout-user-list>') == 2
        assert '/protected-users/search' in html
        assert 'automatic-shoutout-settings.js' in html
        incoming, whitelist = html.split('<h4>Incoming raid messages</h4>', 1)[1].split('<h4>Interactive shoutouts</h4>', 1)
        assert 'data-setting-key="automatic_shoutouts.blacklist"' in incoming
        assert 'data-setting-key="automatic_shoutouts.require_partner"' in incoming
        assert 'data-setting-key="automatic_shoutouts.users"' not in incoming
        assert 'data-setting-key="automatic_shoutouts.users"' in whitelist
        assert 'data-setting-key="automatic_shoutouts.chat"' in whitelist
        assert 'id="auto-interactions"' in whitelist
        assert whitelist.index('automatic_shoutouts.event_message') < whitelist.index('automatic_shoutouts.users')
        assert '<a data-settings-link href="?section=shoutouts#shoutout-messages">standard shoutout message</a>' in whitelist
        assert '<h4>Message</h4>' not in whitelist
        assert 'data-setting-key="automatic_shoutouts.blacklist"' not in whitelist
        assert '<h4>Delivery</h4>' not in html
        assert '<h4>Who qualifies</h4>' not in html
        assert 'class="automatic-shoutout-switch"' not in html
        assert 'automatic-shoutout-switch-form' in html
        assert 'name="setting_name" value="automatic_shoutouts"' not in html
    finally:
        clear_profiles()


@pytest.mark.asyncio
@pytest.mark.parametrize("new_message", [None, "Custom shoutout", ""])
async def test_legacy_incoming_message_moves_to_single_shoutout_setting(tmp_path, new_message):
    async with asqlite.create_pool(str(tmp_path / "raid-message.db")) as db:
        settings = ProfileSettingsService(db)
        await settings.setup()
        async with db.acquire() as connection:
            await connection.execute(
                "INSERT INTO channel_profile_overrides (broadcaster_id, setting_name, setting_value, updated_by) VALUES (?, ?, ?, ?)",
                ("1", "raid_messages.incoming", json.dumps("Welcome {raider_name}, {viewer_count} {viewer_word}!"), "test"))
            if new_message is not None:
                await connection.execute(
                    "INSERT INTO channel_profile_overrides (broadcaster_id, setting_name, setting_value, updated_by) VALUES (?, ?, ?, ?)",
                    ("1", "automatic_shoutouts.raid_message", json.dumps(new_message), "test"))
        await settings.setup()
        await settings.setup()
        profile = settings.apply_overrides("1", ChannelProfile(channel_name="example"))
        expected = new_message if new_message is not None else "Welcome {username}, {viewer_count} {viewer_word}!"
        assert profile.automatic_shoutouts.raid_message == expected
        assert "raid_messages.incoming" not in settings.overrides["1"]
        async with db.acquire() as connection:
            assert not await connection.fetchone("SELECT 1 FROM channel_profile_overrides WHERE setting_name = 'raid_messages.incoming'")


def test_legacy_profile_incoming_message_is_preserved_as_shoutout_default():
    from bot.profiles import RaidMessages
    settings = ProfileSettingsService(None)
    profile = ChannelProfile(channel_name="example", raid_messages=RaidMessages(incoming="Welcome {raider_name}!"))
    assert settings.apply_overrides("1", profile).automatic_shoutouts.raid_message == "Welcome {username}!"


@pytest.mark.asyncio
@pytest.mark.parametrize("trigger", ["chat", "redeem", "subscription", "gift", "bits", "streak"])
async def test_interaction_master_toggle_preserves_triggers_and_does_not_disable_raids(env, trigger):
    bot, service, shoutouts, configure = env
    config = configure(interactions=0, **{trigger: 1})
    assert not await service.handle("1", "2", "alice", trigger, 10)
    bot.services.first_chat_shoutouts.get_live_stream_id.assert_not_awaited()
    shoutouts.send_chat_message.assert_not_awaited()
    assert module.blocked_automatic_shoutout("1", "alice", f"auto:{trigger}")
    assert await service.handle("1", "2", "alice", "raid", 10)
    assert getattr(config, trigger) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('trigger', ['chat', 'redeem', 'subscription', 'gift', 'bits', 'streak'])
async def test_whitelist_triggers_are_enabled_by_default_without_amount_thresholds(env, trigger):
    _, service, _, configure = env
    config = configure()
    assert getattr(config, trigger) == 1
    assert await service.handle('1', '2', 'alice', trigger, 1)
    assert 'automatic_shoutouts.minimum_bits' not in PROFILE_SETTINGS_BY_KEY
    assert 'automatic_shoutouts.minimum_gifts' not in PROFILE_SETTINGS_BY_KEY
