const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('rich dashboard composer completes arguments with Tab while keeping its platform selection',
    {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
        const browser = await chromium.launch({executablePath, headless: true});
        try {
            const page = await browser.newPage();
            await page.setContent('<form><button type="button" id="target">[Twitch]</button><textarea maxlength="500"></textarea><button id="send">Send</button><p id="status"></p></form><div id="suggestions" hidden></div>');
            for (const file of ['chat-emote-input', 'chat-autocomplete', 'chat-target-selector', 'chat-composer']) {
                await page.addScriptTag({path: `web/static/js/${file}.js`});
            }
            const source = fs.readFileSync('web/static/js/dashboard-chat-send.js', 'utf8');
            const insert = source.slice(source.indexOf('    function insertValue('), source.indexOf('    function renderPicker('));
            await page.addScriptTag({content: `
                const form = document.querySelector('form');
                const messageInput = createChatEmoteInput({input: form.querySelector('textarea'), getEmotes: () => []});
                const emotePicker = {}, emoteToggle = {setAttribute() {}};
                function hideSuggestions() { composer.autocomplete.hide(); }
                function showStatus() { throw Error('Unexpected character limit'); }
                ${insert}
                window.sent = [];
                window.selector = createChatTargetSelector({form, button: document.querySelector('#target'), input: messageInput, youtubeAvailable: true, onChange() {}});
                const composer = createChatComposer({form, input: messageInput, sendButton: document.querySelector('#send'), status: document.querySelector('#status'),
                    autocomplete: {box: document.querySelector('#suggestions'), getUsers: () => [{username:'chatter'}],
                        getCommands: () => [{kind:'command', name:'timeout', value:'/timeout', syntax:'/timeout <username> [seconds] [reason]', label:'/timeout', arguments:{1:['60','300']}}],
                        insert: (suggestion, range) => insertValue(suggestion.value, range)},
                    onKey: event => selector.handleKey(event, () => composer.autocomplete.handleKey(event)),
                    send: async message => { window.sent.push(message); }});
            `});
            const input = page.locator('.chat-rich-input');
            await input.fill('/time'); await input.press('Tab');
            assert.equal(await page.locator('textarea').inputValue(), '/timeout ');
            await input.press('ArrowRight');
            assert.equal(await page.locator('textarea').inputValue(), '/timeout chatter ');
            await input.press('Tab');
            assert.equal(await page.locator('textarea').inputValue(), '/timeout chatter 60 ');
            assert.equal(await page.evaluate(() => selector.target()), 'twitch');
            assert.deepEqual(await page.evaluate(() => sent), []);
            await input.press('Enter');
            assert.deepEqual(await page.evaluate(() => sent), ['/timeout chatter 60']);
        } finally { await browser.close(); }
    });
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
function setup(overrides = {}) {
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
        getCommands: () => [{name: 'clear', kind: 'command', value: '/clear', label: '/clear'}], onLimit: () => { limited = true; }, ...overrides});
    return {input, box, controller, handlers, limited: () => limited,
        type(value) { input.value = value; input.selectionStart = input.selectionEnd = value.length; controller.update(); },
        key(key, extra = {}) { const event = {key, preventDefault() {this.prevented = true;}, ...extra}; controller.handleKey(event); return event; }};
}

const definition = (syntax, arguments_) => ({kind: 'command', name: syntax.split(' ')[0].slice(1),
    value: syntax.split(' ')[0], syntax, label: syntax, description: 'Test command', arguments: arguments_});

test('slash completion cascades through username and duration without submitting', () => {
    const app = setup({getCommands: () => [definition('/timeout <username> [seconds] [reason]', {1: ['60', '300', '600']})]});
    app.type('/time'); app.key('Tab');
    assert.equal(app.input.value, '/timeout ');
    assert.equal(app.box.hidden, false);
    app.key('Enter'); assert.equal(app.input.value, '/timeout chatter ');
    assert.equal(app.box.children.length, 3);
    app.key('ArrowDown'); app.key('Tab');
    assert.equal(app.input.value, '/timeout chatter 300 ');
    assert.equal(app.box.hidden, true, 'Reasons are free text');
});

