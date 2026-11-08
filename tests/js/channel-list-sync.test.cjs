const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup() {
    const storage = new Map([['ratsboombot:raid-favorites:1', '["10"]'], ['ratsboombot:raid-blacklist:1', '["20"]']]);
    const calls = [], events = [], alerts = [], messages = [];
    const state = {version: 1, channelId: '1', lists: {automaticShoutouts: ['alice'], incomingRaidBlacklist: ['blocked'], queueBlacklist: ['queued']}};
    const context = {console: Object.fromEntries(['info', 'warn', 'error'].map(level => [level, (...args) => messages.push({level, text: args.join(' ')})])),
        window: {dispatchEvent: event => events.push(event), alert: message => alerts.push(message)}, document: {querySelector: () => ({value: 'secret'})},
        localStorage: {getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value)},
        StorageEvent: class { constructor(type, properties) { Object.assign(this, {type}, properties); } },
        fetch: async (url, options) => {
            calls.push({url, ...options});
            if (options.method === 'POST') {
                const body = JSON.parse(options.body);
                for (const [name, users] of Object.entries(body.lists)) state.lists[name] = [...new Set([...(body.replace ? [] : state.lists[name]), ...users])].sort();
            }
            return {ok: true, json: async () => JSON.parse(JSON.stringify(state))};
        }};
    vm.runInNewContext(fs.readFileSync('web/static/js/channel-list-sync.js', 'utf8'), context);
    return {helper: context.window.ratsLists, window: context.window, context, storage, calls, events, alerts, messages, state};
}

test('simple export and import commands copy, paste and cancel without extra console steps', async () => {
    const ui = setup();
    let copied;
    ui.context.navigator = {clipboard: {writeText: async data => { copied = data; }}};
    await ui.window.exportLists();
    assert.equal(JSON.parse(copied).channelId, '1');
    assert.match(ui.messages.at(-1).text, /Export successful.*clipboard/);
    ui.window.prompt = () => copied;
    assert.equal((await ui.window.importLists()).mode, 'merge');
    assert.match(ui.alerts[0], /Lists imported successfully \(merge\)/);
    assert.match(ui.alerts[0], /Incoming raid blacklist: 1/);
    assert.match(ui.messages.at(-1).text, /Import successful/);
    assert.ok(ui.messages.some(message => /server settings saved/.test(message.text)));
    assert.equal((await ui.window.importLists({replace: true})).mode, 'replace');
    const count = ui.calls.length;
    ui.window.prompt = () => null;
    assert.equal(await ui.window.importLists(), 'Import cancelled.');
    assert.equal(ui.calls.length, count);
    assert.equal(ui.alerts.length, 2);
    assert.match(ui.messages.at(-1).text, /Import cancelled/);
    ui.context.navigator.clipboard.writeText = async () => { throw new Error('Clipboard unavailable'); };
    let fallback;
    ui.window.prompt = (message, text) => { fallback = text; };
    await ui.window.exportLists();
    assert.equal(JSON.parse(fallback).version, 1);
});

test('console export includes local and saved lists without credentials', async () => {
    const ui = setup(), exported = JSON.parse(await ui.helper.export());
    assert.deepEqual(exported, {...ui.state, lists: {...ui.state.lists, raidFavorites: ['10'], raidBlacklist: ['20']}});
    assert.equal(JSON.stringify(exported).includes('secret'), false);
});

test('file commands transfer complete JSON and allow cancelling the file picker', async () => {
    const ui = setup();
    let blob, name, fileData, cancelled = false;
    ui.context.Blob = Blob;
    ui.context.URL = {createObjectURL: value => { blob = value; return 'blob:export'; }, revokeObjectURL() {}};
    ui.context.setTimeout = callback => callback();
    ui.context.document.body = {append() {}};
    ui.context.document.createElement = type => {
        const events = {};
        return {files: [{text: async () => fileData}], addEventListener: (name, callback) => { events[name] = callback; },
            remove() {}, click() { if (type === 'a') name = this.download; else events[cancelled ? 'cancel' : 'change'](); }};
    };
    await ui.window.exportLists({file: true});
    fileData = await blob.text();
    assert.match(name, /^ratsboombot-lists-1-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{3}Z\.json$/);
    assert.deepEqual(JSON.parse(fileData).lists.raidFavorites, ['10']);
    assert.equal((await ui.window.importLists({file: true})).mode, 'merge');
    assert.equal((await ui.window.importLists({file: true, replace: true})).mode, 'replace');
    cancelled = true;
    const count = ui.calls.length;
    assert.equal(await ui.window.importLists({file: true}), 'Import cancelled.');
    assert.equal(ui.calls.length, count);
});

test('truncated pasted JSON gives a recovery message and changes nothing', async () => {
    const ui = setup();
    await assert.rejects(ui.helper.import('{"version":1,"lists":{"automaticShoutouts":["user", "... "123"]}}'), /incomplete or invalid JSON.*No lists were changed/);
    assert.equal(ui.calls.length, 0);
    assert.equal(ui.events.length, 0);
    assert.equal(ui.storage.get('ratsboombot:raid-favorites:1'), '["10"]');
    ui.window.prompt = () => 'invalid JSON';
    await assert.rejects(ui.window.importLists());
    assert.equal(ui.alerts.length, 0);
    assert.match(ui.messages.at(-1).text, /Import failed/);
    assert.equal(ui.messages.some(message => /Import successful/.test(message.text)), false);
});

test('console import merges by default, replaces only supplied lists and notifies storage listeners', async () => {
    const ui = setup();
    const source = {version: 1, channelId: '1', lists: {automaticShoutouts: ['Bob'], raidFavorites: ['30']}};
    await ui.helper.import(JSON.stringify(source));
    assert.deepEqual(ui.state.lists.automaticShoutouts, ['alice', 'bob']);
    assert.equal(ui.storage.get('ratsboombot:raid-favorites:1'), '["10","30"]');
    assert.equal(ui.events[0].key, 'ratsboombot:raid-favorites:1');
    assert.equal(ui.calls.find(call => call.method === 'POST').headers['X-CSRF-Token'], 'secret');
    await ui.helper.import(source, {replace: true});
    assert.deepEqual(ui.state.lists.automaticShoutouts, ['bob']);
    assert.equal(ui.storage.get('ratsboombot:raid-favorites:1'), '["30"]');
    assert.equal(ui.storage.get('ratsboombot:raid-blacklist:1'), '["20"]');
    assert.deepEqual(ui.state.lists.incomingRaidBlacklist, ['blocked']);
});

test('invalid lists, mismatched channels and oversized merges do not write anything', async () => {
    const ui = setup();
    for (const source of [
        {version: 1, channelId: 'other', lists: {raidFavorites: ['1']}},
        {version: 1, channelId: '1', lists: {queueBlacklist: ['bad name']}},
        {version: 1, channelId: '1', lists: {unknown: []}},
        {version: 1, channelId: '1', lists: {raidFavorites: Array.from({length: 100}, (_, i) => String(i + 100))}},
    ]) await assert.rejects(ui.helper.import(source));
    assert.equal(ui.calls.some(call => call.method === 'POST'), false);
    assert.equal(ui.events.length, 0);
    assert.equal(ui.storage.get('ratsboombot:raid-favorites:1'), '["10"]');
});
