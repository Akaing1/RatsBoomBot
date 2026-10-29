const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup(options = {}) {
    const element = () => ({value: '', style: {}, dataset: {}, handlers: {}, maxLength: 500,
        classList: {add() {}}, focus() { this.focused = true; },
        addEventListener(type, handler) { this.handlers[type] = handler; },
        removeEventListener(type) { delete this.handlers[type]; }});
    const form = element(), input = element(), sendButton = element(), status = element();
    const timers = new Map(); let timer = 0, completionHandled = false, destroyed = false;
    const autocomplete = {update() {}, hide() {}, handleKey: () => completionHandled,
        destroy() { assert.equal(destroyed, false, 'Autocomplete should only be disposed once'); destroyed = true; }};
    const window = {setTimeout(callback) { timers.set(++timer, callback); return timer; },
        clearTimeout(id) { timers.delete(id); }, createChatAutocomplete: () => autocomplete};
    vm.runInNewContext(fs.readFileSync('web/static/js/chat-composer.js', 'utf8'), {window, AbortController,
        getComputedStyle: () => ({borderTopWidth: '1', borderBottomWidth: '1', lineHeight: '22', paddingTop: '10', paddingBottom: '10'})});
    let resolve, reject, signal, sent = [];
    const composer = window.createChatComposer({form, input, sendButton, status,
        autocomplete: {}, send(message, abortSignal) {
            sent.push(message); signal = abortSignal;
            return new Promise((yes, no) => { resolve = yes; reject = no; });
        }, ...options});
    return {form, input, sendButton, status, composer, timers, sent,
        submit: () => form.handlers.submit({preventDefault() {}}),
        resolve: result => resolve(result), reject: error => reject(error), signal: () => signal,
        completion: value => { completionHandled = value; }, destroyed: () => destroyed};
}

test('shared composer ignores empty and oversized messages and locks concurrent submissions', async () => {
    const app = setup();
    await app.submit(); app.input.value = 'x'.repeat(501); await app.submit();
    assert.equal(app.sent.length, 0); assert.match(app.status.textContent, /500/);
    app.input.value = ' hello '; const pending = app.submit(); await app.submit();
    assert.deepEqual(app.sent, ['hello']); assert.equal(app.sendButton.disabled, true);
    app.resolve(); await pending;
    assert.equal(app.input.value, ''); assert.equal(app.sendButton.disabled, false);
});

test('sending preserves a newly typed draft and exposes transport-specific success', async () => {
    let delivered;
    const app = setup({onSent: message => { delivered = message; }, focusAfterSend: true});
    app.input.value = 'hello'; const pending = app.submit(); app.input.value = 'next';
    app.resolve({message: 'Sent to Twitch. YouTube unavailable.', tone: 'warning'}); await pending;
    assert.equal(delivered, 'hello'); assert.equal(app.input.value, 'next');
    assert.match(app.status.className, /warning/); assert.match(app.status.textContent, /YouTube/);
    assert.equal(app.input.focused, true);
});

test('failed delivery retains draft and allows retry', async () => {
    const app = setup(); app.input.value = 'hello'; const pending = app.submit();
    app.reject(new Error('Offline')); await pending;
    assert.equal(app.input.value, 'hello'); assert.equal(app.status.textContent, 'Offline');
    assert.match(app.status.className, /error/); assert.equal(app.sendButton.disabled, false);
});

test('completion consumes Enter before submit; Shift/IME Enter are not submitted', () => {
    const app = setup(); let submits = 0;
    app.form.requestSubmit = () => { submits++; };
    const enter = extras => app.input.handlers.keydown({key: 'Enter', preventDefault() {}, ...extras});
    app.completion(true); enter(); app.completion(false);
    enter({shiftKey: true}); enter({isComposing: true}); assert.equal(submits, 0);
    enter(); assert.equal(submits, 1);
});

test('destroy aborts pending delivery and removes listeners, timers and autocomplete', async () => {
    const app = setup(); app.input.value = 'hello'; const pending = app.submit();
    app.composer.showStatus('Connected', 'success', true);
    app.composer.destroy(); app.composer.destroy(); assert.equal(app.signal().aborted, true);
    assert.equal(app.timers.size, 0); assert.equal(app.destroyed(), true);
    assert.deepEqual(app.input.handlers, {}); assert.deepEqual(app.form.handlers, {});
    app.resolve(); await pending;
    assert.equal(app.input.value, 'hello'); assert.equal(app.status.textContent, 'Connected');
    app.composer.showStatus('late event', 'error', true);
    assert.equal(app.status.textContent, 'Connected'); assert.equal(app.timers.size, 0);
    app.input.style.height = '123px'; app.composer.resize();
    assert.equal(app.input.style.height, '123px', 'Late resize must not touch a closed composer');
});

test('fading send status restores a persistent disconnected warning', () => {
    const app = setup(); app.status.dataset.connectionState = 'disconnected';
    app.composer.showStatus('Sent', 'success', true);
    [...app.timers.values()][0]();
    assert.equal(app.status.textContent, 'Not connected'); assert.match(app.status.className, /error/);
});


test('local commands clear the input without sending, reporting delivery or stealing focus', async () => {
    const opened = []; let delivered = 0, cleared = 0;
    const app = setup({handleLocal: message => { opened.push(message); return true; }, onSent: () => delivered++, onInput: () => cleared++, focusAfterSend: true});
    app.input.value = ' /poll ';
    await app.submit();
    assert.deepEqual(opened, ['/poll']);
    assert.deepEqual(app.sent, []);
    assert.equal(delivered, 0);
    assert.equal(app.input.value, '');
    assert.equal(cleared, 1);
    assert.notEqual(app.input.focused, true);
    assert.equal(app.status.textContent, undefined);
    assert.equal(app.signal(), undefined);
});

test('a local handler preserves a replacement draft and its input state', async () => {
    let resets = 0;
    const app = setup({handleLocal() { app.input.value = 'new draft'; return true; }, onInput: () => resets++});
    app.input.value = '/poll';
    await app.submit();
    assert.equal(app.input.value, 'new draft');
    assert.equal(resets, 0);
    assert.deepEqual(app.sent, []);
});
