const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup({mobile = false, textRects = null} = {}) {
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
    const document = {createElement() { const element = new Element('div'); element.style = {}; return element; }, body: {appendChild(element) { tooltip = element; }}, addEventListener: (event, handler) => { handlers[event] = handler; }, getElementById: () => ({textContent: 'Number of viewers'})};
    if (textRects) {
        document.createTreeWalker = () => {
            let visited = false;
            return {nextNode() { if (visited) return null; visited = true; return {textContent: 'Label', parentElement: {closest: () => null}}; }};
        };
        document.createRange = () => ({selectNodeContents() {}, getClientRects: () => textRects});
    }
    vm.runInNewContext(fs.readFileSync('web/static/js/hover-labels.js', 'utf8'), {
        Element, MutationObserver, NodeFilter: {SHOW_TEXT: 4}, window: {MutationObserver, innerWidth: 800, innerHeight: 600, matchMedia: () => ({matches: mobile}), addEventListener() {}, setTimeout(callback, delay) { timers.push({callback, delay}); return timers.length; }, clearTimeout(id) { if (id) timers[id - 1].cancelled = true; }},
        document
    });
    return {Element, timers, observers, tooltip, handlers, hover: target => handlers.pointerover({target, type: 'pointerover'}), focus: target => handlers.focusin({target, type: 'focusin'})};
}

test('selected-value hovers show only the current option and refresh when it changes', () => {
    const {Element, hover, handlers} = setup();
    const language = new Element('select', {'data-hover-current-value': ''}, 'All languages English Japanese');
    language.labels = [{textContent: 'Language All languages English Japanese'}];
    language.selectedOptions = [{textContent: 'English'}];
    hover(language);
    assert.equal(language.attributes.title, 'English');
    language.selectedOptions = [{textContent: 'Japanese'}];
    handlers.input({target: language});
    assert.equal(language.attributes.title, 'Japanese');
    const event = new Element('select', {'data-hover-current-value': ''}, 'All events Drops Enabled');
    event.selectedOptions = [{textContent: 'Drops Enabled'}];
    hover(event);
    assert.equal(event.attributes.title, 'Drops Enabled');
});

test('explicit Search and Tags labels do not include duplicate labels or helper text', () => {
    const {Element, hover} = setup();
    for (const name of ['Search', 'Tags']) {
        const input = new Element('input', {'aria-label': name, title: name});
        input.labels = [{textContent: name}, {textContent: `${name} Maximum 25 characters`}];
        hover(input);
        assert.equal(input.attributes.title, name);
    }
});

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

test('pointer-only suggestions do not show hover labels on keyboard focus but still allow pointer hover', () => {
    const ui = setup();
    const suggestion = new ui.Element('button', {'data-hover-pointer-only': '', 'aria-label': 'Add VTuber'}, 'VTuber');
    ui.focus(suggestion);
    assert.equal(ui.timers.length, 0);
    assert.equal(suggestion.getAttribute('title'), null);
    ui.hover(suggestion);
    ui.timers.at(-1).callback();
    assert.equal(ui.tooltip.hidden, false);
    assert.equal(ui.tooltip.textContent, 'Add VTuber');
    ui.focus(suggestion);
    assert.equal(ui.tooltip.hidden, true);
    assert.equal(suggestion.getAttribute('title'), null);
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
    hover(input); assert.equal(input.attributes.title, 'Duration');
    focus(input); assert.equal(input.attributes.title, undefined);
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

test('focused inputs hide open and pending labels until blurred', () => {
    for (const tag of ['input', 'textarea', 'editable']) {
        const ui = setup();
        const field = new ui.Element(tag, {title: 'Edit value'});
        // Model a contenteditable element in the minimal DOM fixture.
        if (tag === 'editable') field.attributes.contenteditable = 'true';
        ui.hover(field); ui.timers.at(-1).callback();
        ui.focus(field);
        assert.equal(ui.tooltip.hidden, true);
        assert.equal(field.getAttribute('title'), null);
        const count = ui.timers.length;
        ui.hover(field);
        ui.handlers.input({target: field, type: 'input'});
        assert.equal(ui.timers.length, count);
        assert.equal(ui.tooltip.hidden, true);
        ui.handlers.focusout({target: field, relatedTarget: null});
        ui.hover(field);
        assert.equal(ui.timers.length, count + 1);
        ui.focus(field);
        assert.equal(ui.timers.at(-1).cancelled, true);
    }
});

test('hiding input hover labels does not manipulate the native suggestion popover stack', () => {
    const ui = setup();
    ui.tooltip.showPopover = () => assert.fail('Hover labels must not open native popovers');
    ui.tooltip.hidePopover = () => assert.fail('Hover labels must not close native popovers');
    const field = new ui.Element('input', {placeholder: 'Search tags'});
    ui.hover(field); ui.timers.at(-1).callback();
    assert.equal(ui.tooltip.attributes.popover, undefined);
    ui.focus(field);
    assert.equal(ui.tooltip.hidden, true);
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

test('tooltip centers on visible text rather than the full control width', () => {
    const ui = setup({textRects: [{left: 120, right: 180, top: 105, bottom: 125}]});
    ui.tooltip.getBoundingClientRect = () => ({width: 100, height: 30});
    const button = new ui.Element('button', {}, 'Label');
    ui.hover(button); ui.timers.at(-1).callback();
    assert.equal(ui.tooltip.style.left, '100px');
});

test('video preview and its controls never receive dashboard tooltip labels', () => {
    const ui = setup();
    const button = new ui.Element('button', {'aria-label': 'Play video'});
    const closest = button.closest.bind(button);
    button.closest = selector => selector.includes('.dashboard-video-frame') ? button : closest(selector);
    ui.hover(button);
    assert.equal(ui.timers.length, 0);
    assert.equal(button.getAttribute('title'), null);
});

test('mobile labels require a long press; regular taps and focus do not show them', () => {
    const ui = setup({mobile: true});
    const button = new ui.Element('button', {title: 'Filter chat'});
    ui.hover(button); ui.focus(button);
    assert.equal(ui.timers.length, 0);
    assert.equal(button.getAttribute('title'), null);
    const touch = {target: button, pointerType: 'touch', pointerId: 1, clientX: 150, clientY: 110};
    ui.handlers.pointerdown(touch);
    assert.equal(ui.timers.at(-1).delay, 550);
    ui.handlers.pointerup(touch);
    assert.equal(ui.timers.at(-1).cancelled, true);
    assert.equal(ui.tooltip.hidden, true);
    ui.handlers.pointerdown(touch);
    ui.timers.at(-1).callback();
    assert.equal(ui.tooltip.hidden, false);
    assert.equal(ui.tooltip.textContent, 'Filter chat');
    ui.handlers.pointerup(touch);
    let prevented = false;
    ui.handlers.click({preventDefault() { prevented = true; }, stopImmediatePropagation() {}});
    assert.equal(prevented, true);
    ui.timers.at(-1).callback();
    assert.equal(ui.tooltip.hidden, true);
});

test('moving or cancelling a touch cancels its pending tooltip', () => {
    const ui = setup({mobile: true});
    const button = new ui.Element('button', {}, 'Next');
    const touch = {target: button, pointerType: 'touch', pointerId: 1, clientX: 150, clientY: 110};
    ui.handlers.pointerdown(touch);
    ui.handlers.pointermove({...touch, clientX: 170});
    assert.equal(ui.timers.at(-1).cancelled, true);
    assert.equal(ui.tooltip.hidden, true);
    ui.handlers.pointerdown(touch);
    ui.handlers.pointercancel();
    assert.equal(ui.timers.at(-1).cancelled, true);
});
