const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const axes = {users: ['vips', 'mods', 'subs', 'non_subs', 'bots', 'youtube_mods', 'youtube_members', 'youtube_non_members', 'youtube_bots'], types: ['commands', 'redeems', 'messages']};

function setup(storage = new Map(), connectedPlatforms = ['twitch', 'youtube']) {
    const handlers = {}, documentHandlers = {}, buttonHandlers = {}, changes = [];
    const timers = [];
    const connectionBadges = ['twitch', 'youtube'].map(platform => {
        const classes = new Set();
        return {dataset: {connected: String(connectedPlatforms.includes(platform))},
            classes, classList: {add(name) { classes.add(name); }}};
    });
    function input(dataset) {
        return {dataset, handlers: {}, addEventListener(event, handler) { this.handlers[event] = handler; }};
    }
    const inputs = Object.entries(axes).flatMap(([axis, keys]) => keys.map(key => input({chatFilterAxis: axis, chatFilterOption: key})));
    const groups = Object.keys(axes).map(axis => input({chatFilterGroupToggle: axis}));
    const platformInputs = ['twitch', 'youtube'].map(platform => input({chatFilterPlatform: platform}));
    platformInputs.forEach(item => { item.disabled = !connectedPlatforms.includes(item.dataset.chatFilterPlatform); });
    const clears = ['all', 'users', 'types'].map(axis => input({chatFilterClear: axis}));
    const options = {hidden: true, scrollTop: 0, contains: () => false, style: {}, getBoundingClientRect: () => ({width: 200, height: 330})};
    const countLabel = {textContent: ''};
    const classes = new Set();
    const documentState = {};
    const button = {getBoundingClientRect: () => ({right: 400, bottom: 400}), classList: {toggle(name, enabled) { if (enabled) classes.add(name); else classes.delete(name); }, contains: name => classes.has(name)}, setAttribute() {}, focus() { this.focused = true; documentState.activeElement = this; }, blur() { this.focused = false; documentState.activeElement = null; },
        addEventListener: (event, handler) => { buttonHandlers[event] = handler; }};
    const control = {dataset: {channelId: 'test'},
        querySelector: selector => selector.includes('toggle') ? button : selector.includes('count') ? countLabel : options,
        querySelectorAll: selector => selector.includes('connection') ? connectionBadges : selector.includes('group-toggle') ? groups : selector.includes('platform') ? platformInputs : selector.includes('clear') ? clears : inputs,
        addEventListener: (event, handler) => { handlers[event] = handler; },
        contains: target => [button, ...inputs, ...groups, ...platformInputs, ...clears].includes(target)};
    const context = {window: {innerWidth: 500, innerHeight: 600, addEventListener() {}, setTimeout(fn, delay) { timers.push({fn, delay}); }, localStorage: {getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value)}},
        document: Object.assign(documentState, {addEventListener: (event, handler) => { documentHandlers[event] = handler; }})};
    vm.runInNewContext(fs.readFileSync('web/static/js/dashboard-chat-filters.js', 'utf8'), context);
    const api = context.window.dashboardChatFilters;
    const filter = api.attach({closest: () => ({querySelector: () => control})}, () => changes.push(true));
    const option = key => inputs.find(item => item.dataset.chatFilterOption === key);
    const change = (key, checked) => { const item = option(key); item.checked = checked; item.handlers.change(); };
    const clear = axis => clears.find(item => item.dataset.chatFilterClear === axis).handlers.click();
    const solo = item => handlers.contextmenu({target: {closest: () => ({querySelector: selector =>
        selector.includes('platform') ? (platformInputs.includes(item) ? item : null) : (inputs.includes(item) ? item : null)})}, preventDefault() {}});
    const platform = (key, checked) => {
        const item = platformInputs.find(item => item.dataset.chatFilterPlatform === key);
        item.checked = checked; item.handlers.change();
    };
    return {api, filter, inputs, groups, platformInputs, platform, connectionBadges, timers, clears, countLabel, option, change, clear, solo, handlers, documentHandlers, buttonHandlers, options, button, changes};
}

test('connected badges fade after 1.5 seconds on first open only; disconnected badges remain visible', () => {
    const ui = setup(new Map(), ['twitch']);
    assert.equal(ui.timers.length, 0);
    ui.buttonHandlers.click();
    assert.equal(ui.timers[0].delay, 1500);
    ui.timers[0].fn();
    assert.equal(ui.connectionBadges[0].classes.has('is-fading'), true);
    assert.equal(ui.connectionBadges[1].classes.has('is-fading'), false);
    ui.buttonHandlers.click(); ui.buttonHandlers.click();
    assert.equal(ui.timers.length, 1);
});

