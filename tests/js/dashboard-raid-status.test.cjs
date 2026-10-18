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
    append(child) { this.child = child; }
    scrollIntoView() { this.scrolled = true; }
    getBoundingClientRect() { return {left: 20, top: 30, width: 300, height: 80}; }
    animate(frames, options) {
        this.animation = {frames, options};
        return {finished: new Promise(resolve => { this.finish = resolve; }), cancel: () => { this.animation.cancelled = true; }};
    }
}
function setup(reduced = false, followDefault = true) {
    const banner = new Element(), channel = new Element(), text = new Element(), cancel = new Element(), avatar = new Element();
    const requests = [], events = {}, intervals = new Map(), body = [];
    let now = 100;
    let nextInterval = 0;
    const follow = new Element(); follow.checked = followDefault;
    const description = new Element();
    const countdown = new Element(), secondsLabel = new Element(), progress = new Element(), ring = new Element();
    const visits = [];
    banner.dataset = {pendingUrl: '/pending', actionUrl: '/action', csrfToken: 'valid'};
    const controls = {'[data-pending-raid-channel]': channel, '[data-pending-raid-text]': text,
        '[data-pending-raid-cancel]': cancel, '[data-pending-raid-avatar]': avatar, '[data-pending-raid-follow]': follow,
        '[data-pending-raid-description]': description,
        '[data-pending-raid-countdown]': countdown, '[data-pending-raid-seconds]': secondsLabel,
        '[data-pending-raid-progress]': progress, '[data-pending-raid-ring]': ring};
    banner.querySelector = selector => controls[selector];
    vm.runInNewContext(source, {
        document: {querySelector: () => banner, createElement: () => new Element(), addEventListener: (name, callback) => { events[name] = callback; }, body: {append: element => body.push(element)}},
        getComputedStyle: element => ({borderRadius: element === banner ? '8px' : '9px', borderWidth: '1px',
            borderColor: element === banner ? 'rgb(139, 92, 246)' : 'rgb(90, 90, 90)', borderStyle: 'solid', background: 'rgb(24, 27, 33)',
            marginBottom: '8px', paddingTop: '9px', paddingBottom: '12px'}),
        window: {matchMedia: () => ({matches: reduced}), location: {assign: url => visits.push(url)}}, Date: {now: () => now * 1000, parse: Date.parse}, URLSearchParams,
        requestAnimationFrame: callback => callback(), setInterval: callback => { intervals.set(++nextInterval, callback); return nextInterval; }, clearInterval: id => intervals.delete(id),
        fetch: (url, options) => new Promise(resolve => requests.push({url, options,
            respond: (payload, ok = true) => resolve({ok, json: async () => payload})}))
    });
    return {banner, channel, text, description, cancel, avatar, requests, events, intervals, body, follow, visits, countdown, secondsLabel, progress, ring,
        advance: seconds => { now += seconds; [...intervals.values()].forEach(callback => callback()); }};
}
const raid = {login: 'target', display_name: 'Target', target_id: '2', expires_at: 190};
const flush = () => new Promise(resolve => setImmediate(resolve));

test('a profile picture loaded later appears without restarting raid progress', async () => {
    const app = setup();
    app.events['dashboard-raid-started']({detail: {raid}});
    assert.equal(app.avatar.hidden, true);
    const animation = app.progress.animation;
    app.advance(3);
    const image = 'https://static-cdn.jtvnw.net/jtv_user_pictures/target.png';
    app.requests[1].respond({raid: {...raid, profile_image_url: image}}); await flush();
    assert.equal(app.avatar.hidden, false);
    assert.equal(app.avatar.src, image);
    assert.equal(app.progress.animation, animation);
    assert.equal(app.secondsLabel.textContent, '87');
});

test('raiding description refreshes current viewers during the countdown', async () => {
    const app = setup(); app.events['dashboard-raid-started']({detail: {raid: {...raid, viewer_count: 42}}});
    assert.equal(app.description.textContent, 'Raiding with 43 viewers');
    app.advance(3);
    app.requests[1].respond({raid: {...raid, viewer_count: 1}}); await flush();
    assert.equal(app.description.textContent, 'Raiding with 2 viewers');
    const unknown = setup(); unknown.events['dashboard-raid-started']({detail: {raid}});
    assert.equal(unknown.description.textContent, 'Raiding');
    const zero = setup(); zero.events['dashboard-raid-started']({detail: {raid: {...raid, viewer_count: 0}}});
    assert.equal(zero.description.textContent, 'Raiding with 1 viewer');
});

