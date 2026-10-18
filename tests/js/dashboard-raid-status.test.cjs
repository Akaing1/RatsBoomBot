const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web/static/js/dashboard-raid-status.js', 'utf8');

class Element {
    constructor() {
        this.handlers = {}; this.dataset = {}; this.attributes = {}; this.style = {}; this.classes = new Set();
        this.hidden = true;
        this.classList = {add: value => this.classes.add(value), remove: value => this.classes.delete(value)};
    }
    addEventListener(name, callback) { this.handlers[name] = callback; }
    setAttribute(name, value) { this.attributes[name] = value; }
    removeAttribute(name) { delete this.attributes[name]; }
    focus() { this.focused = true; }
    remove() { this.removed = true; }
    scrollIntoView() { this.scrolled = true; }
    getBoundingClientRect() { return {left: 20, top: 30, width: 300, height: 80}; }
    animate(frames, options) {
        this.animation = {frames, options};
        return {finished: new Promise(resolve => { this.finish = resolve; })};
    }
}
function setup(reduced = false, followDefault = true) {
    const banner = new Element(), channel = new Element(), text = new Element(), cancel = new Element(), avatar = new Element();
    const requests = [], events = {}, intervals = new Map(), body = [];
    let now = 100;
    let nextInterval = 0;
    const follow = new Element(); follow.checked = followDefault;
    const visits = [];
    banner.dataset = {pendingUrl: '/pending', actionUrl: '/action', csrfToken: 'valid'};
    const controls = {'[data-pending-raid-channel]': channel, '[data-pending-raid-text]': text,
        '[data-pending-raid-cancel]': cancel, '[data-pending-raid-avatar]': avatar, '[data-pending-raid-follow]': follow};
    banner.querySelector = selector => controls[selector];
    vm.runInNewContext(source, {
        document: {querySelector: () => banner, addEventListener: (name, callback) => { events[name] = callback; }, body: {append: element => body.push(element)}},
        window: {matchMedia: () => ({matches: reduced}), location: {assign: url => visits.push(url)}}, Date: {now: () => now * 1000}, URLSearchParams,
        requestAnimationFrame: callback => callback(), setInterval: callback => { intervals.set(++nextInterval, callback); return nextInterval; }, clearInterval: id => intervals.delete(id),
        fetch: (url, options) => new Promise(resolve => requests.push({url, options,
            respond: (payload, ok = true) => resolve({ok, json: async () => payload})}))
    });
    return {banner, channel, text, cancel, avatar, requests, events, intervals, body, follow, visits,
        advance: seconds => { now += seconds; [...intervals.values()].forEach(callback => callback()); }};
}
const raid = {login: 'target', display_name: 'Target', target_id: '2', expires_at: 190};
const flush = () => new Promise(resolve => setImmediate(resolve));

test('accepted raid appears in chat and countdown expiry does not claim completion', () => {
    const app = setup(); app.events['dashboard-raid-started']({detail: {raid}});
    assert.equal(app.banner.hidden, false);
    assert.equal(app.channel.textContent, 'Target');
    assert.equal(app.channel.href, 'https://www.twitch.tv/target');
    assert.match(app.text.textContent, /90s/);
    app.advance(91);
    assert.match(app.text.textContent, /Check Twitch chat/);
    assert.equal(app.cancel.hidden, true);
    assert.equal(app.intervals.size, 1); // Keep checking for an actual Twitch confirmation.
    assert.deepEqual(app.visits, ['https://www.twitch.tv/target']);
});

test('pending raid shows the target profile picture and has no dismiss control', () => {
    const app = setup();
    const url = 'https://static-cdn.jtvnw.net/jtv_user_pictures/target.png';
    app.events['dashboard-raid-started']({detail: {raid: {...raid, profile_image_url: url}}});
    assert.equal(app.avatar.src, url);
    assert.equal(app.avatar.hidden, false);
    app.avatar.handlers.error();
    assert.equal(app.avatar.hidden, true);
    const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
    assert.equal(template.includes('data-pending-raid-dismiss'), false);
});

