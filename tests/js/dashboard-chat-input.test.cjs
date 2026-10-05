const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('web/static/js/dashboard-chat-send.js', 'utf8');
const resize = source.match(/    function resizeMessageInput\(\) \{[\s\S]*?\n    \}/)[0];

test('reply labels show distinct display names and otherwise only the username', () => {
    const begin = source.match(/    function beginReply\([\s\S]*?\n    \}/)[0];
    const context = {replyMessageId: {}, replyName: {}, replyPreview: {}, replyContext: {},
        defaultMessagePlaceholder: 'Send a message... (supports autocomplete)',
        selectedTarget: 'twitch', messageInput: {value: 'draft', focus() {}}};
    vm.createContext(context);
    vm.runInContext(begin, context);
    for (const [displayName, expected] of [['チなみ', 'チなみ (minamichimaa)'],
        ['Minamichimaa', 'minamichimaa'], ['', 'minamichimaa']]) {
        context.beginReply({messageId: 'twitch:123', username: 'minamichimaa', displayName});
        assert.equal(context.replyName.textContent, `Replying to ${expected}`);
        assert.equal(context.messageInput.placeholder, `Replying to ${expected}...`);
        assert.equal(context.messageInput.value, 'draft');
    }
    const clear = source.match(/    function clearReply\(\) \{[\s\S]*?\n    \}/)[0];
    vm.runInContext(clear, context);
    context.clearReply();
    assert.equal(context.messageInput.placeholder, context.defaultMessagePlaceholder);
    assert.equal(context.messageInput.value, 'draft');
});

test('composer grows with wrapped text and returns to its baseline after clearing', () => {
    const messageInput = {style: {}, value: '', scrollHeight: 140};
    const context = {messageInput, getComputedStyle: () => ({borderTopWidth: '1px', borderBottomWidth: '1px',
        lineHeight: '22px', paddingTop: '10px', paddingBottom: '10px'})};
    vm.createContext(context);
    vm.runInContext(resize, context);
    context.resizeMessageInput();
    assert.equal(messageInput.style.height, '44px');
    messageInput.value = 'wrapped text';
    messageInput.scrollHeight = 140;
    context.resizeMessageInput();
    assert.equal(messageInput.style.height, '142px');
    messageInput.value = '';
    context.resizeMessageInput();
    assert.equal(messageInput.style.height, '44px');
});

test('autocomplete cannot insert text beyond the input limit', () => {
    const insert = source.match(/    function insertValue\(value, range = null\) \{[\s\S]*?\n    \}/)[0];
    let warning;
    const messageInput = {value: 'x'.repeat(499), maxLength: 500, selectionStart: 499, selectionEnd: 499,
        setRangeText() { throw new Error('Should not insert an oversized completion'); }};
    const context = {messageInput, showStatus: message => { warning = message; }};
    vm.createContext(context);
    vm.runInContext(insert, context);
    context.insertValue('Kappa');
    assert.match(warning, /500/);
    assert.equal(messageInput.value.length, 499);
});
