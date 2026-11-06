const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web/static/js/channel-authorization.js', 'utf8');

function element() {
    return {hidden: true, disabled: false, textContent: '', listeners: {},
        addEventListener(name, callback) { this.listeners[name] = callback; }};
}
function banner(dataset = {}) {
    const result = element();
    result.dataset = dataset;
    result.message = element();
    result.connect = element();
    result.retry = element();
    result.querySelector = selector => ({
        '[data-channel-auth-message]': result.message,
        '[data-channel-auth-connect]': result.connect,
        '[data-channel-auth-retry]': result.retry,
    })[selector];
    return result;
}
async function setup(fetch) {
    const twitch = banner();
    const youtube = banner({authPlatform: 'YouTube', authEndpoint: '/channel/api/youtube/authorization'});
    const listeners = [];
    vm.runInNewContext(source, {
        document: {querySelectorAll: () => [twitch, youtube]},
        window: {addEventListener: (name, callback) => listeners.push([name, callback])},
        fetch, AbortController, setTimeout, clearTimeout,
    });
    await new Promise(resolve => setImmediate(resolve));
    return {twitch, youtube, listeners};
}
const response = required => ({ok: true, status: 200, redirected: false, json: async () => ({required})});

test('YouTube reauth is independent of healthy Twitch and clears after reconnect', async () => {
    let required = true;
    const calls = [];
    const {twitch, youtube} = await setup(async (url, options) => {
        calls.push(url);
        assert.equal(options.cache, 'no-store');
        return response(url.includes('youtube') && required);
    });
    assert.equal(twitch.hidden, true);
    assert.equal(youtube.hidden, false);
    assert.equal(youtube.connect.hidden, false);
    assert.match(youtube.message.textContent, /YouTube authorization/);
    assert.deepEqual(calls, ['/channel/api/authorization', '/channel/api/youtube/authorization']);
    required = false;
    await youtube.retry.listeners.click();
    assert.equal(youtube.hidden, true);
});

test('a temporary YouTube failure offers retry without reauthorization', async () => {
    const {twitch, youtube} = await setup(async url => url.includes('youtube')
        ? {ok: false, status: 503} : response(true));
    assert.equal(twitch.connect.hidden, false);
    assert.equal(youtube.hidden, false);
    assert.equal(youtube.connect.hidden, true);
    assert.equal(youtube.retry.hidden, false);
    assert.match(youtube.message.textContent, /Could not check YouTube/);
});

test('both disconnected or healthy integrations stay hidden', async () => {
    const {twitch, youtube} = await setup(async () => response(false));
    assert.equal(twitch.hidden, true);
    assert.equal(youtube.hidden, true);
});

function setupTwitch() {
    const nodes = new Map(); const calls = []; const events = {};
    const banner = {hidden: true, dataset: {}, querySelector(key) {
        if (!nodes.has(key)) nodes.set(key, {hidden: true, textContent: '', addEventListener(type, fn) {this[type] = fn;}});
        return nodes.get(key);
    }};
    vm.runInNewContext(fs.readFileSync('web/static/js/channel-authorization.js', 'utf8'), {
        document: {querySelectorAll: () => [banner]}, window: {addEventListener(type, fn) {events[type] = fn;}},
        AbortController, setTimeout: () => 1, clearTimeout() {},
        fetch(url, options) {return new Promise((resolve, reject) => calls.push({url, options, resolve, reject}));}
    });
    return {banner, nodes, calls, events};
}
const flush = () => new Promise(resolve => setImmediate(resolve));
test('newly required permissions show banner; fresh grant hides it after page restore', async () => {
    const s = setupTwitch(); assert.equal(s.calls.length, 1);
    s.calls[0].resolve({ok: true, json: async () => ({required: true})}); await flush();
    assert.equal(s.banner.hidden, false); assert.equal(s.nodes.get('[data-channel-auth-connect]').hidden, false);
    s.events.pageshow({persisted: true});
    s.calls[1].resolve({ok: true, json: async () => ({required: false})}); await flush();
    assert.equal(s.banner.hidden, true);
});
test('temporary failures offer retry instead of claiming new permissions are needed', async () => {
    const s = setupTwitch(); s.calls[0].reject(Error('offline')); await flush();
    assert.equal(s.banner.hidden, false); assert.equal(s.nodes.get('[data-channel-auth-connect]').hidden, true);
    const retry = s.nodes.get('[data-channel-auth-retry]'); assert.equal(retry.hidden, false);
    retry.click(); retry.click(); assert.equal(s.calls.length, 2);
    s.calls[1].resolve({ok: true, json: async () => ({required: false})}); await flush();
    assert.equal(s.banner.hidden, true);
});
test('expired session shows reconnect action', async () => {
    const s = setupTwitch(); s.calls[0].resolve({status: 401}); await flush();
    assert.equal(s.banner.hidden, false); assert.equal(s.nodes.get('[data-channel-auth-connect]').hidden, false);
});
