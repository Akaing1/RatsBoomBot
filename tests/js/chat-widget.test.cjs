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
    assert.equal(success.status.textContent, 'Sent');
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
