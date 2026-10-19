const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
    constructor() { this.children = []; this.handlers = {}; this.style = {}; this.dataset = {}; this.value = ''; this.classes = new Set();
        this.classList = {add: name => this.classes.add(name), remove: name => this.classes.delete(name), toggle: (name, value) => value ? this.classes.add(name) : this.classes.delete(name)}; }
    setAttribute(name, value) { this.attributes ||= {}; this.attributes[name] = value; }
    set className(value) { this.classes = new Set(value.split(/\s+/).filter(Boolean)); }
    get className() { return [...this.classes].join(' '); }
    append(...children) { this.children.push(...children); }
    appendChild(child) { this.children.push(child); }
    replaceChildren(...children) { this.children = children; }
    addEventListener(name, callback) { this.handlers[name] = callback; }
    removeEventListener(name) { delete this.handlers[name]; }
    contains(node) { return this === node || this.children.some(child => child.contains(node)); }
    focus() { this.focused = true; }
    dispatchEvent(event) { this.handlers[event.type]?.(event); }
    setRangeText(text, start, end) {
        this.value = this.value.slice(0, start) + text + this.value.slice(end);
        this.selectionStart = this.selectionEnd = start + text.length;
    }
}
function setup({fetch: fetchOverride} = {}) {
    const window = {location: {origin: 'http://localhost:4345'}};
    const connections = [], requests = [], received = [], completions = [], timers = new Map(); let nextTimer = 0;
    let destroyed = false, pickerRenders = 0, groupRenders = 0, testNow = Date.now();
    window.createTwitchPreviewFeed = () => ({receive: value => received.push(value), destroy: () => {
        assert.equal(destroyed, false, 'Feed should only be disposed once'); destroyed = true;
    }});
    window.createChatAutocomplete = options => {
        const controller = {update() {}, handleKey: () => false, hide() {}, destroy() {this.destroyed = true;}};
        completions.push({options, controller}); return controller;
    };
    const document = {handlers: {}, createElement: () => new Element(),
        addEventListener(type, handler) { this.handlers[type] = handler; },
        removeEventListener(type) { delete this.handlers[type]; }};
    const context = {
        window, document, URL, URLSearchParams, AbortController, Event: class {constructor(type) {this.type = type;}},
        Date: class extends Date { static now() { return testNow; } },
        getComputedStyle: () => ({borderTopWidth: '1px', borderBottomWidth: '1px',
            lineHeight: '22px', paddingTop: '10px', paddingBottom: '10px'}),
        setTimeout: (callback, delay) => { timers.set(++nextTimer, {callback, delay}); return nextTimer; },
        clearTimeout: id => timers.delete(id),
        EventSource: class { constructor(url) { this.url = url; connections.push(this); } close() { this.closed = true; } },
        fetch: async (url, options) => { requests.push({url, options}); return fetchOverride ? fetchOverride(url, options) : {ok: true, json: async () => ({sent: true})}; }
    };
    window.setTimeout = context.setTimeout; window.clearTimeout = context.clearTimeout;
    // Real shared composer, not a second preview implementation.
    vm.createContext(context);
    vm.runInContext(fs.readFileSync('web/static/js/chat-composer.js', 'utf8'), context);
    vm.runInContext(fs.readFileSync('web/static/js/chat-emote-picker.js', 'utf8'), context);
    const createPicker = window.createChatEmotePicker;
    window.createChatEmotePicker = options => {
        const picker = createPicker(options), render = picker.render, renderGroups = picker.renderGroups;
        picker.render = () => { pickerRenders++; render(); };
        picker.renderGroups = () => { groupRenders++; renderGroups(); };
        return picker;
    };
    vm.runInContext(fs.readFileSync('web/static/js/raid-preview-chat.js', 'utf8'), context);
    const host = new Element();
    const controller = window.createRaidPreviewChat(host, {id: '2', login: 'target'}, 'csrf');
    return {host, controller, connections, received, requests, timers, completions, document, destroyed: () => destroyed,
        pickerRenders: () => pickerRenders, groupRenders: () => groupRenders, advanceTime: ms => { testNow += ms; }};
}

