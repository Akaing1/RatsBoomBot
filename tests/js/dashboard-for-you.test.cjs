const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {remaining, formatTime} = require('../../web/static/js/dashboard-for-you.js');

test('absolute deadlines handle sleep, expiry and long timers', () => {
    assert.equal(remaining(2200, 1000), 1200);
    assert.equal(remaining(2200, 2199.1), 1);
    assert.equal(remaining(2200, 2300), 0);
    assert.equal(formatTime(1200), '20:00');
    assert.equal(formatTime(3661), '1:01:01');
    assert.equal(formatTime(604800), '168:00:00');
});

function harness(initial) {
    const nodes = new Map(), intervals = [], listeners = {};
    function node(selector) {
        if (!nodes.has(selector)) nodes.set(selector, {
            hidden: false, value: '', textContent: '', disabled: false, dataset: {}, events: {}, elements: [], open: false,
            classList: {toggle() {}}, setAttribute() {}, focus() {},
            addEventListener(name, callback) {this.events[name] = callback;},
            querySelector: node, querySelectorAll() {return [];},
            showModal() {this.open = true;}, close() {this.open = false;},
        });
        return nodes.get(selector);
    }
    const root = node('[data-for-you]'); root.dataset.csrfToken = 'secret';
    let state = {...initial}, failSave = false;
    const context = {
        document: {querySelector: node, addEventListener(name, fn) {listeners[name] = fn;}, hidden: false},
        window: {addEventListener(name, fn) {listeners[name] = fn;}},
        setInterval(fn) {intervals.push(fn);}, Date, URLSearchParams,
        fetch: async (url, options) => {
            if (options.method === 'POST') {
                const body = options.body;
                assert.equal(body.get('csrf_token'), 'secret');
                if (failSave) return {ok: false, json: async () => ({detail: 'Save failed'})};
                if (body.get('action') === 'notes') {state.notes = body.get('notes'); state.notes_revision++;}
                if (body.get('action') === 'clear') state.timer_id = null;
            }
            return {ok: true, json: async () => ({...state})};
        },
    };
    vm.runInNewContext(fs.readFileSync('web/static/js/dashboard-for-you.js', 'utf8'), context);
    return {node, intervals, listeners, state, fail() {failSave = true;}};
}
const flush = () => new Promise(resolve => setImmediate(resolve));
const initial = () => ({notes: 'Saved note', notes_revision: 0, timer_id: null, timer_label: '', timer_due_at: null, server_now: Date.now() / 1000});

test('polling preserves unsaved notes and failed saves remain recoverable', async () => {
    const h = harness(initial()); await flush();
    const notes = h.node('[data-fy-notes]');
    assert.equal(notes.value, 'Saved note');
    notes.value = 'Unsaved draft'; notes.events.input();
    h.state.notes = 'Other tab'; h.state.notes_revision = 1;
    h.intervals[1](); await flush();
    assert.equal(notes.value, 'Unsaved draft');
    h.fail(); h.node('[data-fy-save]').events.click(); await flush();
    assert.equal(h.node('[data-fy-save-status]').textContent, 'Not saved');
    assert.equal(notes.value, 'Unsaved draft');
    assert.equal(h.node('[data-fy-save]').disabled, false);
    h.intervals[1](); await flush();
    assert.equal(h.node('[data-fy-error]').textContent, 'Save failed');
});

test('overdue timer opens safely on load and can be acknowledged from front side', async () => {
    const s = initial(); Object.assign(s, {timer_id: 'timer', timer_due_at: s.server_now - 1, timer_label: '<img src=x onerror=alert(1)>'});
    const h = harness(s); await flush();
    assert.equal(h.node('[data-fy-dialog]').open, true);
    assert.equal(h.node('[data-fy-timer-action]').textContent, 'Cancel');
    h.node('[data-fy-dismiss]').events.click(); await flush();
    assert.equal(h.node('[data-fy-dialog]').open, false);
    assert.equal(h.state.timer_id, null);
    h.intervals[1](); await flush();
    assert.equal(h.node('[data-fy-dialog]').open, false);
});

test('a timer cancelled in another tab does not show an expired popup', async () => {
    const s = initial(); Object.assign(s, {timer_id: 'timer', timer_due_at: s.server_now + 10, timer_label: 'Pizza'});
    const h = harness(s); await flush();
    h.state.timer_id = null;
    h.intervals[1](); await flush();
    assert.equal(h.node('[data-fy-dialog]').open, false);
    assert.equal(h.node('[data-fy-running]').hidden, true);
});


test('single timer action cancels without validating duration and restores start state', async () => {
    const s = initial(); Object.assign(s, {timer_id: 'timer', timer_due_at: s.server_now + 60});
    const h = harness(s); await flush();
    const action = h.node('[data-fy-timer-action]');
    assert.equal(action.textContent, 'Cancel');
    assert.equal(action.formNoValidate, true);
    await h.node('[data-fy-timer-form]').events.submit({preventDefault() {}});
    await flush();
    assert.equal(h.state.timer_id, null);
    assert.equal(action.textContent, 'Start timer');
    assert.equal(action.formNoValidate, false);
    assert.equal(h.node('[data-fy-running]').hidden, true);
});

test('failed cancellation keeps the active timer available to retry', async () => {
    const s = initial(); Object.assign(s, {timer_id: 'timer', timer_due_at: s.server_now + 60});
    const h = harness(s); await flush(); h.fail();
    await h.node('[data-fy-timer-form]').events.submit({preventDefault() {}});
    await flush();
    assert.equal(h.state.timer_id, 'timer');
    assert.equal(h.node('[data-fy-timer-action]').textContent, 'Cancel');
    assert.equal(h.node('[data-fy-error]').textContent, 'Save failed');
});
