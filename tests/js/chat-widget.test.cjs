const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup(result, ok = true) {
    const handlers = {};
    const input = {value: 'hello', addEventListener(type, fn) { handlers[type] = fn; }, focus() {}};
    const button = {}, status = {};
    const form = {action: '/widgets/chat/token/send', querySelector: selector =>
        selector.includes('message') ? input : selector.includes('submit') ? button : status,
        addEventListener(type, fn) { handlers[type] = fn; }};
    vm.runInNewContext(fs.readFileSync('web/static/js/chat-widget.js', 'utf8'), {
        document: {querySelector: selector => selector.includes('reload') ? null : form},
        window: {setTimeout() {}, clearTimeout() {}}, AbortController,
        FormData: class {}, fetch: async () => ({ok, json: async () => result})
    });
    return {input, button, status, send: () => handlers.submit({preventDefault() {}})};
}
test('dock clears successful sends but preserves rejected drafts', async () => {
    const success = setup({sent: ['twitch'], errors: {}});
    await success.send();
    assert.equal(success.input.value, '');
    assert.equal(success.status.textContent, '');
    assert.equal(success.button.disabled, false);
    const failure = setup({detail: 'Sign in to send'}, false);
    await failure.send();
    assert.equal(failure.input.value, 'hello');
    assert.equal(failure.status.textContent, 'Sign in to send');
});
test('partial sends show the failed destination', async () => {
    const app = setup({sent: ['twitch'], errors: {youtube: 'YouTube offline'}});
    await app.send();
    assert.equal(app.status.textContent, 'YouTube offline');
});

test('dock picker loads trusted emotes, inserts separated text, and disables for YouTube', async () => {
    let config, rendered = 0;
    const handlers = {}, targetHandlers = {};
    const input = {value: 'hello', selectionStart: 5, selectionEnd: 5,
        addEventListener(type, fn) { handlers[type] = fn; }, focus() {}, dispatchEvent() {},
        setRangeText(text, start, end) { this.value = this.value.slice(0, start) + text + this.value.slice(end); }};
    const target = {value: 'twitch', addEventListener(type, fn) { targetHandlers[type] = fn; }};
    const toggle = {addEventListener(type, fn) { this[type] = fn; }, setAttribute() {}};
    const picker = {hidden: true}, status = {}, button = {};
    const form = {querySelector: selector => selector.includes('message') ? input
        : selector.includes('submit') ? button : selector.includes('picker') ? picker
        : selector.includes('emotes') ? toggle : status, addEventListener() {}};
    const view = {search: {focus() {}}, note: {}, render() { rendered++; }, renderGroups() {}};
    vm.runInNewContext(fs.readFileSync('web/static/js/chat-widget.js', 'utf8'), {
        document: {querySelector: selector => selector === '#dock-target' ? target : form, addEventListener() {}},
        window: {createChatEmotePicker(options) { config = options; return view; }},
        AbortController, Event, Date,
        fetch: async () => ({ok: true, json: async () => ({emotes: [
            {name: 'Kappa', url: 'https://static-cdn.jtvnw.net/emotes/v2/25/default/dark/2.0'},
            {name: 'bad', url: 'https://evil.example/image'}]})})
    });
    toggle.click();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(picker.hidden, false);
    assert.equal(config.getEmotes().length, 1);
    assert.equal(rendered, 1);
    config.insert('Kappa');
    assert.equal(input.value, 'hello Kappa ');
    target.value = 'youtube'; targetHandlers.change();
    assert.equal(toggle.disabled, true);
    assert.equal(picker.hidden, true);
});
