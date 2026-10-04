const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup() {
    const handlers = {};
    const timers = [];
    const observers = [];
    class MutationObserver {
        constructor(callback) { this.callback = callback; observers.push(this); }
        observe() {}
        disconnect() {}
    }
    class Element {
        constructor(tag, attributes = {}, caption = '') {
            this.tag = tag; this.attributes = attributes; this.textContent = caption;
            this.dataset = {}; this.labels = []; this.parentLabel = null;
        }
        getAttribute(key) { return this.attributes[key] || null; }
        setAttribute(key, value) { this.attributes[key] = value; }
        removeAttribute(key) { delete this.attributes[key]; }
        contains(element) { return element === this; }
        getBoundingClientRect() { return {left: 100, right: 300, top: 100, bottom: 130, width: 200, height: 30}; }
        closest(selector) {
            if (selector.startsWith('[data-queue-count]')) return this.matches(selector) ? this : null;
            if (selector === 'label') return this.parentLabel;
            if (selector.includes('button') && ['button', 'a', 'input', 'select', 'textarea', 'editable'].includes(this.tag)) return this;
            if (selector === 'img[alt], [title]' && (this.tag === 'img' || this.attributes.title)) return this;
            return null;
        }
        matches(selector) { return selector.split(',').map(value => value.trim()).some(value =>
            value.startsWith('[') ? Object.hasOwn(this.attributes, value.slice(1, -1))
                : value.startsWith('.') ? String(this.attributes.class || '').split(' ').includes(value.slice(1)) : value === this.tag); }
        querySelector() { return null; }
    }
    let tooltip;
    vm.runInNewContext(fs.readFileSync('web/static/js/hover-labels.js', 'utf8'), {
        Element, MutationObserver, window: {MutationObserver, innerWidth: 800, innerHeight: 600, addEventListener() {}, setTimeout(callback, delay) { timers.push({callback, delay}); return timers.length; }, clearTimeout(id) { if (id) timers[id - 1].cancelled = true; }},
        document: {createElement() { const element = new Element('div'); element.style = {}; return element; }, body: {appendChild(element) { tooltip = element; }}, addEventListener: (event, handler) => { handlers[event] = handler; }, getElementById: () => ({textContent: 'Number of viewers'})}
    });
    return {Element, timers, observers, tooltip, handlers, hover: target => handlers.pointerover({target, type: 'pointerover'}), focus: target => handlers.focusin({target, type: 'focusin'})};
}

test('adds descriptive labels to controls and dynamically added elements', () => {
    const {Element, hover} = setup();
    const button = new Element('button', {'aria-label': 'Pin message'}, '📌');
    hover(button); assert.equal(button.attributes.title, 'Pin message');
    const next = new Element('button', {}, 'Next 4');
    hover(next); assert.equal(next.attributes.title, 'Next 4');
    next.textContent = 'Next 5'; hover(next); assert.equal(next.attributes.title, 'Next 5');
    const field = new Element('editable', {}, 'Some category'); field.dataset.channelField = 'game';
    hover(field); assert.equal(field.attributes.title, 'Some category');
    field.textContent = 'New category'; hover(field);
    assert.equal(field.attributes.title, 'New category');
    const emote = new Element('img', {alt: 'Kappa'});
    hover(emote); assert.equal(emote.attributes.title, 'Kappa');
});

test('live values update an open tooltip without restarting the hover delay', () => {
    const ui = setup();
    for (const attribute of ['data-ad-status', 'data-ad-status-mirror', 'data-queue-count', 'data-dashboard-points-lost']) {
        const bubble = new ui.Element('div', {[attribute]: '', 'aria-hidden': 'true'}, 'Current value');
        ui.hover(bubble); ui.timers.at(-1).callback();
        const timerCount = ui.timers.length;
        bubble.textContent = 'Updated value';
        ui.observers.at(-1).callback();
        ui.handlers.pointerout({relatedTarget: null, clientX: 150, clientY: 115});
        ui.handlers.scroll({target: ui.tooltip});
        assert.equal(ui.tooltip.hidden, false);
        assert.equal(ui.tooltip.textContent, 'Updated value');
        assert.equal(ui.timers.length, timerCount);
    }
});

test('custom tooltip appears after 150ms and restores native text on leaving', () => {
    const ui = setup();
    const button = new ui.Element('button', {'aria-label': 'Reply to message'});
    ui.hover(button);
    assert.equal(ui.tooltip.hidden, true);
    assert.equal(ui.timers.at(-1).delay, 150);
    ui.timers.at(-1).callback();
    assert.equal(ui.tooltip.hidden, false);
    assert.equal(ui.tooltip.textContent, 'Reply to message');
    assert.equal(button.attributes.title, undefined);
    ui.handlers.pointerout({relatedTarget: null});
    assert.equal(ui.tooltip.hidden, true);
    assert.equal(button.attributes.title, 'Reply to message');
});