test('disconnected platforms cannot be toggled and do not prevent the empty-selection reset', () => {
    const ui = setup(new Map(), ['twitch']);
    assert.ok(ui.inputs.filter(item => item.dataset.chatFilterOption.startsWith('youtube_')).every(item => item.disabled && !item.checked));
    ui.platform('youtube', true);
    assert.equal(ui.filter.allows({user: 'youtube_mods', type: 'messages'}), false);
    for (const key of ['vips', 'mods', 'subs', 'non_subs', 'bots']) ui.change(key, false);
    assert.ok(ui.inputs.filter(item => !item.disabled).every(item => item.checked));
    ui.clear('all');
    assert.equal(ui.option('youtube_mods').checked, false);
    assert.equal(ui.button.classList.contains('has-filter-count'), false);
});

test('platform checkboxes are hidden with fewer than two connected platforms', () => {
    for (const connected of [[], ['twitch'], ['youtube']]) {
        const ui = setup(new Map(), connected);
        assert.ok(ui.platformInputs.every(item => item.hidden));
    }
    const ui = setup();
    assert.ok(ui.platformInputs.every(item => !item.hidden));
});

test('newly connected platforms enable all their roles while preserving existing selections', () => {
    const storage = new Map();
    const ui = setup(storage, ['twitch']);
    ui.solo(ui.option('mods'));
    const connected = setup(storage, ['twitch', 'youtube']);
    assert.equal(connected.option('mods').checked, true);
    assert.equal(connected.option('subs').checked, false);
    assert.ok(connected.inputs.filter(item => item.dataset.chatFilterOption.startsWith('youtube_')).every(item => item.checked));
});

test('messages have independent user and type classifications', () => {
    const {category} = setup().api;
    assert.equal(category({kind: 'command', is_bot: true}).user, 'bots');
    assert.equal(category({kind: 'command', is_bot: true}).type, 'commands');
    assert.equal(category({is_redeem: true, badges: ['vip']}).user, 'vips');
    assert.equal(category({is_redeem: true, badges: ['vip']}).type, 'redeems');
    assert.equal(category({badges: [{name: 'moderator'}], accent: 'first-time'}).user, 'mods');
    assert.equal(category({badges: ['founder']}).user, 'subs');
    assert.equal(category({}).user, 'non_subs');
    assert.equal(category({kind: 'system'}).type, 'messages');
    assert.equal(category({platform: 'youtube', badges: ['Mod']}).user, 'youtube_mods');
    assert.equal(category({platform: 'youtube', badges: ['Member']}).user, 'youtube_members');
    assert.equal(category({platform: 'youtube'}).user, 'youtube_non_members');
    assert.equal(category({platform: 'youtube', is_bot: true}).user, 'youtube_bots');
});

test('each platform can be disabled, and only disabling both resets all users', () => {
    const storage = new Map();
    const ui = setup(storage);
    ui.platform('twitch', false);
    assert.equal(ui.filter.allows({user: 'mods', type: 'messages'}), false);
    assert.equal(ui.filter.allows({user: 'youtube_mods', type: 'messages'}), true);
    const restored = setup(storage);
    assert.equal(restored.option('mods').checked, false);
    assert.equal(restored.option('youtube_mods').checked, true);
    ui.platform('youtube', false);
    assert.ok(ui.inputs.every(item => item.checked));
    ui.platform('youtube', false);
    assert.equal(ui.filter.allows({user: 'youtube_mods', type: 'messages'}), false);
    assert.equal(ui.filter.allows({user: 'mods', type: 'messages'}), true);
    ui.platform('twitch', false);
    assert.ok(ui.inputs.every(item => item.checked));
});

test('unchecking individual roles leaves an empty platform disabled until all users are disabled', () => {
    const ui = setup();
    for (const role of ['vips', 'mods', 'subs', 'non_subs', 'bots']) ui.change(role, false);
    assert.equal(ui.option('mods').checked, false);
    assert.equal(ui.option('youtube_mods').checked, true);
    for (const role of ['youtube_mods', 'youtube_members', 'youtube_non_members', 'youtube_bots']) ui.change(role, false);
    assert.ok(ui.inputs.every(item => item.checked));
});