test('bot completion follows nested subcommands and fixed choices', () => {
    const commands = [definition('!set slowmode on|off'), definition('!set title <stream title>'), definition('!socials twitch')];
    const app = setup({getCommands: () => commands});
    app.type('!s');
    assert.equal(app.box.children.length, 2, 'A root command appears once despite multiple syntaxes');
    app.type('!set '); assert.equal(app.box.children.length, 2);
    app.type('!set slow'); app.key('Tab'); assert.equal(app.input.value, '!set slowmode ');
    assert.equal(app.box.children.length, 2);
    app.type('!set slowmode on'); app.key('Enter'); assert.equal(app.input.value, '!set slowmode on ');
    assert.equal(app.box.hidden, true);
    app.type('!set title A custom stream title'); assert.equal(app.box.hidden, true);
    app.type('hello !set '); assert.equal(app.box.hidden, true);
});

test('Right Arrow accepts the selected command or argument at the token end', () => {
    const app = setup({getCommands: () => [definition('!set slowmode on|off')]});
    app.type('!se'); assert.equal(app.key('ArrowRight').prevented, true);
    assert.equal(app.input.value, '!set ');
    app.key('ArrowRight'); assert.equal(app.input.value, '!set slowmode ');
    app.key('ArrowDown'); app.key('ArrowRight');
    assert.equal(app.input.value, '!set slowmode on ');
});

test('Right Arrow keeps cursor movement and selection shortcuts when not accepting a completion', () => {
    const app = setup({getCommands: () => [definition('/timeout <username> [seconds]')]});
    for (const extra of [{shiftKey: true}, {ctrlKey: true}, {altKey: true}, {metaKey: true}, {isComposing: true}]) {
        app.type('/time'); assert.equal(app.key('ArrowRight', extra).prevented, undefined);
        assert.equal(app.input.value, '/time');
    }
    app.type('/timeout chatzzz');
    app.input.selectionStart = app.input.selectionEnd = '/timeout chat'.length;
    app.controller.update();
    assert.equal(app.key('ArrowRight').prevented, undefined);
    assert.equal(app.input.value, '/timeout chatzzz');
    app.type('/timeout chat'); app.input.selectionStart--;
    assert.equal(app.key('ArrowRight').prevented, undefined, 'Selected text must not be replaced');
    app.type('ordinary text'); assert.equal(app.key('ArrowRight').prevented, undefined);
});

test('editing an argument replaces its complete token and preserves later arguments', () => {
    const app = setup({getCommands: () => [definition('/timeout <username> [seconds] [reason]')]});
    app.type('/timeout chatzzz 60 test reason');
    app.input.selectionStart = app.input.selectionEnd = '/timeout chat'.length;
    app.controller.update(); app.key('Tab');
    assert.equal(app.input.value, '/timeout chatter 60 test reason');
});

test('argument choices include literal alternatives without inserting placeholder names', () => {
    const app = setup({getCommands: () => [definition('!points gamble <amount|all>'), definition('!pets buy <ticket|summon|summon ticket>')]});
    app.type('!points gamble '); assert.equal(app.box.children.length, 1);
    app.key('Tab'); assert.equal(app.input.value, '!points gamble all ');
    app.type('!pets buy summon '); app.key('Tab'); assert.equal(app.input.value, '!pets buy summon ticket ');
});

test('Tab loads missing usernames for argument completion and ignores a changed draft', async () => {
    let users = [], resolve;
    const app = setup({getCommands: () => [definition('/ban <username> [reason]')], getUsers: () => users,
        loadUsers: () => new Promise(done => { resolve = () => { users = [{username: 'chatter'}]; done(); }; })});
    app.type('/ban chat'); assert.equal(app.key('Tab').prevented, true);
    resolve(); await new Promise(done => setImmediate(done));
    assert.equal(app.input.value, '/ban chatter ');
    users = []; app.type('/ban chat'); app.key('Tab'); app.type('different draft');
    resolve(); await new Promise(done => setImmediate(done));
    assert.equal(app.input.value, 'different draft');
});
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
