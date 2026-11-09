const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup(enabled = false) {
    const key = 'ratsboombot:youtube-chat-test', storage = new Map(enabled ? [[key, 'true']] : []);
    const events = [], handlers = {}, logs = [], classes = () => ({add() {}});
    const badge = {dataset: {}, classList: classes()}, details = {hidden: true};
    const section = {children: [{}, details], querySelector: () => badge};
    const youtube = {disabled: true, hidden: true, closest: () => section};
    const twitch = {hidden: true}, input = {}, form = {dataset: {}, querySelector: () => input};
    const dot = {classList: classes(), setAttribute() {}};
    const document = {querySelector: selector => ({'[data-chat-composer]': form, '[data-chat-filter-platform="youtube"]': youtube, '.chat-platform-dot.youtube': dot})[selector],
        querySelectorAll: () => [twitch, youtube], addEventListener: (type, callback) => {handlers[type] = callback;},
        dispatchEvent: event => events.push(event)};
    let reloads = 0;
    const window = {sessionStorage: {getItem: name => storage.get(name), setItem: (name, value) => storage.set(name, value)},
        location: {reload() {reloads++;}}};
    vm.runInNewContext(fs.readFileSync('web/static/js/dashboard-chat-test-mode.js', 'utf8'), {
        window, document, console: {warn: text => logs.push(text), info: text => logs.push(text)}, CustomEvent: class {constructor(type, options) {this.type = type; this.detail = options.detail;}}
    });
    return {api: window.dashboardChatDebug, document, logs, form, input, youtube, twitch, details, badge, dot, events, handlers, storage, window, key, reloads: () => reloads};
}

test('notice samples explain hidden filters and missing chat listeners', () => {
    const app = setup();
    app.api.notice('watchstreak');
    assert.match(app.logs.at(-1), /No chat feed received/);
    app.document.querySelectorAll = () => [{dataset: {messageId: app.events.at(-1).detail.id}, hidden: true}];
    app.api.notice('watchstreak');
    assert.match(app.logs.at(-1), /Enable Bots and Redeems/);
    app.document.querySelectorAll = () => [{dataset: {messageId: app.events.at(-1).detail.id}, hidden: false}];
    app.api.notice('watchstreak');
    assert.match(app.logs.at(-1), /sample added to chat/);
});

test('Bits sample previews 100 Bits locally without enabling simulated connections', () => {
    const app = setup();
    app.api.notice('bits');
    assert.equal(app.api.active, false);
    assert.equal(app.events.length, 1);
    const event = app.events[0];
    assert.equal(event.type, 'dashboard-chat-test-notice');
    assert.equal(event.detail.bits, 100);
    assert.equal(event.detail.platform, 'twitch');
    assert.equal(event.detail.test_mode, true);
    assert.equal(event.detail.local_preview, true);
    assert.match(event.detail.message, /Cheer100/);
    assert.equal(event.detail.notice_type, '');
});

test('spaced-Bits sample provides a local preview with the combined amount', () => {
    const app = setup();
    app.api.notice('spacedbits');
    assert.equal(app.events[0].detail.bits, 150);
    assert.equal(app.events[0].detail.message, 'Cheer100 hello Cheer50 world');
    assert.equal(app.events[0].detail.local_preview, true);
});

test('test command opts into a session-only simulation and can turn it off again', () => {
    const app = setup(); assert.equal(app.api.active, false);
    assert.equal(app.api.send('real message', 'youtube'), null);
    assert.equal(app.form.dataset.youtubeConnected, undefined);
    app.api.youtube(); assert.equal(app.storage.get(app.key), 'true'); assert.equal(app.reloads(), 1);
    app.api.youtube(false); assert.equal(app.storage.get(app.key), 'false'); assert.equal(app.reloads(), 2);
});

test('YouTube test connection toggles by default and still accepts explicit on/off values', () => {
    const app = setup();
    app.api.youtube(); assert.equal(app.api.active, true); assert.equal(app.storage.get(app.key), 'true');
    app.api.youtube(); assert.equal(app.api.active, false); assert.equal(app.storage.get(app.key), 'false');
    app.api.youtube(true); app.api.youtube(true);
    assert.equal(app.api.active, true); assert.equal(app.storage.get(app.key), 'true');
    app.api.youtube(false); app.api.youtube(false);
    assert.equal(app.api.active, false); assert.equal(app.storage.get(app.key), 'false');
    const enabled = setup(true);
    enabled.api.youtube(); assert.equal(enabled.api.active, false); assert.equal(enabled.storage.get(enabled.key), 'false');
});

