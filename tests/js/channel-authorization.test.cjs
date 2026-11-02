const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function setup() {
    const nodes = new Map(); const calls = []; const events = {};
    const banner = {hidden: true, querySelector(key) {
        if (!nodes.has(key)) nodes.set(key, {hidden: true, textContent: '', addEventListener(type, fn) {this[type] = fn;}});
        return nodes.get(key);
    }};
    vm.runInNewContext(fs.readFileSync('web/static/js/channel-authorization.js', 'utf8'), {
        document: {querySelector: () => banner}, window: {addEventListener(type, fn) {events[type] = fn;}},
        AbortController, setTimeout: () => 1, clearTimeout() {},
        fetch(url, options) {return new Promise((resolve, reject) => calls.push({url, options, resolve, reject}));}
    });
    return {banner, nodes, calls, events};
}
const flush = () => new Promise(resolve => setImmediate(resolve));
test('newly required permissions show banner; fresh grant hides it after page restore', async () => {
    const s = setup(); assert.equal(s.calls.length, 1);
    s.calls[0].resolve({ok: true, json: async () => ({required: true})}); await flush();
    assert.equal(s.banner.hidden, false); assert.equal(s.nodes.get('[data-channel-auth-connect]').hidden, false);
    s.events.pageshow({persisted: true});
    s.calls[1].resolve({ok: true, json: async () => ({required: false})}); await flush();
    assert.equal(s.banner.hidden, true);
});
test('temporary failures offer retry instead of claiming new permissions are needed', async () => {
    const s = setup(); s.calls[0].reject(Error('offline')); await flush();
    assert.equal(s.banner.hidden, false); assert.equal(s.nodes.get('[data-channel-auth-connect]').hidden, true);
    const retry = s.nodes.get('[data-channel-auth-retry]'); assert.equal(retry.hidden, false);
    retry.click(); retry.click(); assert.equal(s.calls.length, 2);
    s.calls[1].resolve({ok: true, json: async () => ({required: false})}); await flush();
    assert.equal(s.banner.hidden, true);
});
test('expired session shows reconnect action', async () => {
    const s = setup(); s.calls[0].resolve({status: 401}); await flush();
    assert.equal(s.banner.hidden, false); assert.equal(s.nodes.get('[data-channel-auth-connect]').hidden, false);
});