test('preview builds a catalog once and reuses its picker on cached reopen', async () => {
    const app = setup({fetch: async () => ({ok: true, json: async () => ({emotes: [
        {name: 'Wave', provider: '7tv', group_key: '7tv', url: 'https://cdn.7tv.app/emote/1/2x.webp'}
    ]})})});
    const form = app.host.children[2], toggle = form.children[0].children[3], picker = form.children[2];
    await toggle.handlers.click();
    assert.equal(app.pickerRenders(), 1);
    assert.equal(app.groupRenders(), 1);
    const section = picker.children[1].children[0].children[0];
    await toggle.handlers.click(); await toggle.handlers.click();
    assert.equal(app.requests.length, 1);
    assert.equal(app.pickerRenders(), 1);
    assert.equal(app.groupRenders(), 1);
    assert.equal(picker.children[1].children[0].children[0], section);
    assert.match(picker.children[2].textContent, /Tip:/);
    app.advanceTime(31000);
    form.children[0].children[0].handlers.focus();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(app.requests.length, 2);
    assert.equal(app.pickerRenders(), 2, 'A refreshed catalog must still rebuild the picker');
    assert.equal(app.groupRenders(), 2);
    assert.notEqual(picker.children[1].children[0].children[0], section);
    app.controller.destroy();
});
test('connects only to our relay, renders events and closes on teardown', () => {
    const app = setup(), source = app.connections[0];
    assert.equal(source.url.origin, 'http://localhost:4345');
    assert.equal(source.url.searchParams.get('target_id'), '2');
    source.onmessage({data: JSON.stringify({type: 'message', message: {id: 'm'}})});
    assert.equal(app.received[0].message.id, 'm');
    const lateMessage = source.onmessage;
    app.controller.destroy(); app.controller.destroy(); assert.ok(source.closed && app.destroyed());
    lateMessage({data: '{"type":"message"}'}); assert.equal(app.received.length, 1);
    assert.equal(source.onmessage, null); assert.equal(source.onerror, null);
    assert.equal(app.host.children.length, 0);
});
test('terminal permission failures stop automatic retries', () => {
    const app = setup(), source = app.connections[0];
    const lateError = source.onerror, lateMessage = source.onmessage;
    source.onmessage({data: JSON.stringify({type: 'status', text: 'Reconnect Twitch', terminal: true, error: true})});
    assert.ok(source.closed); assert.equal(app.host.children[2].children[0].children[1].textContent, 'Reconnect Twitch');
    lateError(); lateMessage({data: '{"type":"status","text":"Connected"}'});
    assert.equal(app.host.children[2].children[0].children[1].textContent, 'Reconnect Twitch');
    assert.equal(source.onmessage, null); assert.equal(source.onerror, null);
});
test('send uses target and CSRF, limits input, and waits for real chat echo', async () => {
    const app = setup(), form = app.host.children[2], input = form.children[0].children[0];
    assert.equal(input.maxLength, 500); assert.equal(input.rows, 1);
    input.value = 'hello'; await form.handlers.submit({preventDefault() {}});
    assert.equal(app.requests[0].options.body.get('target_id'), '2');
    assert.equal(app.requests[0].options.body.get('csrf_token'), 'csrf');
    assert.equal(input.value, ''); assert.equal(app.received.length, 0);
});