test('simulated connection enables platform filters and supplies clearly marked samples', () => {
    const app = setup(true);
    assert.equal(app.form.dataset.youtubeConnected, 'true'); assert.match(app.input.placeholder, /not sent/);
    assert.equal(app.youtube.disabled, false); assert.equal(app.youtube.hidden, false);
    assert.equal(app.twitch.hidden, false); assert.equal(app.details.hidden, false);
    assert.equal(app.badge.textContent, 'Test connection');
    app.handlers.DOMContentLoaded();
    assert.equal(app.events.length, 5);
    assert.ok(app.events.every(event => event.detail.test_mode));
    assert.equal(app.events.filter(event => event.detail.platform === 'youtube').length, 4);
    const result = app.api.send('hello', 'both');
    assert.match(result.message, /nothing sent/);
    assert.deepEqual(app.events.slice(-2).map(event => event.detail.platform), ['twitch', 'youtube']);
});

test('dashboard sends in test mode never construct or post a real chat request', async () => {
    const app = setup(true);
    const source = fs.readFileSync('web/static/js/dashboard-chat-send.js', 'utf8');
    const send = source.match(/        async send\(outgoingMessage, signal\) \{[\s\S]*?\n        \}/)[0];
    const transport = vm.runInNewContext(`({${send}}).send`, {window: app.window, selectedTarget: 'both',
        FormData: class {constructor() {throw new Error('Must not prepare a live send');}},
        fetch() {throw new Error('Must not send live messages');}});
    const result = await transport('hello', null);
    assert.match(result.message, /Test mode/); assert.equal(app.events.length, 2);
});

test('one-shot failures simulate the entire send locally and then restore normal delivery', () => {
    for (const platform of ['twitch', 'youtube', 'all']) {
        const app = setup();
        assert.match(app.api.failNext(platform), /Nothing will be posted/);
        const result = app.api.send('hello', 'both');
        const failures = platform === 'all' ? ['twitch', 'youtube'] : [platform];
        assert.deepEqual(Object.keys(result.errors), failures);
        assert.deepEqual(Array.from(result.sent), ['twitch', 'youtube'].filter(item => !failures.includes(item)));
        assert.deepEqual(app.events.map(event => event.detail.platform), Array.from(result.sent));
        assert.equal(app.api.send('next real send', 'both'), null);
    }
});

test('failure applies only to selected destinations and validates console arguments', () => {
    const app = setup(true);
    assert.throws(() => app.api.failNext('invalid'), /twitch, youtube, or all/);
    app.api.failNext('youtube');
    const result = app.api.send('hello', 'twitch');
    assert.deepEqual(Object.keys(result.errors), []);
    assert.deepEqual(Array.from(result.sent), ['twitch']);
    assert.deepEqual(Object.keys(app.api.send('again', 'both').errors), []);
});

test('notice simulations cover every event locally without enabling simulated connection or sends', () => {
    const app = setup();
    const ids = app.api.notice('all');
    assert.equal(ids.length, 12);
    assert.equal(new Set(ids).size, ids.length);
    assert.ok(app.events.every(event => event.type === 'dashboard-chat-test-notice' && event.detail.test_mode));
    assert.ok(app.events.every(event => event.detail.platform === 'twitch'));
    assert.equal(app.events.filter(event => event.detail.is_redeem).length, 1);
    assert.ok(app.events.some(event => event.detail.notice_label === 'Prime subscription'));
    assert.ok(app.events.some(event => event.detail.notice_label === 'Prime resubscription'));
    assert.ok(app.events.some(event => event.detail.notice.includes('6 consecutive months')));
    assert.ok(app.events.some(event => event.detail.notice_type === 'raid'));
    assert.equal(app.api.active, false);
    assert.equal(app.api.send('normal message', 'twitch'), null);
    assert.throws(() => app.api.notice('invalid'), /Use all/);
    const before = app.events.length;
    app.api.notice('raid');
    assert.equal(app.events.length, before + 1);
});

test('simulated failures run through the actual private-error transport without posting', async () => {
    for (const platform of ['youtube', 'both']) {
        const app = setup(); app.api.failNext(platform);
        const notices = [];
        const source = fs.readFileSync('web/static/js/dashboard-chat-send.js', 'utf8');
        const send = source.match(/        async send\(outgoingMessage, signal\) \{[\s\S]*?\n        \}/)[0];
        const transport = vm.runInNewContext(`({${send}}).send`, {window: app.window, selectedTarget: 'both',
            reportSendFailure: (platform, message) => notices.push({platform, message}),
            FormData: class {constructor() {throw new Error('Must not prepare a live send');}},
            fetch() {throw new Error('Must not post');}});
        if (platform === 'both') await assert.rejects(transport('hello', {aborted: false}), /Simulated/);
        else await transport('hello', {aborted: false});
        assert.deepEqual(notices.map(item => item.platform), platform === 'both' ? ['twitch', 'youtube'] : ['youtube']);
    }
});