test('cancel hides pending raid only after accepted response', async () => {
    const app = setup(); app.events['dashboard-raid-started']({detail: {raid}});
    const result = app.cancel.handlers.click();
    assert.equal(app.requests[1].options.body.get('action'), 'cancel');
    assert.equal(app.requests[1].options.body.get('csrf_token'), 'valid');
    assert.equal(app.banner.hidden, false);
    app.requests[1].respond({raid: null}); await result;
    assert.equal(app.banner.hidden, true);
});

test('failed cancel preserves pending raid and reports failure', async () => {
    const app = setup(); app.events['dashboard-raid-started']({detail: {raid}});
    const result = app.cancel.handlers.click();
    app.requests[1].respond({detail: 'Reconnect Twitch.'}, false); await result;
    assert.equal(app.banner.hidden, false);
    assert.equal(app.cancel.disabled, false);
    assert.equal(app.text.textContent, 'Reconnect Twitch.');
});

test('late initial status cannot overwrite a newly started raid', async () => {
    const app = setup(); app.events['dashboard-raid-started']({detail: {raid}});
    app.requests[0].respond({raid: {...raid, login: 'old', display_name: 'Old'}}); await flush();
    assert.equal(app.channel.textContent, 'Target');
});

test('selected card animates to chat and is removed after arrival', async () => {
    const app = setup(), flyer = new Element();
    app.events['dashboard-raid-started']({detail: {raid, flyer, sourceRect: {left: 100, top: 100, width: 400, height: 200}}});
    assert.equal(app.body[0], flyer);
    assert.equal(flyer.animation.options.duration, 500);
    assert.match(flyer.animation.frames[1].transform, /translate\(-80px,-70px\)/);
    assert.equal(app.banner.classes.has('is-arriving'), true);
    flyer.finish(); await flush();
    assert.equal(flyer.removed, true);
    assert.equal(app.banner.focused, true);
});

test('reduced motion skips flying animation and focuses chat status', () => {
    const app = setup(true), flyer = new Element();
    app.events['dashboard-raid-started']({detail: {raid, flyer, sourceRect: {left: 100, top: 100, width: 400, height: 200}}});
    assert.equal(flyer.animation, undefined);
    assert.equal(flyer.removed, true);
    assert.equal(app.banner.focused, true);
});

test('also follows an early Twitch confirmation without duplicate navigation', async () => {
    const app = setup(); app.events['dashboard-raid-started']({detail: {raid}});
    app.advance(3);
    app.requests[1].respond({raid: {...raid, completed: true}}); await flush();
    assert.deepEqual(app.visits, ['https://www.twitch.tv/target']);
    assert.equal(app.text.textContent, 'Raid started');
    app.advance(3); assert.equal(app.visits.length, 1);
});

test('saved off default and per-raid opt out prevent navigation', async () => {
    for (const savedDefault of [true, false]) {
        const app = setup(false, savedDefault); app.events['dashboard-raid-started']({detail: {raid}});
        assert.equal(app.follow.checked, savedDefault);
        app.follow.checked = false; app.advance(3);
        app.requests[1].respond({raid: {...raid, completed: true}}); await flush();
        assert.equal(app.visits.length, 0);
    }
});

test('stale confirmation after cancel cannot follow', async () => {
    const app = setup(); app.events['dashboard-raid-started']({detail: {raid}}); app.advance(3);
    const cancel = app.cancel.handlers.click();
    app.requests[2].respond({raid: null}); await cancel;
    app.requests[1].respond({raid: {...raid, completed: true}}); await flush();
    assert.equal(app.visits.length, 0);
});

test('target avatar flies separately into the left side of the chat pin', async () => {
    const app = setup(), avatarFlyer = new Element();
    app.events['dashboard-raid-started']({detail: {raid: {...raid, profile_image_url: 'https://static-cdn.jtvnw.net/avatar.png'},
        avatarFlyer, avatarRect: {left: 100, top: 100, width: 40, height: 40}}});
    assert.equal(app.body[0], avatarFlyer); assert.equal(app.avatar.style.opacity, '0');
    assert.equal(avatarFlyer.animation.options.duration, 550);
    avatarFlyer.finish(); await flush();
    assert.equal(avatarFlyer.removed, true); assert.equal(app.avatar.style.opacity, '');
});