test('preview reuses main composer styles with Send beside the entry and status inside it', () => {
    const app = setup(), form = app.host.children[2], entry = form.children[0];
    assert.ok(form.className.includes('dashboard-chat-composer'));
    assert.ok(entry.className.includes('chat-message-entry'));
    assert.equal(entry.children[1].className, 'chat-send-status');
    assert.ok(form.children[1].className.includes('chat-send-button'));
    assert.match(form.children[1].innerHTML, /<path d="M4 3 21 12 4 21 8 12Z"/);
    assert.equal(form.children[1].title, 'Send');
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.ok(!styles.includes('.raid-preview-chat-compose button {'));
    assert.ok(!styles.includes('.raid-preview-chat-status {'));
    assert.match(styles, /\.raid-preview-chat \.raid-preview-chat-entry textarea \{ display: block; height: calc\(1\.4em \+ 22px\); \}/);
    assert.ok(!styles.includes('height: calc(1.4em + 32px)'));
    assert.match(styles, /\.raid-preview-chat \.raid-preview-chat-compose \{[^}]*align-items: stretch;/);
    assert.match(styles, /\.raid-preview-chat \.dashboard-chat-composer textarea \{[^}]*padding-right: 50px;/);
    assert.ok(!styles.includes('.raid-preview-chat-entry:not(:focus-within):has(.chat-send-status'),
        'Connection status must not reserve extra input width or wrap the placeholder');
    assert.match(styles, /\.raid-preview-chat \.raid-preview-chat-send \{[^}]*align-self: center;[^}]*width: 40px; height: 40px; min-height: 40px; aspect-ratio: 1;/);
    assert.match(styles, /\.raid-preview-chat \.chat-emote-section-grid \{ grid-template-columns: repeat\(auto-fill,minmax\(44px,1fr\)\); gap: 2px;/);
    assert.match(styles, /\.raid-preview-chat \.chat-emote-option \{ height: 50px; padding: 3px; gap: 2px;/);
    assert.match(styles, /\.raid-preview-chat \.raid-preview-chat-compose \{ position: relative;/);
    assert.match(styles, /\.raid-preview-chat \.chat-emote-picker \{ box-sizing: border-box; left: 0; right: 0; bottom: 100%; width: auto;/);
    assert.match(styles, /\.raid-browser-close \{ display: grid; place-items: center; box-sizing: border-box;/);
    assert.match(styles, /\.raid-browser-close svg, \.raid-preview-header \[data-raid-preview-back\] svg \{ display: block; width: 18px; height: 18px;/);
});

test('status matches main chat fade delay; disconnects stay readable and close clears the timer', () => {
    const app = setup(), status = app.host.children[2].children[0].children[1];
    app.connections[0].onmessage({data: JSON.stringify({type: 'status', text: 'Connected'})});
    assert.equal(app.timers.size, 1);
    const timer = [...app.timers.values()][0]; assert.equal(timer.delay, 3000);
    timer.callback(); assert.ok(status.classes.has('is-fading'));
    app.connections[0].onerror();
    assert.ok(!status.classes.has('is-fading')); assert.ok(status.classes.has('error'));
    assert.equal(app.timers.size, 0);
    app.connections[0].onmessage({data: JSON.stringify({type: 'status', text: 'Connected'})});
    app.controller.destroy(); assert.equal(app.timers.size, 0);
});

test('preview autocomplete uses its target catalog and observed chatters, handles completion before sending, and cleans up', async () => {
    const app = setup(), form = app.host.children[2], input = form.children[0].children[0];
    input.handlers.focus(); await new Promise(resolve => setImmediate(resolve));
    assert.equal(app.requests[0].url.searchParams.get('target_id'), '2');
    assert.equal(app.requests[0].url.pathname, '/channel/api/raid-browser/chat/emotes');
    app.connections[0].onmessage({data: JSON.stringify({type: 'message', message: {username: 'chatter', display_name: 'Chatter'}})});
    assert.ok(app.completions[0].options.getUsers().some(user => user.username === 'chatter'));
    app.completions[0].controller.handleKey = () => true;
    form.requestSubmit = () => { throw new Error('Completing a name must not send a message'); };
    input.handlers.keydown({key: 'Enter'});
    app.controller.destroy(); assert.equal(app.completions[0].controller.destroyed, true);
    assert.equal(app.requests[0].options.signal.aborted, false, 'Completed catalog requests are released');
    assert.equal(input.handlers.focus, undefined);
});

test('closing during an emote request aborts it and ignores its late result', async () => {
    let resolve;
    const app = setup({fetch: () => new Promise(done => { resolve = done; })});
    const input = app.host.children[2].children[0].children[0];
    let updates = 0;
    app.completions[0].controller.update = () => { updates++; };
    input.handlers.focus(); input.handlers.focus();
    assert.equal(app.requests.length, 1);
    app.controller.destroy();
    assert.equal(app.requests[0].options.signal.aborted, true);
    resolve({ok: true, json: async () => ({emotes: [{name: 'late'}]})});
    await new Promise(done => setImmediate(done));
    assert.equal(updates, 0);
});

test('preview emote button loads target emotes, searches and inserts at the caret without sending', async () => {
    const app = setup({fetch: async () => ({ok: true, json: async () => ({emotes: [
        {name: 'Wave', provider: '7tv', group_key: '7tv', url: 'https://cdn.7tv.app/emote/1/2x.webp'},
        {name: 'Hello', provider: 'twitch', group_key: 'twitch:global', url: 'https://static-cdn.jtvnw.net/emoticons/v2/1/default/dark/2.0'},
        {name: 'Unsafe', url: 'https://example.com/untrusted.png'}
    ]})})});
    const form = app.host.children[2], entry = form.children[0], input = entry.children[0];
    const toggle = entry.children[3], picker = form.children[2];
    const search = picker.children[0].children[0], body = picker.children[1], grid = body.children[0];
    input.value = 'hi there'; input.selectionStart = input.selectionEnd = 2;
    await toggle.handlers.click();
    assert.equal(toggle.type, 'button'); assert.equal(picker.hidden, false);
    assert.equal(app.requests[0].url.searchParams.get('target_id'), '2');
    assert.equal(grid.children.length, 2); assert.equal(search.focused, true);
    search.value = 'wave'; search.handlers.input();
    assert.equal(grid.children.length, 1);
    const sevenTv = body.children[1].children[1];
    sevenTv.handlers.click(); assert.equal(grid.children.length, 1);
    assert.equal(sevenTv.attributes['aria-pressed'], 'true');
    grid.children[0].children[1].children[0].handlers.click();
    assert.equal(input.value, 'hi Wave there');
    assert.equal(input.focused, true); assert.equal(picker.hidden, true);
    assert.equal(app.requests.length, 1, 'Inserting an emote does not send a chat message');
    app.controller.destroy();
    assert.equal(app.document.handlers.pointerdown, undefined);
});

test('preview emote picker closes outside and on Escape, limits length and ignores late opening', async () => {
    let resolve;
    const app = setup({fetch: () => new Promise(done => {resolve = done;})});
    const form = app.host.children[2], entry = form.children[0], input = entry.children[0];
    const toggle = entry.children[3], picker = form.children[2], search = picker.children[0].children[0];
    const opening = toggle.handlers.click();
    app.document.handlers.pointerdown({target: picker}); assert.equal(picker.hidden, false);
    app.document.handlers.pointerdown({target: input}); assert.equal(picker.hidden, true);
    resolve({ok: true, json: async () => ({emotes: [{name: 'Wave', url: 'https://cdn.7tv.app/emote/1/2x.webp'}]})});
    await opening; assert.equal(search.focused, undefined);
    await toggle.handlers.click();
    input.value = 'x'.repeat(500); input.selectionStart = input.selectionEnd = 500;
    picker.children[1].children[0].children[0].children[1].children[0].handlers.click();
    assert.equal(input.value.length, 500); assert.equal(picker.hidden, false);
    let prevented = false;
    app.host.handlers.keydown({key: 'Escape', preventDefault() {prevented = true;}, stopPropagation() {}});
    assert.ok(prevented); assert.equal(picker.hidden, true); assert.equal(toggle.focused, true);
    app.controller.destroy();
});