test('follow raid adds one immediately without accumulating or changing confirmed counts', async () => {
    const app = setup(false, false);
    app.events['dashboard-raid-started']({detail: {raid: {...raid, viewer_count: 0}}});
    assert.equal(app.description.textContent, 'Raiding with 0 viewers');
    app.follow.checked = true; app.follow.handlers.change();
    assert.equal(app.description.textContent, 'Raiding with 1 viewer');
    app.follow.handlers.change();
    assert.equal(app.description.textContent, 'Raiding with 1 viewer');
    app.follow.checked = false; app.follow.handlers.change();
    assert.equal(app.description.textContent, 'Raiding with 0 viewers');
    app.follow.checked = true; app.advance(3);
    app.requests[1].respond({raid: {...raid, completed: true, viewer_count: 5}}); await flush();
    assert.equal(app.description.textContent, 'Raiding with 5 viewers');
    app.follow.checked = false; app.follow.handlers.change();
    assert.equal(app.description.textContent, 'Raiding with 5 viewers');
});

test('restored confirmations preserve zero and never guess missing or invalid counts', async () => {
    for (const count of [0, 5, undefined, null, -1, true, '42']) {
        const app = setup();
        app.requests[0].respond({raid: {...raid, completed: true, viewer_count: count}}); await flush();
        assert.equal(app.description.textContent, Number.isSafeInteger(count) && count >= 0
            ? `Raiding with ${count} viewers` : 'Raiding');
    }
});

test('raid line and circular timer count down using the original start and expiry', async () => {
    const app = setup();
    app.events['dashboard-raid-started']({detail: {raid: {...raid, created_at: new Date(100000).toISOString()}}});
    assert.equal(app.secondsLabel.textContent, '90');
    assert.equal(app.progress.style.transform, 'scaleX(1)');
    assert.equal(app.ring.style.strokeDashoffset, '0');
    assert.equal(app.progress.animation.options.duration, 90000);
    assert.equal(app.progress.animation.frames[1].transform, 'scaleX(0)');
    assert.equal(app.ring.animation.frames[1].strokeDashoffset, '1');
    app.advance(45);
    assert.equal(app.secondsLabel.textContent, '45');
    assert.equal(app.progress.style.transform, 'scaleX(0.5)');
    assert.equal(app.ring.style.strokeDashoffset, '0.5');
    assert.equal(app.countdown.attributes['aria-label'], '45 seconds remaining');
    app.advance(45);
    assert.equal(app.secondsLabel.textContent, '0');
    assert.equal(app.progress.style.transform, 'scaleX(0)');
    assert.equal(app.progress.animation.cancelled, true);
    assert.equal(app.ring.animation.cancelled, true);
    assert.match(app.text.textContent, /Countdown elapsed/);
});

test('restoring a raid resumes progress and cancellation removes its animations', async () => {
    const app = setup();
    app.requests[0].respond({raid: {...raid, created_at: new Date(10000).toISOString(), expires_at: 100}});
    await flush();
    assert.equal(app.secondsLabel.textContent, '0');
    assert.equal(app.progress.style.transform, 'scaleX(0)');
    const active = setup();
    active.requests[0].respond({raid: {...raid, created_at: new Date(55000).toISOString(), expires_at: 145}});
    await flush();
    assert.equal(active.secondsLabel.textContent, '45');
    assert.equal(active.progress.animation.frames[0].transform, 'scaleX(0.5)');
    assert.equal(active.ring.animation.frames[0].strokeDashoffset, '0.5');
    assert.equal(active.progress.animation.options.duration, 45000);
    const cancelled = active.cancel.handlers.click();
    active.requests[1].respond({raid: null}); await cancelled;
    active.banner.finish(); await flush();
    assert.equal(active.banner.hidden, true);
    assert.equal(active.progress.animation.cancelled, true);
    assert.equal(active.ring.animation.cancelled, true);
});

test('confirmed completion clears progress, and reduced motion uses static timed updates', async () => {
    const app = setup(); app.events['dashboard-raid-started']({detail: {raid}});
    app.advance(3);
    app.requests[1].respond({raid: {...raid, completed: true}}); await flush();
    assert.equal(app.progress.hidden, true);
    assert.equal(app.countdown.hidden, true);
    assert.equal(app.ring.animation.cancelled, true);
    const reduced = setup(true); reduced.events['dashboard-raid-started']({detail: {raid}});
    assert.equal(reduced.progress.animation, undefined);
    reduced.advance(45);
    assert.equal(reduced.secondsLabel.textContent, '45');
    assert.equal(reduced.progress.style.transform, 'scaleX(0.5)');
    assert.equal(reduced.ring.style.strokeDashoffset, '0.5');
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.match(styles, /\.dashboard-raid-progress \{[^}]*bottom: 0;[^}]*transform-origin: left center/);
});

