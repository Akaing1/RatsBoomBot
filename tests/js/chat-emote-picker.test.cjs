const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
    constructor() { this.children = []; this.handlers = {}; this.dataset = {}; this.attributes = {}; this.value = ''; }
    append(...children) { this.children.push(...children); }
    appendChild(child) { this.children.push(child); }
    replaceChildren(...children) { this.children = children; }
    setAttribute(name, value) { this.attributes[name] = value; }
    addEventListener(type, handler) { this.handlers[type] = handler; }
    removeEventListener(type) { delete this.handlers[type]; }
}
function setup() {
    const picker = new Element(), window = {}, inserted = [];
    let emotes = [
        {name: 'Mine', provider: 'twitch', group_key: 'mine', group: 'My channel', group_image: 'https://static-cdn.jtvnw.net/avatar.png', url: 'https://static-cdn.jtvnw.net/emotes/1/2.0'},
        {name: 'Kappa', provider: 'twitch', group_key: 'twitch:global', group: 'Global', url: 'https://static-cdn.jtvnw.net/emotes/2/2.0'},
        {name: 'Wave', provider: '7tv', group: '7TV', url: 'https://cdn.7tv.app/emote/1/2x.webp'}
    ];
    let comparisons = 0;
    const context = {window, document: {createElement: () => new Element()}, countComparison: () => { comparisons++; }};
    vm.createContext(context);
    vm.runInContext('const compare = String.prototype.localeCompare; String.prototype.localeCompare = function(...args) { countComparison(); return compare.apply(this, args); };', context);
    vm.runInContext(fs.readFileSync('web/static/js/chat-emote-picker.js', 'utf8'), context);
    const options = {picker, getEmotes: () => emotes, getPersonalGroup: () => 'mine', insert: value => inserted.push(value)};
    const view = window.createChatEmotePicker(options);
    view.renderGroups(); view.render();
    const grid = picker.children[1].children[0], rail = picker.children[1].children[1];
    return {picker, view, grid, rail, inserted, options, create: window.createChatEmotePicker,
        comparisons: () => comparisons, emotes, setEmotes: value => { emotes = value; }};
}

test('searches reuse catalog sorting and refreshes invalidate it without mutating the source', () => {
    const app = setup(), initial = app.comparisons();
    assert.ok(initial > 0);
    assert.deepEqual(app.emotes.map(emote => emote.name), ['Mine', 'Kappa', 'Wave']);
    app.view.render();
    app.view.search.value = 'a'; app.view.search.handlers.input();
    app.rail.children[1].handlers.click();
    assert.equal(app.comparisons(), initial);
    app.setEmotes([...app.emotes, {name: 'Alpha', provider: '7tv', group: '7TV', url: 'https://cdn.7tv.app/emote/2/2x.webp'}]);
    app.view.render();
    assert.ok(app.comparisons() > initial);
    assert.deepEqual(app.grid.children[0].children[1].children.map(button => button.children[1].textContent), ['Alpha', 'Wave']);
});

test('shared picker preserves dashboard sections, channel icons and high-resolution emotes', () => {
    const app = setup();
    assert.equal(app.picker.children[1].className, 'chat-emote-picker-body');
    assert.deepEqual(app.grid.children.map(section => section.children[0].textContent), ['Your channel · My channel', 'Global', '7TV']);
    assert.equal(app.rail.children[0].children[0].children[0].src, 'https://static-cdn.jtvnw.net/avatar.png');
    assert.equal(app.rail.children[1].children[0].src, '/static/img/7tv.svg');
    assert.match(app.grid.children[2].children[1].children[0].children[0].srcset, /3x\.webp 3x/);
    assert.equal(app.picker.children[0].children[1].children[0].textContent, '3');
});

test('7TV section toggles, search filters case-insensitively, and disposed pickers ignore late actions', () => {
    const app = setup(), sevenTv = app.rail.children[1];
    sevenTv.handlers.click(); assert.equal(app.grid.children.length, 1);
    assert.equal(sevenTv.attributes['aria-pressed'], 'true');
    sevenTv.handlers.click(); assert.equal(app.grid.children.length, 3);
    app.view.search.value = 'waVE'; app.view.search.handlers.input();
    assert.equal(app.grid.children.length, 1);
    const option = app.grid.children[0].children[1].children[0];
    option.handlers.click(); assert.deepEqual(app.inserted, ['Wave']);
    app.view.destroy(); app.view.destroy(); option.handlers.click();
    assert.deepEqual(app.inserted, ['Wave']);
    assert.equal(app.view.search.handlers.input, undefined); assert.equal(sevenTv.handlers.click, undefined);
});

test('dashboard markup is reused by the same component instead of rebuilt', () => {
    const app = setup(); app.view.destroy();
    const controls = {
        '[data-emote-search]': app.view.search, '[data-emote-group]': app.rail,
        '[data-emote-channels]': app.rail.children[0], '[data-emote-seventv]': app.rail.children[1],
        '[data-emote-grid]': app.grid, '[data-emote-count]': app.picker.children[0].children[1].children[0],
        '[data-emote-note]': app.view.note
    };
    app.picker.querySelector = selector => controls[selector];
    app.picker.replaceChildren = () => { throw new Error('Existing dashboard markup must stay in place'); };
    const view = app.create(app.options); view.renderGroups(); view.render();
    assert.equal(view.search, app.view.search); assert.equal(app.grid.children.length, 3);
});
