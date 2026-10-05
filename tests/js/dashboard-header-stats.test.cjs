const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('stat toggles and refreshes still work after moving into the mobile sidebar', async () => {
    const value = {textContent: '12', hidden: false};
    const classes = new Set();
    let click;
    const attributes = {};
    const button = {
        dataset: {dashboardStat: 'viewers'},
        classList: {toggle(name, enabled) { if (enabled) classes.add(name); else classes.delete(name); }},
        querySelector(selector) { return selector === 'span' ? {textContent: 'Viewers'} : value; },
        setAttribute(name, content) { attributes[name] = content; },
        addEventListener(event, handler) { if (event === 'click') click = handler; }
    };
    const dashboard = {style: {setProperty() {}}, querySelector() { return null; }};
    const container = {
        dataset: {channelId: 'test', refreshUrl: '/stats'},
        closest() { return null; },
        querySelectorAll() { return [button]; },
        querySelector(selector) {
            if (selector === '[data-stream-status]') return null;
            return selector.includes('[data-dashboard-stat-value]') ? value : button;
        }
    };
    const timers = [];
    const storage = new Map();
    const context = {
        document: {hidden: false, querySelector(selector) { return selector === '[data-dashboard-header-stats]' ? container : dashboard; }, addEventListener() {}},
        window: {localStorage: {getItem(key) { return storage.get(key); }, setItem(key, content) { storage.set(key, content); }}, setInterval(callback) { timers.push(callback); }, addEventListener() {}},
        CSS: {escape: String},
        fetch: async () => ({ok: true, json: async () => ({stats: [{key: 'viewers', display_value: '42'}]})})
    };
    vm.runInNewContext(fs.readFileSync('web/static/js/dashboard-header-stats.js', 'utf8'), context);
    assert.equal(typeof click, 'function');
    click();
    assert.equal(value.hidden, true);
    assert.equal(attributes['aria-pressed'], 'true');
    assert.deepEqual(JSON.parse([...storage.values()][0]), ['viewers']);
    await timers[0]();
    assert.equal(value.textContent, '42');
    click();
    assert.equal(value.hidden, false);
});
