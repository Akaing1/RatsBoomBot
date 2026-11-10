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
            replaceChildren() {this.children = [];}, append(child) {this.children.push(child);}, close() {}, removeAttribute() {}});
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
test('newest fills through sparse and empty intervals until history ends', async () => {
    const app = setup([{clips: [clip('a'),clip('b')], cursor: 'older'}, {clips: [], cursor: 'older2'},
        {clips: [clip('b'), ...Array.from({length: 47}, (_, i) => clip('c'+i))], cursor: ''}]);
    await app.node('#clip-sort').handlers.change();
    assert.equal(app.requests.length, 3);
    assert.equal(app.node('[data-clips-grid]').children.length, 49);
    assert.equal(app.node('[data-clips-more]').hidden, true);
});
test('load more fills another batch without stopping at existing count', async () => {
    const app = setup([{clips: Array.from({length: 50}, (_, i) => clip('a'+i)), cursor: 'next'},
        {clips: [clip('b')], cursor: 'next2'}, {clips: [clip('c')], cursor: ''}]);
    await app.node('#clip-sort').handlers.change();
    assert.equal(app.requests.length, 1);
    await app.node('[data-clips-more]').handlers.click();
    assert.equal(app.requests.length, 3);
    assert.equal(app.node('[data-clips-grid]').children.length, 52);
});
