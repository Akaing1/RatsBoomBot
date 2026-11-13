const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web/static/js/for-you-clips.js', 'utf8');
function setup(pages) {
    const nodes = new Map();
    function node(key) {
        if (!nodes.has(key)) nodes.set(key, {value: key === '#clip-days' ? '0' : key === '#clip-sort' ? 'newest' : '',
            dataset: {}, handlers: {}, children: [], hidden: false,
            addEventListener(event, fn) {this.handlers[event] = fn;},
            replaceChildren() {this.children = [];}, append(...children) {this.children.push(...children);}, close() {}, removeAttribute() {}});
        return nodes.get(key);
    }
    const panel = {querySelector: node};
    const tab = node('tab'); tab.dataset.workspaceTab = 'clips';
    const requests = [];
    vm.runInNewContext(source, {document: {
        querySelector: () => panel, querySelectorAll: () => [tab], createElement: () => node(Symbol()),
        body: {dataset: {channelRoot: '/moderator/channel'}}},
        URL, URLSearchParams, AbortController, location: {hostname: 'example.com'},
        fetch: async url => {requests.push(url); const page = pages.shift(); assert.ok(page, 'unexpected extra request');
            return {status: 200, ok: true, headers: {get: () => 'application/json'}, json: async () => page};}});
    return {node, requests};
}
const clip = id => ({id, title: id, creator_name: 'viewer', created_at: '2026-01-01T00:00:00Z', view_count: 1});
async function open(app) { await app.node('tab').handlers.click(); }
async function ready(app) {
    // Tab events start an async load without returning its promise.
    for (let i = 0; i < 30; ++i) await new Promise(resolve => setImmediate(resolve));
}
test('collects all intervals and deduplicates before rendering pages of 50', async () => {
    const app = setup([{clips: Array.from({length: 75}, (_, i) => clip('a'+i)), cursor: 'older'},
        {clips: [], cursor: 'older2'}, {clips: [clip('a0'),clip('last')], cursor: ''}]);
    await open(app); await ready(app);
    assert.equal(app.requests.length, 3);
    assert.equal(app.node('[data-clips-grid]').children.length, 50);
    assert.equal(app.node('[data-clips-page]').textContent, 'Page 1 of 2');
    app.node('[data-clips-next]').handlers.click();
    assert.equal(app.node('[data-clips-grid]').children.length, 26);
    assert.equal(app.node('[data-clips-next]').disabled, true);
    app.node('[data-clips-prev]').handlers.click();
    assert.equal(app.node('[data-clips-grid]').children.length, 50);
});
test('search includes clips beyond the first upstream page and resets pagination', async () => {
    const app = setup([{clips: Array.from({length: 50}, (_, i) => clip('a'+i)), cursor: 'next'},
        {clips: [clip('hidden match')], cursor: ''}]);
    await open(app); await ready(app);
    app.node('[data-clips-next]').handlers.click();
    app.node('#clip-search').value = 'hidden'; app.node('#clip-search').handlers.input();
    assert.equal(app.node('[data-clips-grid]').children.length, 1);
    assert.equal(app.node('[data-clips-page]').textContent, 'Page 1 of 1');
    app.node('#clip-search').value = 'missing'; app.node('#clip-search').handlers.input();
    assert.equal(app.node('[data-clips-grid]').children.length, 0);
    assert.equal(app.node('[data-clips-status]').textContent, 'No clips match your filters.');
    app.node('#clip-search').value = ''; app.node('#clip-search').handlers.input();
    assert.equal(app.node('[data-clips-grid]').children.length, 50);
    assert.equal(app.requests.length, 2);
});
test('date and sort apply to the entire collection', async () => {
    const app = setup([{clips: [clip('old')], cursor: 'next'},
        {clips: [{...clip('recent'), created_at: new Date().toISOString(), view_count: 100}], cursor: ''}]);
    await open(app); await ready(app);
    app.node('#clip-sort').value = 'views'; app.node('#clip-sort').handlers.change();
    assert.equal(app.node('[data-clips-grid]').children[0].children[1].textContent, 'recent');
    app.node('#clip-days').value = '1'; app.node('#clip-days').handlers.change();
    assert.equal(app.node('[data-clips-grid]').children.length, 1);
    app.node('#clip-days').value = '0'; app.node('#clip-days').handlers.change();
    assert.equal(app.node('[data-clips-grid]').children.length, 2);
    assert.ok(app.requests.every(url => url.includes('days=0') && url.includes('sort=newest')));
});
test('incomplete collections show retry instead of misleading filtered results', async () => {
    const app = setup([{clips: [clip('a')], cursor: 'repeat'}, {clips: [], cursor: 'repeat'},
        {clips: [clip('complete')], cursor: ''}]);
    await open(app); await ready(app);
    assert.equal(app.node('[data-clips-grid]').children.length, 0);
    assert.equal(app.node('[data-clips-retry]').hidden, false);
    assert.match(app.node('[data-clips-status]').textContent, /stopped progressing/);
    await app.node('[data-clips-retry]').handlers.click();
    assert.equal(app.node('[data-clips-grid]').children.length, 1);
    assert.equal(app.node('[data-clips-retry]').hidden, true);
});
test('leaving the tab during loading cannot publish a partial collection', async () => {
    const app = setup([{clips: [clip('stale')], cursor: ''}, {clips: [clip('fresh')], cursor: ''}]);
    app.node('tab').handlers.click();
    app.node('tab').dataset.workspaceTab = 'notes'; app.node('tab').handlers.click();
    await ready(app);
    assert.equal(app.node('[data-clips-grid]').children.length, 0);
    app.node('tab').dataset.workspaceTab = 'clips'; await open(app); await ready(app);
    assert.equal(app.node('[data-clips-grid]').children[0].children[1].textContent, 'fresh');
});