test('stat tooltips show actual values even when the count is hidden', () => {
    const {Element, hover} = setup();
    const stat = new Element('button', {title: 'Hide viewers count'});
    stat.dataset.dashboardStat = 'viewers';
    const value = {textContent: '123', hidden: true};
    stat.querySelector = selector => selector === 'span' ? {textContent: 'Viewers'}
        : selector === '[data-dashboard-stat-value]' ? value : null;
    hover(stat); assert.equal(stat.attributes.title, 'Viewers: 123');
    value.textContent = '456'; hover(stat);
    assert.equal(stat.attributes.title, 'Viewers: 456');
});

test('preserves explicit descriptions and refreshes changing accessible names', () => {
    const {Element, hover} = setup();
    const ad = new Element('button', {title: 'Start a 90-second ad now'}, '+1.5 min');
    hover(ad); assert.equal(ad.attributes.title, 'Start a 90-second ad now');
    const lock = new Element('button', {'aria-label': 'Lock automatic chat resizing'});
    hover(lock);
    lock.attributes['aria-label'] = 'Unlock automatic chat resizing';
    hover(lock); assert.equal(lock.attributes.title, 'Unlock automatic chat resizing');
    lock.attributes.title = 'Custom explanation'; hover(lock);
    assert.equal(lock.attributes.title, 'Custom explanation');
});

test('uses associated labels and placeholders without exposing input values', () => {
    const {Element, hover, focus} = setup();
    const input = new Element('input'); input.labels = [{textContent: 'Duration'}];
    focus(input); assert.equal(input.attributes.title, 'Duration');
    const search = new Element('input', {placeholder: 'Search emotes…'});
    hover(search); assert.equal(search.attributes.title, 'Search emotes…');
    const password = new Element('input', {type: 'password', value: 'secret'});
    hover(password); assert.equal(password.attributes.title, undefined);
    const select = new Element('select', {'aria-labelledby': 'viewer-count'});
    hover(select); assert.equal(select.attributes.title, 'Number of viewers');
});

test('does not add tooltips to headings or ordinary static labels', () => {
    const {Element, hover} = setup();
    for (const tag of ['h3', 'label', 'span']) {
        const heading = new Element(tag, {}, 'Title');
        hover(heading); assert.equal(heading.attributes.title, undefined);
    }
});

test('queued and points-lost summaries show their current values', () => {
    const {Element, hover} = setup();
    const queue = new Element('small', {'data-queue-count': ''}, '12 queued');
    hover(queue); assert.equal(queue.attributes.title, '12 queued');
    queue.textContent = '15 queued'; hover(queue); assert.equal(queue.attributes.title, '15 queued');
    const points = new Element('div', {'data-dashboard-points-lost': ''}, 'Points lost 1,234');
    hover(points); assert.equal(points.attributes.title, 'Points lost 1,234');
});

test('filter row and checkbox share one tooltip containing only the filter name', () => {
    const ui = setup();
    const row = new ui.Element('label', {class: 'chat-filter-row', title: 'Click to toggle; right-click to solo'}, 'Mods');
    const checkbox = new ui.Element('input', {type: 'checkbox', title: 'Separate checkbox label'});
    row.parentLabel = row;
    checkbox.parentLabel = row;
    row.querySelector = selector => selector.includes('checkbox') ? checkbox : null;
    ui.hover(row);
    assert.equal(row.attributes.title, 'Mods');
    assert.equal(checkbox.attributes.title, undefined);
    const count = ui.timers.length;
    ui.hover(checkbox);
    assert.equal(ui.timers.length, count);
    ui.timers.at(-1).callback();
    assert.equal(ui.tooltip.textContent, 'Mods');
});

test('tooltips center on controls and stay inside the viewport edges', () => {
    const ui = setup();
    const button = new ui.Element('button', {'aria-label': 'Example'});
    ui.tooltip.getBoundingClientRect = () => ({width: 100, height: 30});
    button.getBoundingClientRect = () => ({left: 100, right: 300, top: 100, bottom: 130, width: 200});
    ui.hover(button); ui.timers.at(-1).callback();
    assert.equal(ui.tooltip.style.left, '150px');
    button.getBoundingClientRect = () => ({left: 0, right: 20, top: 100, bottom: 130, width: 20});
    ui.observers.at(-1).callback();
    assert.equal(ui.tooltip.style.left, '8px');
    button.getBoundingClientRect = () => ({left: 780, right: 800, top: 100, bottom: 130, width: 20});
    ui.observers.at(-1).callback();
    assert.equal(ui.tooltip.style.left, '692px');
});

test('navigation hover labels omit decorative icons even after title suppression', () => {
    const ui = setup();
    const link = new ui.Element('a', {title: 'Overview'}, '⌂ Overview');
    link.querySelector = selector => selector === '.nav-link-label, .sidebar-button-label' ? {textContent: 'Overview'} : null;
    ui.hover(link); ui.timers.at(-1).callback();
    assert.equal(ui.tooltip.textContent, 'Overview');
    ui.hover(link);
    assert.equal(ui.tooltip.textContent, 'Overview');
});
