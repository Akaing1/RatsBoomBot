const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function setup() {
    const nodes = new Map(), events = {}, timers = new Map(), calls = []; let serial = 0;
    function node() { return {textContent: '', children: [], scrollTop: 0, append(...items) {this.children.push(...items);}, replaceChildren(...items) {this.children = items;}, addEventListener(type, fn) {this[type] = fn;}}; }
    const root = {dataset: {stateUrl: '/admin/channels/123/api/monitor'}, querySelector(key) {if (!nodes.has(key)) nodes.set(key, node()); return nodes.get(key);}};
    const document = {hidden: false, querySelector: () => root, createElement: node, addEventListener(type, fn) {events[type] = fn;}};
    vm.runInNewContext(fs.readFileSync('web/static/js/admin-channel-monitor.js', 'utf8'), {
        document, window: {dispatchEvent() {}, addEventListener() {}}, CustomEvent: class {}, AbortController, Date, Math,
        setTimeout(fn, ms) {timers.set(++serial, {fn, ms}); return serial;}, clearTimeout(id) {timers.delete(id);},
        fetch(url, options) {return new Promise((resolve, reject) => {calls.push({url, options, resolve, reject}); options.signal.addEventListener('abort', () => reject(Error('aborted')));});}
    });
    return {nodes, events, timers, calls, document};
}
const flush = () => new Promise(resolve => setImmediate(resolve));
const success = {ok: true, status: 200, json: async () => ({is_live: true, activity: {feed: [{reward_title: '<img onerror=bad>'}], automod: [], mod_actions: []}})};
test('bounded serial updates render untrusted activity as text', async () => {
    const s = setup(); assert.equal(s.calls.length, 1);
    s.calls[0].resolve(success); await flush();
    assert.equal(s.nodes.get('[data-monitor-feed="feed"]').children[0].children[0].textContent, '<img onerror=bad>');
    assert.deepEqual([...s.timers.values()].map(timer => timer.ms), [5000]);
});
test('pause and hidden tabs abort requests; resume loads fresh state', async () => {
    const s = setup(); s.nodes.get('[data-monitor-pause]').click(); await flush();
    assert.equal(s.calls[0].options.signal.aborted, true); assert.equal(s.timers.size, 0);
    s.nodes.get('[data-monitor-pause]').click(); assert.equal(s.calls.length, 2);
    s.document.hidden = true; s.events.visibilitychange(); await flush(); assert.equal(s.timers.size, 0);
    s.document.hidden = false; s.events.visibilitychange(); assert.equal(s.calls.length, 3);
    s.calls[2].resolve(success); await flush();
});
test('authentication failures stop retries, network failures back off', async () => {
    const s = setup(); s.calls[0].reject(Error('offline')); await flush();
    assert.deepEqual([...s.timers.values()].map(timer => timer.ms), [10000]);
    [...s.timers.values()][0].fn(); s.calls[1].resolve({status: 401}); await flush();
    assert.equal(s.nodes.get('[data-monitor-pause]').disabled, true); assert.equal(s.timers.size, 0);
});
