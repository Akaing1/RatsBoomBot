const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
    constructor() { this.children = []; this.handlers = {}; this.attrs = {}; this.classes = new Set();
        this.classList = {toggle: (name, on) => on ? this.classes.add(name) : this.classes.delete(name)}; }
    setAttribute(name, value) { this.attrs[name] = value; }
    append(...children) { this.children.push(...children); }
    appendChild(child) { this.children.push(child); }
    replaceChildren() { this.children = []; }
    addEventListener(name, handler) { this.handlers[name] = handler; }
    contains(target) { return this === target || this.children.some(child => child.contains(target)); }
    querySelector() { return this.children.find(child => child.classes.has('active')); }
    scrollIntoView() {}
    focus() {}
}
function setup() {
    const input = new Element(), box = new Element(), handlers = {}, window = {};
    input.maxLength = 500; input.value = ''; input.selectionStart = input.selectionEnd = 0;
    input.setRangeText = (value, start, end) => {
        input.value = input.value.slice(0, start) + value + input.value.slice(end);
        input.selectionStart = input.selectionEnd = start + value.length;
    };
    input.dispatchEvent = () => controller.update();
    vm.runInNewContext(fs.readFileSync('web/static/js/chat-autocomplete.js', 'utf8'), {
        window, document: {createElement: () => new Element(), addEventListener: (name, handler) => { handlers[name] = handler; },
            removeEventListener: name => { delete handlers[name]; }}, Event: class {}
    });
    const emotes = [{name: 'Kappa', provider: 'twitch', url: 'https://static-cdn.jtvnw.net/emotes/25/2.0'},
        {name: 'KapWave', provider: '7tv', url: 'https://cdn.7tv.app/emote/abc/2x.webp'},
        {name: 'KapBad', provider: '7tv', url: 'https://untrusted.example/emote.png'}];
    let limited = false;
    const controller = window.createChatAutocomplete({input, box, getEmotes: () => emotes,
        getUsers: () => [{username: 'chatter', display_name: 'Chat Friend'}],
        getCommands: () => [{name: 'clear', kind: 'command', value: '/clear', label: '/clear'}], onLimit: () => { limited = true; }});
    return {input, box, controller, handlers, limited: () => limited,
        type(value) { input.value = value; input.selectionStart = input.selectionEnd = value.length; controller.update(); },
        key(key, extra = {}) { const event = {key, preventDefault() {this.prevented = true;}, ...extra}; controller.handleKey(event); return event; }};
}
test('shared emote autocomplete supports keyboard navigation and replaces only the current token', () => {
    const app = setup(); app.type('hello :kap'); assert.equal(app.box.children.length, 2);
    app.key('ArrowDown'); assert.equal(app.box.children[1].attrs['aria-selected'], 'true');
    app.key('Tab'); assert.equal(app.input.value, 'hello KapWave '); assert.equal(app.box.hidden, true);
});
test('shared autocomplete handles mentions, main-chat slash commands, and Escape', () => {
    const app = setup(); app.type('@chat'); app.key('Enter'); assert.equal(app.input.value, '@chatter ');
    app.type('/cl'); app.key('Tab'); assert.equal(app.input.value, '/clear ');
    app.type(':kap'); app.key('Escape'); assert.equal(app.box.hidden, true); assert.equal(app.input.value, ':kap');
});

test('arrow navigation reuses suggestion nodes and updates only selection state', () => {
    const app = setup(); app.type(':kap');
    const first = app.box.children[0], second = app.box.children[1];
    app.key('ArrowDown');
    assert.equal(app.box.children[0], first); assert.equal(app.box.children[1], second);
    assert.equal(first.attrs['aria-selected'], 'false'); assert.equal(second.attrs['aria-selected'], 'true');
    app.key('ArrowDown'); assert.equal(first.attrs['aria-selected'], 'true');
    app.key('ArrowUp'); assert.equal(second.attrs['aria-selected'], 'true');
    second.handlers.click(); assert.equal(app.input.value, 'KapWave ');
});
test('click completes without losing caret focus and outside click closes suggestions', () => {
    const app = setup(); app.type(':kap'); app.box.children[0].handlers.click(); assert.equal(app.input.value, 'Kappa ');
    app.type(':kap'); app.handlers.click({target: new Element()}); assert.equal(app.box.hidden, true);
    app.controller.destroy(); assert.equal(app.handlers.click, undefined);
});
test('autocomplete respects the character limit and IME composition', () => {
    const app = setup(); app.type('x'.repeat(494) + ' :kap'); app.key('Tab'); assert.equal(app.limited(), true);
    app.type(':kap'); app.key('Enter', {isComposing: true}); assert.equal(app.input.value, ':kap');
});