test('right-click platform solo affects users but preserves the message-type selection', () => {
    const ui = setup();
    ui.solo(ui.option('commands'));
    const youtube = ui.platformInputs.find(item => item.dataset.chatFilterPlatform === 'youtube');
    ui.solo(youtube);
    assert.equal(ui.filter.allows({user: 'youtube_mods', type: 'commands'}), true);
    assert.equal(ui.filter.allows({user: 'mods', type: 'commands'}), false);
    assert.equal(ui.filter.allows({user: 'youtube_mods', type: 'messages'}), false);
    ui.solo(youtube);
    assert.equal(ui.filter.allows({user: 'mods', type: 'commands'}), true);
});

test('defaults are checked and selections require both axes to match', () => {
    const ui = setup();
    assert.ok(ui.inputs.every(item => item.checked && !item.indeterminate));
    assert.equal(ui.filter.allows({user: 'bots', type: 'commands'}), true);
    ui.solo(ui.option('mods'));
    assert.equal(ui.filter.allows({user: 'mods', type: 'commands'}), true);
    assert.equal(ui.filter.allows({user: 'bots', type: 'commands'}), false);
    ui.solo(ui.option('messages'));
    assert.equal(ui.filter.allows({user: 'mods', type: 'messages'}), true);
    assert.equal(ui.filter.allows({user: 'mods', type: 'commands'}), false);
    ui.change('messages', false);
    assert.equal(ui.filter.allows({user: 'mods', type: 'commands'}), true);
    assert.ok(ui.inputs.filter(item => item.dataset.chatFilterAxis === 'types').every(item => item.checked));
});

test('solo and repeated solo affect only the selected axis', () => {
    const ui = setup();
    ui.solo(ui.option('commands'));
    ui.solo(ui.option('bots'));
    assert.equal(ui.filter.allows({user: 'bots', type: 'commands'}), true);
    assert.equal(ui.filter.allows({user: 'bots', type: 'messages'}), false);
    ui.solo(ui.option('bots'));
    assert.ok(ui.inputs.filter(item => item.dataset.chatFilterAxis === 'users').every(item => item.checked && !item.indeterminate));
    assert.equal(ui.option('commands').checked, true);
});

test('Clear enables all in its axis and Clear all enables both', () => {
    const ui = setup();
    ui.solo(ui.option('commands'));
    ui.solo(ui.option('mods'));
    ui.clear('users');
    assert.ok(ui.inputs.filter(item => item.dataset.chatFilterAxis === 'users').every(item => item.checked));
    assert.equal(ui.option('commands').checked, true);
    assert.equal(ui.option('messages').checked, false);
    ui.clear('users');
    assert.equal(ui.option('bots').checked, true);
    ui.clear('types'); ui.clear('types');
    assert.equal(ui.option('commands').checked, true);
    ui.change('bots', true); ui.change('messages', true);
    ui.clear('all'); assert.ok(ui.inputs.every(item => item.checked && !item.indeterminate));
    ui.clear('all'); assert.ok(ui.inputs.every(item => item.checked && !item.indeterminate));
});

test('persistence respects independent axes and migrates old names', () => {
    const storage = new Map([['ratsboombot:chat-filters:test', JSON.stringify(['normal', 'other'])]]);
    const ui = setup(storage);
    assert.equal(ui.option('non_subs').checked, true);
    assert.equal(ui.option('messages').checked, true);
    ui.clear('users');
    assert.equal(ui.option('bots').checked, true);
    assert.equal(ui.option('commands').checked, false);
    ui.change('commands', true);
    const restored = setup(storage);
    assert.equal(restored.option('commands').checked, true);
    assert.equal(restored.option('messages').checked, true);
    assert.equal(restored.option('redeems').checked, false);
});

test('dropdown remains open during edits and closes on outside click or Escape', () => {
    const ui = setup();
    ui.buttonHandlers.click();
    ui.change('mods', true); ui.clear('types');
    ui.documentHandlers.click({target: ui.option('mods')});
    assert.equal(ui.options.hidden, false);
    assert.equal(ui.handlers.focusout, undefined);
    ui.handlers.keydown({key: 'Escape', preventDefault() {}, stopPropagation() {}});
    assert.equal(ui.options.hidden, true);
    assert.equal(ui.button.focused, true);
    ui.buttonHandlers.click(); ui.documentHandlers.click({target: {}});
    assert.equal(ui.options.hidden, true);
});

test('blocked storage does not prevent filtering', () => {
    const ui = setup({get() { throw Error('blocked'); }, set() { throw Error('blocked'); }});
    ui.solo(ui.option('subs'));
    assert.equal(ui.filter.allows({user: 'subs', type: 'messages'}), true);
    assert.equal(ui.filter.allows({user: 'bots', type: 'messages'}), false);
});

