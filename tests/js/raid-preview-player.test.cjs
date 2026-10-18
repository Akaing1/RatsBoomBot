const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
    constructor() { this.children = []; this.rect = {width: 640, height: 360}; }
    getBoundingClientRect() { return this.rect; }
    append(child) { this.children.push(child); }
    replaceChildren() { this.children = []; }
    remove() { this.removed = true; }
}
function setup(sdk = true) {
    const frames = new Map(), players = [], reports = []; let id = 0;
    class Player {
        constructor(mount, options) {
            this.mount = mount; this.options = options; this.events = {}; this.calls = []; players.push(this);
            const iframe = new Element(); iframe.tagName = 'iframe'; host.children[0].append(iframe);
        }
        addEventListener(name, handler) {
            assert.ok(!this.events[name], `Duplicate player listener: ${name}`);
            this.events[name] = handler;
        }
        setMuted(value) { this.calls.push(['muted', value]); }
        play() { this.calls.push(['play']); }
        pause() { this.calls.push(['pause']); }
    }
    Object.assign(Player, {READY: 'ready', PLAYING: 'playing', PLAYBACK_BLOCKED: 'blocked', PAUSE: 'pause', OFFLINE: 'offline', ENDED: 'ended'});
    const observers = [], documentHandlers = {};
    const window = {location: {hostname: 'localhost'}, Twitch: sdk ? {Player} : undefined};
    window.ResizeObserver = class {
        constructor(callback) { this.callback = callback; observers.push(this); }
        observe() {} disconnect() { this.disconnected = true; }
    };
    const document = {hidden: false, createElement: () => new Element(),
        addEventListener: (name, callback) => { documentHandlers[name] = callback; },
        removeEventListener: name => { delete documentHandlers[name]; }};
    const style = {visibility: 'visible', display: 'block', opacity: '1'};
    vm.runInNewContext(fs.readFileSync('web/static/js/raid-preview-player.js', 'utf8'), {
        window, document, getComputedStyle: () => style, URL, URLSearchParams,
        requestAnimationFrame: callback => { frames.set(++id, callback); return id; }, cancelAnimationFrame: key => frames.delete(key)
    });
    const host = new Element(), controller = window.createRaidPreviewPlayer(host, 'target', message => reports.push(message));
    return {host, controller, players, reports, document, style, observers, documentHandlers,
        flush() { const pending = [...frames.values()]; frames.clear(); pending.forEach(callback => callback()); },
        settle() { this.flush(); this.flush(); }};
}
test('waits for visible layout, then uses native muted autoplay without extra READY playback calls', () => {
    const app = setup(); assert.equal(app.players.length, 0); app.flush();
    assert.equal(app.players.length, 0); app.flush();
    const player = app.players[0];
    assert.equal(player.options.channel, 'target'); assert.equal(player.options.autoplay, true); assert.equal(player.options.muted, true);
    assert.equal(player.options.width, '100%'); assert.equal(player.options.height, '100%');
    player.events.ready(); app.settle(); assert.deepEqual(player.calls, []);
    player.events.ready(); assert.equal(player.calls.length, 0);
});
test('reports browser blocking without repeatedly overriding a user pause', () => {
    const app = setup(); app.settle(); const player = app.players[0]; player.events.ready(); app.settle();
    player.events.blocked(); assert.match(app.reports[0], /Press Play/);
    player.events.playing(); assert.equal(app.reports[1], ''); assert.equal(player.calls.length, 0);
});
test('closing pauses and removes the player and ignores late events', () => {
    const app = setup(); app.settle(); const player = app.players[0]; player.events.ready();
    app.controller.destroy(); assert.deepEqual(player.calls.at(-1), ['pause']); assert.ok(app.host.children[0].removed);
    player.events.playing(); player.events.blocked(); assert.equal(app.reports.length, 0);
});
test('closing before layout prevents a hidden player from starting', () => {
    const app = setup(); app.controller.destroy(); app.flush(); assert.equal(app.players.length, 0);
});
test('SDK failure falls back to an autoplay-enabled muted iframe after layout', () => {
    const app = setup(false); app.settle(); const frame = app.host.children[0].children[0];
    const url = new URL(frame.src); assert.equal(url.searchParams.get('autoplay'), 'true');
    assert.equal(url.searchParams.get('muted'), 'true'); assert.equal(frame.allow, 'autoplay; fullscreen');
    app.controller.destroy(); assert.ok(app.host.children[0].removed);
});

test('cleanup is idempotent and no unused overlay-state listeners remain', () => {
    const app = setup(); app.settle(); const player = app.players[0]; player.events.ready();
    assert.deepEqual(Object.keys(player.events).sort(), ['blocked', 'playing', 'ready']);
    app.controller.destroy(); app.controller.destroy();
    assert.deepEqual(player.calls, [['pause']]);
    assert.equal(app.observers[0].disconnected, true);
    assert.deepEqual(app.documentHandlers, {});
});

test('undersized or hidden previews wait for resize and visible stable dimensions', () => {
    const app = setup(); app.host.rect = {width: 399, height: 300}; app.settle();
    assert.equal(app.players.length, 0);
    app.host.rect = {width: 400, height: 299}; app.observers[0].callback(); app.settle();
    assert.equal(app.players.length, 0);
    app.host.rect = {width: 400, height: 300}; app.style.visibility = 'hidden';
    app.observers[0].callback(); app.settle(); assert.equal(app.players.length, 0);
    app.style.visibility = 'visible'; app.document.hidden = true;
    app.observers[0].callback(); app.settle(); assert.equal(app.players.length, 0);
    app.document.hidden = false; app.documentHandlers.visibilitychange(); app.settle();
    assert.equal(app.players.length, 1); assert.equal(app.observers[0].disconnected, true);
});

test('width changes during opening must settle before player construction', () => {
    const app = setup(); app.flush(); app.host.rect.width = 800; app.flush();
    assert.equal(app.players.length, 0); app.flush(); assert.equal(app.players.length, 1);
});

test('closing after READY never schedules a later playback request', () => {
    const app = setup(); app.settle(); const player = app.players[0]; player.events.ready();
    app.flush(); app.controller.destroy(); app.flush();
    assert.deepEqual(player.calls, [['pause']]);
});
