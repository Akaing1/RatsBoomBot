const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('web/static/js/dashboard-chat-send.js', 'utf8');
const core = fs.readFileSync('web/static/js/chat-composer.js', 'utf8');
const resize = core.match(/        function resize\(\) \{[\s\S]*?\n        \}/)[0];

test('a late emote catalog cannot steal focus after the dashboard picker closes', async () => {
    const toggle = source.match(/    async function toggleEmotes\(\) \{[\s\S]*?\n    \}/)[0];
    let resolve, focuses = 0;
    const pending = new Promise(done => { resolve = done; });
    const context = {emotePicker: {hidden: true}, emoteToggle: {setAttribute() {}},
        emoteSearch: {focus() { focuses++; }}, loadEmotes: () => pending};
    vm.createContext(context); vm.runInContext(toggle, context);
    const opening = context.toggleEmotes();
    assert.equal(context.emotePicker.hidden, false);
    await context.toggleEmotes();
    assert.equal(context.emotePicker.hidden, true);
    resolve(); await opening;
    assert.equal(focuses, 0);
    await context.toggleEmotes();
    assert.equal(focuses, 1, 'A picker that remains open should still receive focus');
});

test('reply labels show distinct display names and otherwise only the username', () => {
    const begin = source.match(/    function beginReply\([\s\S]*?\n    \}/)[0];
    const context = {replyMessageId: {}, replyName: {}, replyPreview: {}, replyContext: {},
        defaultMessagePlaceholder: 'Send a message... (supports autocomplete)',
        selectedTarget: 'twitch', messageInput: {value: 'draft', focus() {}}};
    vm.createContext(context);
    vm.runInContext(begin, context);
    for (const [displayName, expected] of [['チなみ', 'チなみ (minamichimaa)'],
        ['Minamichimaa', 'minamichimaa'], ['', 'minamichimaa']]) {
        context.beginReply({messageId: 'twitch:123', username: 'minamichimaa', displayName});
        assert.equal(context.replyName.textContent, `Replying to ${expected}`);
        assert.equal(context.messageInput.placeholder, `Replying to ${expected}...`);
        assert.equal(context.messageInput.value, 'draft');
    }
    const clear = source.match(/    function clearReply\(\) \{[\s\S]*?\n    \}/)[0];
    vm.runInContext(clear, context);
    context.clearReply();
    assert.equal(context.messageInput.placeholder, context.defaultMessagePlaceholder);
    assert.equal(context.messageInput.value, 'draft');
});

test('composer grows with wrapped text and returns to its baseline after clearing', () => {
    const messageInput = {style: {}, value: '', scrollHeight: 140};
    const context = {closed: false, input: messageInput, getComputedStyle: () => ({borderTopWidth: '1px', borderBottomWidth: '1px',
        lineHeight: '22px', paddingTop: '10px', paddingBottom: '10px'})};
    vm.createContext(context);
    vm.runInContext(resize, context);
    context.resize();
    assert.equal(messageInput.style.height, '44px');
    messageInput.value = 'wrapped text';
    messageInput.scrollHeight = 140;
    context.resize();
    assert.equal(messageInput.style.height, '142px');
    messageInput.value = '';
    context.resize();
    assert.equal(messageInput.style.height, '44px');
});

test('autocomplete cannot insert text beyond the input limit', () => {
    const insert = source.match(/    function insertValue\(value, range = null\) \{[\s\S]*?\n    \}/)[0];
    let warning;
    const messageInput = {value: 'x'.repeat(499), maxLength: 500, selectionStart: 499, selectionEnd: 499,
        setRangeText() { throw new Error('Should not insert an oversized completion'); }};
    const context = {messageInput, showStatus: message => { warning = message; }};
    vm.createContext(context);
    vm.runInContext(insert, context);
    context.insertValue('Kappa');
    assert.match(warning, /500/);
    assert.equal(messageInput.value.length, 499);
});

test('a successful empty emote catalog is cached, including concurrent callers', async () => {
    const load = source.match(/    async function loadEmotes\(force = false\) \{[\s\S]*?\n    \}/)[0];
    let requests = 0, now = 1000;
    const context = {emotes: [], catalogLoadedAt: 0, catalogPromise: null, personalGroup: '',
        trustedEmoteUrl: /^https:\/\/static-cdn\.jtvnw\.net\//,
        Date: {now: () => now}, renderGroupOptions() {}, renderPicker() {}, updateSuggestions() {},
        emoteNote: {replaceChildren() {}, classList: {toggle() {}}},
        fetch: async () => { requests++; return {ok: true, json: async () => ({emotes: []})}; }};
    vm.createContext(context); vm.runInContext(load, context);
    await Promise.all([context.loadEmotes(), context.loadEmotes()]); assert.equal(requests, 1);
    await context.loadEmotes(); assert.equal(requests, 1);
    await context.loadEmotes(true); assert.equal(requests, 2);
    now += 30001; await context.loadEmotes(); assert.equal(requests, 3);
});