test('Clear buttons are visible only for sections with disabled options', () => {
    const ui = setup();
    const clear = axis => ui.clears.find(item => item.dataset.chatFilterClear === axis);
    assert.ok(ui.clears.every(item => item.hidden));
    ui.change('mods', false);
    assert.equal(clear('users').hidden, false);
    assert.equal(clear('types').hidden, true);
    assert.equal(clear('all').hidden, false);
    ui.change('commands', false);
    assert.equal(clear('types').hidden, false);
    ui.clear('users');
    assert.equal(clear('users').hidden, true);
    assert.equal(clear('all').hidden, false);
    ui.clear('types');
    assert.ok(ui.clears.every(item => item.hidden));
    ui.solo(ui.option('bots'));
    assert.equal(clear('users').hidden, false);
    ui.solo(ui.option('bots'));
    assert.ok(ui.clears.every(item => item.hidden));
});

test('button count tracks enabled options across both independent sections', () => {
    const ui = setup();
    assert.equal(ui.countLabel.textContent, '| 12');
    assert.equal(ui.button.classList.contains('has-filter-count'), false);
    ui.change('bots', false);
    assert.equal(ui.countLabel.textContent, '| 11');
    assert.equal(ui.button.classList.contains('has-filter-count'), true);
    ui.solo(ui.option('messages'));
    assert.equal(ui.countLabel.textContent, '| 9');
    ui.clear('all');
    assert.equal(ui.countLabel.textContent, '| 12');
    assert.equal(ui.button.classList.contains('has-filter-count'), false);
});

test('unchecking the last user option re-enables that section and persists it', () => {
    const storage = new Map();
    const ui = setup(storage);
    ui.solo(ui.option('mods'));
    ui.solo(ui.option('commands'));
    ui.change('mods', false);
    assert.ok(ui.inputs.filter(item => item.dataset.chatFilterAxis === 'users').every(item => item.checked));
    assert.equal(ui.option('commands').checked, true);
    assert.equal(ui.option('messages').checked, false);
    assert.equal(ui.filter.allows({user: 'bots', type: 'commands'}), true);
    assert.equal(ui.filter.allows({user: 'bots', type: 'messages'}), false);
    const restored = setup(storage);
    assert.equal(restored.option('bots').checked, true);
    assert.equal(restored.option('messages').checked, false);
});

test('dropdown shifts up to keep its bottom in the viewport and tracks the button when space permits', () => {
    const ui = setup();
    ui.buttonHandlers.click();
    assert.equal(ui.options.style.top, '262px');
    assert.equal(ui.options.style.left, '200px');
    assert.equal(ui.options.style.overflowY, 'visible');
    const place = ui.api.dropdownPosition;
    const viewport = {top: 0, left: 0, width: 500, height: 800};
    assert.equal(place({right: 400, bottom: 100}, {width: 200, height: 330}, viewport).top, 106);
    assert.equal(place({right: 510, bottom: 700}, {width: 200, height: 330}, viewport).top, 462);
    assert.equal(place({right: 510, bottom: 700}, {width: 200, height: 330}, viewport).left, 292);
});

test('oversized dropdown scrolls inside the viewport and returns to natural height when it fits', () => {
    const ui = setup();
    let height = 900;
    ui.options.getBoundingClientRect = () => ({width: 200, height});
    ui.buttonHandlers.click();
    assert.equal(ui.options.style.top, '8px');
    assert.equal(ui.options.style.maxHeight, '584px');
    assert.equal(ui.options.style.overflowY, 'auto');
    height = 330;
    ui.documentHandlers.scroll({target: {}});
    assert.equal(ui.options.style.maxHeight, 'none');
    assert.equal(ui.options.style.overflowY, 'visible');
    assert.equal(ui.options.style.top, '262px');
});

test('scrolling inside the dropdown does not remeasure or reset its scroll position', () => {
    const ui = setup();
    let measurements = 0;
    ui.options.getBoundingClientRect = () => { measurements++; return {width: 200, height: 900}; };
    ui.buttonHandlers.click();
    ui.options.scrollTop = 150;
    const before = measurements;
    ui.documentHandlers.scroll({target: ui.options});
    assert.equal(measurements, before);
    assert.equal(ui.options.scrollTop, 150);
    ui.documentHandlers.scroll({target: {}});
    assert.equal(ui.options.scrollTop, 150);
});

test('switching carousel cards dismisses the dropdown', () => {
    const ui = setup();
    ui.buttonHandlers.click();
    assert.equal(ui.options.hidden, false);
    ui.button.focus();
    ui.documentHandlers['dashboard-carousel-card-changed']();
    assert.equal(ui.options.hidden, true);
    assert.equal(ui.button.focused, false);
});
