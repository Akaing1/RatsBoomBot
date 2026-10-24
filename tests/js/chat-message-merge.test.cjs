const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('combined messages match the All selector sky blue without changing either platform color', () => {
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.match(styles, /\.live-chat-message\[data-merged-message-id\] \{ --chat-edge-color: #7dd3fc; \}/);
    assert.match(styles, /\.chat-target-cycle\[data-target="both"\] \{ color: #7dd3fc; \}/);
});

class Element {
    constructor() { this.children = []; this.dataset = {}; this.hidden = false; this.deleted = false;
        this.classList = {contains: name => name === 'is-deleted' && this.deleted}; }
    insertBefore(child, before) { child.parent = this; const index = this.children.indexOf(before); this.children.splice(index < 0 ? this.children.length : index, 0, child); }
    remove() { this.parent.children.splice(this.parent.children.indexOf(this), 1); }
    querySelector(selector) {
        for (const child of this.children) {
            if ((child.className || '').split(' ').includes(selector.slice(1))) return child;
            const nested = child.querySelector(selector); if (nested) return nested;
        }
    }
}
function setup() {
    const window = {}, events = [], allowed = new Set(['twitch', 'youtube']);
    vm.runInNewContext(fs.readFileSync('web/static/js/chat-message-merge.js', 'utf8'), {
        window, document: {createElement: () => new Element(), dispatchEvent: event => events.push(event)},
        CustomEvent: class {constructor(type, options) {this.type = type; this.detail = options.detail;}}
    });
    const merger = window.createChatMessageMerger({allows: row => allowed.has(row.platform)});
    function row(id) {
        const result = new Element(); result.dataset.messageId = id; result.platform = id.split(':')[0];
        const heading = new Element(); heading.className = 'live-chat-message-heading';
        heading.insertBefore(new Element(), null); heading.insertBefore(new Element(), null);
        result.insertBefore(heading, null); return result;
    }
    return {merger, allowed, row, events, confirm: window.confirmDashboardChatSend};
}
const ids = {twitch: 'twitch:tw1', youtube: 'youtube:yt1'};

test('only a confirmed successful All send registers a merge', () => {
    const app = setup();
    app.confirm({sent: ['twitch'], errors: {youtube: 'Offline'}, message_ids: ids});
    app.confirm({sent: ['twitch', 'youtube'], errors: {youtube: 'Failed'}, message_ids: ids});
    app.confirm({sent: ['twitch', 'youtube'], errors: {}, message_ids: {twitch: ids.twitch}});
    assert.equal(app.events.length, 0);
    app.confirm({sent: ['twitch', 'youtube'], errors: {}, message_ids: ids});
    assert.equal(app.events.length, 1); assert.equal(app.events[0].type, 'dashboard-chat-send-confirmed');
});

test('echoes can arrive before confirmation and merge by ID without replacing the Twitch row', () => {
    const app = setup(), twitch = app.row(ids.twitch), youtube = app.row(ids.youtube);
    app.merger.track(twitch); app.merger.track(youtube);
    assert.equal(youtube.hidden, false);
    app.merger.register(ids);
    assert.equal(twitch.hidden, false); assert.equal(youtube.hidden, true);
    assert.equal(twitch.dataset.messageId, ids.twitch);
    assert.equal(twitch.dataset.mergedMessageId, ids.youtube);
    const badge = twitch.querySelector('.live-chat-merged-platform');
    assert.equal(badge.textContent, 'YT'); assert.equal(badge.hidden, false);
    app.merger.register(ids);
    assert.equal(twitch.querySelector('.live-chat-message-heading').children.length, 3);
});

test('confirmation can arrive first and YouTube echo can arrive before Twitch', () => {
    const app = setup(), twitch = app.row(ids.twitch), youtube = app.row(ids.youtube);
    app.merger.register(ids); app.merger.track(youtube);
    assert.equal(youtube.hidden, false, 'The only received echo remains visible');
    app.merger.track(twitch); assert.equal(youtube.hidden, true); assert.equal(twitch.hidden, false);
    const unrelated = app.row('youtube:another-identical-message'); app.merger.track(unrelated);
    assert.equal(unrelated.hidden, false, 'Identical text from another send is never deduplicated');
});

test('platform filters reveal the appropriate original copy and restore the combined badge', () => {
    const app = setup(), twitch = app.row(ids.twitch), youtube = app.row(ids.youtube);
    app.merger.track(twitch); app.merger.track(youtube); app.merger.register(ids);
    app.allowed.delete('twitch'); app.merger.refresh();
    assert.equal(twitch.hidden, true); assert.equal(youtube.hidden, false);
    app.allowed.add('twitch'); app.allowed.delete('youtube'); app.merger.refresh();
    assert.equal(twitch.hidden, false); assert.equal(youtube.hidden, true);
    assert.equal(twitch.querySelector('.live-chat-merged-platform').hidden, true);
    app.allowed.add('youtube'); app.merger.refresh();
    assert.equal(twitch.querySelector('.live-chat-merged-platform').hidden, false);
});

test('deleting or trimming one platform does not hide the surviving message', () => {
    const app = setup(), twitch = app.row(ids.twitch), youtube = app.row(ids.youtube);
    app.merger.track(twitch); app.merger.track(youtube); app.merger.register(ids);
    twitch.deleted = true; app.merger.refresh(); assert.equal(youtube.hidden, false);
    twitch.deleted = false; app.merger.refresh(); assert.equal(youtube.hidden, true);
    app.merger.forget(twitch); assert.equal(youtube.hidden, false);
    assert.equal(twitch.dataset.mergedMessageId, undefined);
    assert.equal(twitch.querySelector('.live-chat-merged-platform'), undefined);
    app.merger.destroy(); app.merger.destroy();
});

test('deletion refresh touches only the affected pair, not every merged message', () => {
    const app = setup(), twitch = app.row(ids.twitch), youtube = app.row(ids.youtube);
    app.merger.track(twitch); app.merger.track(youtube); app.merger.register(ids);
    const other = {twitch: 'twitch:other', youtube: 'youtube:other'};
    app.merger.track(app.row(other.twitch)); app.merger.track(app.row(other.youtube)); app.merger.register(other);
    let checks = 0;
    const has = app.allowed.has.bind(app.allowed);
    app.allowed.has = platform => { checks++; return has(platform); };
    twitch.deleted = true; app.merger.refresh(ids.twitch);
    assert.equal(checks, 2);
    assert.equal(youtube.hidden, false);
    app.merger.refresh('twitch:not-merged');
    assert.equal(checks, 2);
});