test('accepted raid appears in chat and countdown expiry does not claim completion', () => {
    const app = setup(); app.events['dashboard-raid-started']({detail: {raid}});
    assert.equal(app.banner.hidden, false);
    assert.equal(app.channel.textContent, 'Target');
    assert.equal(app.channel.href, 'https://www.twitch.tv/target');
    assert.equal(app.text.textContent, '');
    assert.equal(app.secondsLabel.textContent, '90');
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
    assert.equal(app.banner.hidden, false);
    assert.equal(app.banner.animation.frames[1].transform, 'translateY(-80px)');
    assert.equal(app.banner.animation.frames[1].height, '0px');
    assert.equal(app.banner.animation.options.duration, 240);
    assert.equal(app.intervals.size, 1); // Continue discovering raids started outside the browser.
    app.banner.finish(); await flush();
    assert.equal(app.banner.hidden, true);
});

test('discovers externally started raids without refreshing and observes external cancellation', async () => {
    const app = setup(true, false);
    app.requests[0].respond({raid: null}); await flush();
    app.advance(3);
    app.requests[1].respond({raid: {...raid, viewer_count: 8}}); await flush();
    assert.equal(app.banner.hidden, false);
    assert.equal(app.channel.textContent, 'Target');
    assert.equal(app.description.textContent, 'Raiding with 8 viewers');
    assert.equal(app.follow.checked, false);
    app.advance(3);
    app.requests[2].respond({raid: null}); await flush();
    assert.equal(app.banner.hidden, true);
    app.advance(3);
    app.requests[3].respond({raid: {...raid, target_id: '3', login: 'next', display_name: 'Next'}}); await flush();
    assert.equal(app.channel.textContent, 'Next');
    assert.equal(app.banner.hidden, false);
});

test('discovery ignores completed old raids and follows a newly discovered raid once', async () => {
    const app = setup();
    app.requests[0].respond({raid: null}); await flush();
    app.advance(3);
    app.requests[1].respond({raid: {...raid, completed: true}}); await flush();
    assert.equal(app.banner.hidden, true);
    assert.deepEqual(app.visits, []);
    app.advance(3);
    app.requests[2].respond({raid}); await flush();
    app.advance(90);
    assert.deepEqual(app.visits, ['https://www.twitch.tv/target']);
});

test('new raid interrupts an old cancellation slide without hiding the new banner', async () => {
    const app = setup(); app.events['dashboard-raid-started']({detail: {raid}});
    const cancel = app.cancel.handlers.click();
    app.requests[1].respond({raid: null}); await cancel;
    const staleFinish = app.banner.finish;
    app.events['dashboard-raid-started']({detail: {raid: {...raid, login: 'newtarget', display_name: 'New Target'}}});
    staleFinish(); await flush();
    assert.equal(app.banner.hidden, false);
    assert.equal(app.channel.textContent, 'New Target (newtarget)');
    assert.equal(app.cancel.disabled, false);
});

test('reduced motion hides a cancelled raid immediately without a slide', async () => {
    const app = setup(true); app.events['dashboard-raid-started']({detail: {raid}});
    const cancel = app.cancel.handlers.click();
    app.requests[1].respond({raid: null}); await cancel;
    assert.equal(app.banner.hidden, true);
    assert.equal(app.banner.animation, undefined);
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
    const frame = app.body[0];
    assert.equal(frame.child, flyer);
    assert.equal(flyer.animation.options.duration, 650);
    assert.equal(flyer.animation.frames[1].transform, 'translate(70px,0px) scale(0.4)');
    assert.equal(frame.animation.frames[1].transform, 'translate(-80px,-70px)');
    assert.equal(frame.animation.frames[1].width, '300px');
    assert.equal(frame.animation.frames[1].height, '80px');
    assert.equal(frame.animation.frames[1].borderRadius, '8px');
    assert.equal(frame.animation.frames[1].borderColor, 'rgb(139, 92, 246)');
    assert.equal(frame.animation.frames[1].borderWidth, '1px');
    assert.equal(flyer.animation.frames[1].opacity, 1);
    assert.equal(flyer.animation.frames[1].offset, .85);
    assert.equal(flyer.animation.frames[2].transform, flyer.animation.frames[1].transform);
    assert.equal(flyer.animation.frames[2].opacity, 0);
    assert.equal(app.banner.classes.has('is-arriving'), true);
    frame.finish(); await flush();
    assert.equal(flyer.removed, true);
    assert.equal(frame.removed, true);
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
    assert.equal(app.text.textContent, '');
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
