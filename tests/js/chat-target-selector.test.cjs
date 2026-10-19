const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup(youtubeAvailable = true, withInput = false) {
    const element = () => ({handlers: {}, dataset: {}, attributes: {}, style: {setProperty(name, value) {this[name] = value;}},
        addEventListener(type, handler) { this.handlers[type] = handler; },
        removeEventListener(type) { delete this.handlers[type]; },
        setAttribute(name, value) { this.attributes[name] = value; }});
    const form = element(), button = element(), window = element(), changes = [], sent = [];
    const input = withInput ? element() : undefined;
    button.getBoundingClientRect = () => ({width: button.textContent.length * 8});
    let resize, disconnected = false, layouts = 0;
    if (withInput) window.ResizeObserver = class {
        constructor(callback) {resize = callback;}
        observe() {}
        disconnect() {disconnected = true;}
    };
    form.contains = node => node === button;
    vm.runInNewContext(fs.readFileSync('web/static/js/chat-target-selector.js', 'utf8'), {window});
    const selector = window.createChatTargetSelector({form, button, input, youtubeAvailable,
        onChange: target => changes.push(target), onLayout: () => { layouts++; }});
    form.requestSubmit = () => sent.push(selector.target());
    return {form, button, input, window, changes, sent, selector, resize: () => resize(), disconnected: () => disconnected, layouts: () => layouts};
}
const key = (name, extra = {}) => ({key: name, preventDefault() {this.prevented = true;}, ...extra});

test('destination button cycles Twitch, YouTube and All', () => {
    const app = setup(); assert.equal(app.button.textContent, '[Twitch]');
    assert.equal(app.button.title, 'Twitch');
    app.button.handlers.click(); assert.equal(app.button.textContent, '[YouTube]');
    assert.equal(app.button.title, 'YouTube');
    app.button.handlers.click(); assert.equal(app.button.textContent, '[All]');
    assert.equal(app.button.title, 'All');
    app.button.handlers.click(); assert.equal(app.selector.target(), 'twitch');
});

test('Tab cycles unless completing a suggestion, while Shift+Tab and browser shortcuts remain available', () => {
    const app = setup(), tab = key('Tab');
    assert.equal(app.selector.handleKey(tab), true); assert.ok(tab.prevented);
    assert.equal(app.selector.target(), 'youtube');
    assert.equal(app.selector.handleKey(key('Tab'), () => true), true);
    assert.equal(app.selector.target(), 'youtube', 'An emote completion must not change destinations');
    assert.equal(app.selector.handleKey(key('Tab', {shiftKey: true})), false);
    assert.equal(app.selector.handleKey(key('Tab', {ctrlKey: true})), false);
    assert.equal(app.selector.handleKey(key('Tab', {isComposing: true})), false);
    app.button.handlers.keydown(key('Tab')); assert.equal(app.selector.target(), 'both');
});

test('holding Shift temporarily displays All and restores the chosen destination on release or blur', () => {
    const app = setup(); app.selector.select('youtube');
    app.form.handlers.keydown(key('Shift')); assert.equal(app.button.textContent, '[All]');
    app.window.handlers.keyup(key('Shift')); assert.equal(app.button.textContent, '[YouTube]');
    app.form.handlers.pointerdown({shiftKey: true}); assert.equal(app.selector.target(), 'both');
    app.form.handlers.focusout({relatedTarget: app.button}); assert.equal(app.selector.target(), 'both');
    app.form.handlers.focusout({relatedTarget: null}); assert.equal(app.selector.target(), 'youtube');
    app.form.handlers.keydown(key('Shift')); app.window.handlers.blur();
    assert.equal(app.selector.target(), 'youtube');
});

test('Shift+Enter submits to All immediately without changing the persistent destination', () => {
    const app = setup(), enter = key('Enter', {shiftKey: true});
    app.selector.select('youtube');
    assert.equal(app.selector.handleKey(enter), true); assert.ok(enter.prevented);
    assert.deepEqual(app.sent, ['both']);
    app.window.handlers.keyup(key('Shift')); assert.equal(app.selector.target(), 'youtube');
    assert.equal(app.selector.handleKey(key('Enter')), false, 'Ordinary Enter stays with the shared composer');
    assert.equal(app.selector.handleKey(key('Enter', {shiftKey: true, isComposing: true})), false);
});

test('single-platform chat consumes Tab without changing destinations or redrawing', () => {
    const app = setup(false); assert.equal(app.button.disabled, true);
    const tab = key('Tab');
    assert.equal(app.selector.handleKey(tab), true);
    assert.equal(tab.prevented, true);
    assert.equal(app.selector.handleKey(key('Tab'), () => true), true);
    for (const extra of [{shiftKey: true}, {ctrlKey: true}, {altKey: true}, {metaKey: true}, {isComposing: true}]) {
        const shortcut = key('Tab', extra);
        assert.equal(app.selector.handleKey(shortcut), false);
        assert.equal(shortcut.prevented, undefined);
    }
    app.selector.select('youtube'); app.form.handlers.keydown(key('Shift'));
    assert.equal(app.selector.target(), 'twitch'); assert.equal(app.button.textContent, '[Twitch]');
    app.selector.handleKey(key('Enter', {shiftKey: true})); assert.deepEqual(app.sent, ['twitch']);
    assert.equal(app.changes.length, 1, 'Unavailable Shift override should not redraw the selector');
});

test('unchanged prefix dimensions do not trigger extra textarea layouts', () => {
    const app = setup(true, true);
    assert.equal(app.layouts(), 1);
    app.resize(); app.resize();
    assert.equal(app.layouts(), 1);
    app.button.getBoundingClientRect = () => ({width: 100}); app.resize();
    assert.equal(app.layouts(), 2);
});