test('picker groups matches once while preserving alphabetical items and group order', () => {
    const pickerSource = fs.readFileSync('web/static/js/chat-emote-picker.js', 'utf8');
    const render = pickerSource.match(/    function renderPicker\(\) \{[\s\S]*?\n    \}/)[0];
    class Element {
        constructor() { this.children = []; this.handlers = {}; }
        append(...children) { this.children.push(...children); }
        appendChild(child) { this.children.push(child); }
        replaceChildren() { this.children = []; }
        addEventListener(name, callback) { this.handlers[name] = callback; }
        setAttribute() {}
    }
    const emotes = [{name: 'Zebra', provider: '7tv', group_key: '7tv'},
        {name: 'Kappa', provider: 'twitch', group_key: 'personal'},
        {name: 'Alpha', provider: '7tv', group_key: '7tv'}];
    let inserted;
    const context = {closed: false, emotes, sortedSource: null, sortedEmotes: [], getEmotes: () => emotes, getPersonalGroup: () => 'personal',
        emoteSearch: {value: ''}, selectedGroup: null, personalGroup: 'personal',
        groupKey: emote => emote.group_key, orderedGroups: () => [{key: 'personal', label: 'Mine'}, {key: '7tv', label: '7TV'}],
        emoteGrid: new Element(), emoteCount: {}, emoteSrcset: () => '',
        insertValue: value => { inserted = value; }, document: {createElement: () => new Element()}};
    vm.createContext(context); vm.runInContext(render, context); context.renderPicker();
    const sections = context.emoteGrid.children;
    assert.deepEqual(sections.map(section => section.children[0].textContent), ['Your channel · Mine', '7TV']);
    assert.deepEqual(sections[1].children[1].children.map(button => button.children[1].textContent), ['Alpha', 'Zebra']);
    assert.equal(context.emoteCount.textContent, '3');
    sections[1].children[1].children[0].handlers.click(); assert.equal(inserted, 'Alpha');
    context.selectedGroup = 'personal'; context.renderPicker(); assert.equal(context.emoteGrid.children.length, 1);
    context.selectedGroup = null; context.emoteSearch.value = 'ze'; context.renderPicker();
    assert.equal(context.emoteGrid.children.length, 1); assert.equal(context.emoteCount.textContent, '1');
});


function localCommands(unavailable = false) {
    const clicked = [], warnings = [];
    const context = {document: {querySelector: selector => unavailable ? null : {disabled: false, click() { clicked.push(selector); }}},
        emotePicker: {hidden: false}, emoteToggle: {setAttribute() {}}, showStatus: message => warnings.push(message)};
    const declarations = source.slice(source.indexOf('    const overlayCommands = ['), source.indexOf('    function showStatus('));
    vm.createContext(context);
    vm.runInContext(declarations + '\nthis.commands = twitchCommands;', context);
    const handler = source.slice(source.indexOf('        handleLocal(message) {'), source.indexOf('        async send(outgoingMessage, signal) {')).trim().replace(/,$/, '');
    const handle = vm.runInContext(`({${handler}}).handleLocal`, context);
    return {handle, clicked, warnings, commands: context.commands, context};
}

test('dashboard slash commands open the matching overlays and appear in autocomplete', () => {
    const app = localCommands();
    for (const command of ['/poll', '/prediction', '/raidbrowser']) {
        assert.equal(app.handle(command), true);
        assert.ok(app.commands.some(item => item.value === command));
    }
    assert.deepEqual(app.clicked, ['[data-engagement-open="polls"]', '[data-engagement-open="predictions"]', '[data-raid-browser-open]']);
    assert.equal(app.context.emotePicker.hidden, true);
    for (const message of ['/prediction/', '/poll extra', '/raid someone', 'hello']) assert.equal(app.handle(message), false);
    assert.equal(app.handle('/POLL'), true);
});

test('unavailable overlay commands stay local and are omitted from autocomplete', () => {
    const app = localCommands(true);
    assert.equal(app.handle('/poll'), true);
    assert.equal(app.clicked.length, 0);
    assert.match(app.warnings[0], /unavailable/);
    assert.equal(app.commands.some(item => item.value === '/poll'), false);
});
