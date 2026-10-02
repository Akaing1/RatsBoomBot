const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../../web/static/js/dashboard-stream-player.js'), 'utf8');

function setup(live = true) {
    const handlers = {};
    const documentHandlers = {};
    const windowHandlers = {};
    const commands = [];
    let creations = 0;
    const mount = {id: 'preview', dataset: {channel: 'example', isLive: String(live)}};
    const status = {};
    class Player {
        constructor(id, options) { creations++; assert.equal(options.autoplay, false); }
        addEventListener(name, handler) { handlers[name] = handler; }
        play() { commands.push('play'); }
        pause() { commands.push('pause'); handlers.PAUSE(); }
        setChannel(channel) { commands.push(`channel:${channel}`); }
    }
    for (const name of ['READY', 'ONLINE', 'OFFLINE', 'PLAY', 'PLAYING', 'PAUSE', 'PLAYBACK_BLOCKED']) Player[name] = name;
    const document = {
        hidden: false,
        querySelector: selector => selector === '[data-stream-player]' ? mount : status,
        addEventListener: (name, handler) => { documentHandlers[name] = handler; }
    };
    vm.runInNewContext(source, {
        document, Twitch: {Player},
        window: {Twitch: {Player}, location: {hostname: 'localhost'},
            addEventListener: (name, handler) => { windowHandlers[name] = handler; }}
    });
    return {handlers, documentHandlers, windowHandlers, document, commands, status,
        creations: () => creations};
}

test('asks the user to start a live preview instead of autoplaying', () => {
    const app = setup();
    app.handlers.READY();
    assert.match(app.status.textContent, /Press Play/);
    assert.equal(app.status.hidden, false);
    assert.deepEqual(app.commands, []);
});

test('only shows the start prompt once an offline channel goes live', () => {
    const app = setup(false);
    app.handlers.READY();
    assert.equal(app.status.hidden, true);
    app.handlers.ONLINE();
    assert.equal(app.status.hidden, false);
    assert.match(app.status.textContent, /Press Play/);
    assert.deepEqual(app.commands, []);
});

test('dismisses the prompt when the user starts the Twitch player', () => {
    const app = setup();
    app.handlers.READY();
    app.handlers.PLAY();
    assert.equal(app.status.hidden, true);
    app.handlers.PLAYING();
    app.windowHandlers['dashboard-stream-live-changed']({detail: {isLive: true}});
    assert.equal(app.status.hidden, true);
    assert.deepEqual(app.commands, []);
});

test('pausing shows a resume prompt without automatically restarting', () => {
    const app = setup();
    app.handlers.READY();
    app.handlers.PLAYING();
    app.handlers.PAUSE();
    assert.match(app.status.textContent, /resume/);
    app.handlers.ONLINE();
    assert.deepEqual(app.commands, []);
});

test('tab and layout changes do not issue playback commands or recreate the player', () => {
    const app = setup();
    app.handlers.READY();
    app.handlers.PLAYING();
    app.document.hidden = true;
    app.documentHandlers.visibilitychange?.();
    app.document.hidden = false;
    app.documentHandlers.visibilitychange?.();
    app.windowHandlers.resize?.();
    app.documentHandlers.transitionend?.();
    assert.deepEqual(app.commands, []);
    assert.equal(app.creations(), 1);
});

test('stops an offline preview and asks again when it goes live', () => {
    const app = setup();
    app.handlers.READY();
    app.handlers.PLAYING();
    app.handlers.OFFLINE();
    assert.deepEqual(app.commands, ['pause']);
    assert.equal(app.status.hidden, true);
    app.handlers.ONLINE();
    assert.match(app.status.textContent, /Press Play/);
    assert.deepEqual(app.commands, ['pause']);
});

test('simulation selects a channel but still waits for the user to press Play', () => {
    const app = setup(false);
    app.handlers.READY();
    app.windowHandlers['dashboard-stream-test-start']({detail: {channel: 'testchannel'}});
    assert.match(app.status.textContent, /Press Play/);
    assert.deepEqual(app.commands, ['channel:testchannel']);
    app.windowHandlers['dashboard-stream-test-stop']({detail: {isLive: false}});
    assert.deepEqual(app.commands, ['channel:testchannel', 'channel:example']);
    assert.equal(app.status.hidden, true);
    assert.equal(app.creations(), 1);
});

test('blocked playback asks for native Play without an automatic retry', () => {
    const app = setup();
    app.handlers.READY();
    app.handlers.PLAYBACK_BLOCKED();
    assert.match(app.status.textContent, /Playback was blocked.*Press Play/);
    assert.deepEqual(app.commands, []);
});