test('teardown removes modifier listeners and ignores late keyboard events', () => {
    const app = setup(), lateShift = app.form.handlers.keydown;
    app.selector.destroy(); app.selector.destroy(); lateShift(key('Shift'));
    assert.equal(app.selector.target(), 'twitch');
    assert.deepEqual(app.window.handlers, {}); assert.deepEqual(app.form.handlers, {}); assert.deepEqual(app.button.handlers, {});
});

test('first-line indentation follows the prefix width and scrolled text cannot overlap it', () => {
    const app = setup(true, true);
    assert.equal(app.input.style['--chat-target-indent'], '66px');
    app.selector.select('youtube'); assert.equal(app.input.style['--chat-target-indent'], '74px');
    app.form.handlers.keydown(key('Shift')); assert.equal(app.input.style['--chat-target-indent'], '42px');
    app.window.handlers.keyup(key('Shift')); assert.equal(app.input.style['--chat-target-indent'], '74px');
    app.button.getBoundingClientRect = () => ({width: 85}); app.resize();
    assert.equal(app.input.style['--chat-target-indent'], '87px');
    app.input.scrollTop = 10; app.input.handlers.scroll(); assert.equal(app.button.style.visibility, 'hidden');
    app.input.scrollTop = 0; app.input.handlers.scroll(); assert.equal(app.button.style.visibility, '');
    app.selector.destroy(); app.button.getBoundingClientRect = () => ({width: 100}); app.resize();
    assert.equal(app.input.style['--chat-target-indent'], '87px');
    assert.equal(app.input.handlers.scroll, undefined); assert.ok(app.disconnected());
});

test('dashboard composer has one row with destination first and square Send last, with no bottom buttons', () => {
    const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
    const row = template.split('<div class="dashboard-chat-compose-row">')[1].split('<div class="chat-emote-picker"')[0];
    assert.ok(row.indexOf('data-chat-target-cycle') < row.indexOf('name="message"'));
    assert.match(row, /<div class="chat-message-entry">\s*<button[^>]*data-chat-target-cycle/);
    assert.ok(row.indexOf('data-emote-toggle') < row.indexOf('chat-send-button'));
    assert.ok(!template.includes('dashboard-chat-composer-actions')); assert.ok(!template.includes('data-chat-target="'));
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.match(styles, /\.dashboard-chat-compose-row \{ display: flex; align-items: stretch/);
    assert.match(styles, /\.channel-dashboard-layout \.live-chat-panel:has\(\[data-chat-composer\]\) \{ padding-bottom: 8px;/);
    assert.match(styles, /\.dashboard-chat-compose-row \.chat-send-button \{[^}]*align-self: center;[^}]*width: 40px; height: 40px;/);
    assert.match(template, /aria-describedby="dashboard-chat-send-hint" aria-keyshortcuts="Shift\+Enter"/);
    assert.match(template, /id="dashboard-chat-send-hint"[^>]*><kbd>Shift<\/kbd> \+ <kbd>Enter<\/kbd> sends to all connected platforms/);
    assert.match(styles, /\.dashboard-chat-compose-row \.chat-message-entry \{ display: flex;[^}]*border: 1px solid var\(--border\);/);
    assert.match(styles, /\.chat-target-cycle \{[^}]*border: 0;[^}]*background: transparent; color: var\(--text\); font: inherit; font-weight: 700; line-height: 1.4;/);
    assert.match(styles, /\.dashboard-chat-compose-row textarea \{[^}]*padding-left: 12px; text-indent: var\(--chat-target-indent, 9ch\); border: 0;/);
    assert.match(styles, /\.chat-target-cycle \{ position: absolute;/);
    assert.match(styles, /\.chat-target-cycle\[data-target="twitch"\] \{ color: #c4b5fd;/);
    assert.match(styles, /\.chat-target-cycle\[data-target="youtube"\] \{ color: #ff8986;/);
    assert.match(styles, /\.chat-target-cycle\[data-target="both"\] \{ color: #7dd3fc;/);
});

test('shared composer sends Shift+Enter to All even if Shift is released while delivery is pending', async () => {
    const app = setup(), sent = [];
    app.window.createChatAutocomplete = () => ({handleKey: () => false, hide() {}, update() {}, destroy() {}});
    app.window.setTimeout = () => 1; app.window.clearTimeout = () => {};
    const input = {value: 'hello', maxLength: 500, style: {}, handlers: {},
        addEventListener(type, handler) { this.handlers[type] = handler; },
        removeEventListener(type) { delete this.handlers[type]; }};
    const status = {dataset: {}, classList: {add() {}}};
    vm.runInNewContext(fs.readFileSync('web/static/js/chat-composer.js', 'utf8'), {
        window: app.window, AbortController,
        getComputedStyle: () => ({lineHeight: '20', paddingTop: '10', paddingBottom: '10', borderTopWidth: '1', borderBottomWidth: '1'})
    });
    let pending;
    const composer = app.window.createChatComposer({form: app.form, input, sendButton: {}, status,
        autocomplete: {}, onKey: event => app.selector.handleKey(event),
        async send(message) { sent.push({message, target: app.selector.target()}); }});
    app.form.requestSubmit = () => { pending = app.form.handlers.submit({preventDefault() {}}); };
    app.selector.select('youtube');
    input.handlers.keydown(key('Enter', {shiftKey: true}));
    app.window.handlers.keyup(key('Shift')); await pending;
    assert.deepEqual(sent, [{message: 'hello', target: 'both'}]);
    assert.equal(app.selector.target(), 'youtube'); assert.equal(input.value, '');
    composer.destroy(); app.selector.destroy();
});
