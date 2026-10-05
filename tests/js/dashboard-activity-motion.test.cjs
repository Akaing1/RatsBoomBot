const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup(reduced = false) {
    const timers = [];
    const window = {
        matchMedia: () => ({matches: reduced}),
        getComputedStyle: () => ({paddingTop: '13px', paddingBottom: '13px'}),
        setTimeout: callback => { timers.push(callback); },
        requestAnimationFrame: () => 1,
        cancelAnimationFrame() {}
    };
    vm.runInNewContext(fs.readFileSync('web/static/js/dashboard-activity-motion.js', 'utf8'), {window, performance: {now: () => 0}, WeakMap, WeakSet, Set});
    const container = {
        items: [], scrollTop: 0, isConnected: true, hidden: false,
        closest() { return this.hidden ? {} : null; },
        querySelectorAll() { return this.items; },
        querySelector(selector) { return selector === '.activity-list' ? this : null; },
        getBoundingClientRect() { return {top: 0}; },
        addEventListener() {}, removeEventListener() {},
        insertBefore(row, next) {
            row.parentElement = this;
            const index = this.items.indexOf(next);
            if (index < 0) this.items.push(row);
            else this.items.splice(index, 0, row);
        }
    };
    function row(id) {
        const classes = new Set();
        return {
            dataset: {activityKey: id}, parentElement: container, isConnected: true,
            classList: {contains: name => classes.has(name), add: name => classes.add(name), remove: (...names) => names.forEach(name => classes.delete(name))},
            style: {setProperty() {}},
            getBoundingClientRect() { return {height: 54, top: 0, bottom: 54}; },
            addEventListener() {}, removeEventListener() {}, setAttribute() {},
            remove() { container.items = container.items.filter(item => item !== this); this.isConnected = false; }
        };
    }
    return {motion: window.dashboardActivityMotion, container, row, timers};
}

test('initial history and unchanged polling do not fold every row again', () => {
    const {motion, container, row} = setup();
    const first = row('a');
    motion.reconcile(container, () => { container.items = [first]; });
    assert.equal(first.classList.contains('is-activity-appearing'), false);
    const refreshed = row('a');
    motion.reconcile(container, () => { container.items = [refreshed]; });
    assert.equal(refreshed.classList.contains('is-activity-appearing'), false);
});

test('new events fold in and removed events slide out without replaying survivors', () => {
    const {motion, container, row, timers} = setup();
    const removed = row('a');
    motion.reconcile(container, () => { container.items = [removed, row('b')]; });
    const added = row('c');
    const survivor = row('b');
    motion.reconcile(container, () => { container.items = [added, survivor]; });
    assert.equal(added.classList.contains('is-activity-appearing'), true);
    assert.equal(survivor.classList.contains('is-activity-appearing'), false);
    assert.equal(removed.classList.contains('is-activity-removing'), true);
    assert.equal(removed.inert, true);
    timers.forEach(callback => callback());
    assert.equal(container.items.includes(removed), false);
    assert.equal(added.classList.contains('is-activity-appearing'), false);
});

test('AutoMod removal stays visible during the exit then removes the row', () => {
    const {motion, container, row, timers} = setup();
    const held = row('held');
    container.items = [held];
    motion.remove(container, held);
    assert.equal(container.items.includes(held), true);
    assert.equal(held.classList.contains('is-activity-removing'), true);
    timers.forEach(callback => callback());
    assert.equal(container.items.length, 0);
});

test('new-entry highlight clears independently of the folding animation', () => {
    const {motion, row, timers} = setup();
    const entry = row('new');
    motion.highlight(entry);
    assert.equal(entry.classList.contains('is-new-entry'), true);
    timers.forEach(callback => callback());
    assert.equal(entry.classList.contains('is-new-entry'), false);
    const reduced = setup(true);
    const quiet = reduced.row('quiet');
    reduced.motion.highlight(quiet);
    assert.equal(quiet.classList.contains('is-new-entry'), false);
});

test('reduced motion and hidden panels remove immediately', () => {
    for (const reduced of [true, false]) {
        const {motion, container, row} = setup(reduced);
        container.hidden = !reduced;
        const held = row('held');
        container.items = [held];
        motion.remove(container, held);
        assert.equal(container.items.length, 0);
    }
});

test('switching tabs cancels the prior transition and respects reduced motion', () => {
    let played = 0, cancelled = 0;
    const panel = {animate() { played++; return {cancel() { cancelled++; }}; }};
    const {motion} = setup();
    motion.switchTab(panel);
    motion.switchTab(panel);
    assert.equal(played, 2);
    assert.equal(cancelled, 1);
    setup(true).motion.switchTab(panel);
    assert.equal(played, 2);
});
