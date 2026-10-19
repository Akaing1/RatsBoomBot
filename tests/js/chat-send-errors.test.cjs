const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('web/static/js/dashboard-chat-send.js', 'utf8');
const transport = source.slice(source.indexOf('        async send(outgoingMessage, signal) {'), source.indexOf('        onSent(message) {')).trim().replace(/,$/, '');
function setup(result, ok = true) {
    const notices = [], merges = [];
    const context = {selectedTarget: 'both', form: {},
        window: {confirmDashboardChatSend: result => merges.push(result)},
        reportSendFailure: (platform, message) => notices.push({platform, message}),
        FormData: class {set() {}},
        fetch: async () => { if (result instanceof Error) throw result; return {ok, json: async () => result}; }};
    const send = vm.runInNewContext(`({${transport}}).send`, context);
    return {notices, merges, send: (signal = {aborted: false}) => send('hello', signal)};
}
test('partial sends display a private notice only for the failed platform', async () => {
    const app = setup({sent: ['twitch'], errors: {youtube: 'Reconnect YouTube.'}});
    await app.send();
    assert.deepEqual(app.notices, [{platform: 'youtube', message: 'Reconnect YouTube.'}]);
});
test('total failures report each platform once even when the request is rejected', async () => {
    const app = setup({detail: 'Failed', errors: {twitch: 'Twitch failed', youtube: 'YouTube failed'}}, false);
    await assert.rejects(app.send(), /Failed/);
    assert.deepEqual(app.notices.map(item => item.platform), ['twitch', 'youtube']);
    assert.equal(app.merges.length, 0);
});
test('network errors show uncertain delivery for both targets, but closing the page stays quiet', async () => {
    const app = setup(new Error('Network error'));
    await assert.rejects(app.send());
    assert.deepEqual(app.notices.map(item => item.platform), ['twitch', 'youtube']);
    assert.match(app.notices[0].message, /could not be confirmed/);
    const closed = setup(new Error('Aborted'));
    await assert.rejects(closed.send({aborted: true}));
    assert.equal(closed.notices.length, 0);
});
test('successful sends do not add error notices', async () => {
    const app = setup({sent: ['twitch', 'youtube'], errors: {}});
    await app.send();
    assert.equal(app.notices.length, 0);
});
