const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web/static/js/dashboard-raid-browser.js', 'utf8');

class Element {
    constructor() {
        this.handlers = {}; this.children = []; this.hidden = false; this.value = '';
        this.dataset = {}; this.classes = new Set(); this.attributes = {};
        this.style = {setProperty(name, value) { this[name] = value; }}; this.scrollTop = 0; this.clientWidth = 760; this.clientHeight = 400;
        this.classList = {add: name => this.classes.add(name), remove: name => this.classes.delete(name),
            toggle: (name, on) => on ? this.classes.add(name) : this.classes.delete(name)};
    }
    addEventListener(name, handler) { this.handlers[name] = handler; }
    setAttribute(name, value) { this.attributes[name] = value; }
    append(...children) { children.forEach(child => this.insertBefore(child, null)); }
    insertBefore(child, before) {
        child.remove();
        const index = before ? this.children.indexOf(before) : this.children.length;
        this.children.splice(index, 0, child); child.parent = this;
    }
    remove() {
        if (this.parent) this.parent.children.splice(this.parent.children.indexOf(this), 1);
        this.parent = null;
    }
    replaceChildren(...children) { this.children.forEach(child => { child.parent = null; }); this.children = []; this.append(...children); }
    contains(element) { return this === element || this.children.some(child => child.contains(element)); }
    querySelector(tag) {
        for (const child of this.children) {
            if (child.tagName === tag || (tag.startsWith('.') && String(child.className || '').split(' ').includes(tag.slice(1)))) return child;
            const nested = child.querySelector(tag);
            if (nested) return nested;
        }
    }
    focus() { this.focused = true; }
    click() { this.handlers.click?.(); }
    showModal() { this.open = true; }
    showPopover() { this.popoverOpen = true; }
    hidePopover() { this.popoverOpen = false; this.handlers.toggle?.({newState: 'closed'}); }
    close() { this.open = false; this.handlers.close(); }
    getBoundingClientRect() { return {left: 20, top: 20, right: 500, bottom: 500}; }
    animate(frames, options) {
        this.animations ||= [];
        const animation = {frames, options, finished: Promise.resolve(), cancel() { this.cancelled = true; }};
        this.animations.push(animation);
        return animation;
    }
}
function setup(storage = new Map(), account = '1', hash = '', viewportWidth = 1280) {
    let taskTimeOffset = 0;
    const location = {origin: 'http://localhost:4345', pathname: '/channel', search: '?test=1', hash};
    const windowHandlers = {};
    const setLocation = value => {
        const url = new URL(value, location.origin + location.pathname + location.search);
        location.hash = url.hash; location.pathname = url.pathname; location.search = url.search;
    };
    const dialog = new Element(), opener = new Element(), search = new Element(), input = new Element();
    const results = new Element(), status = new Element(), tagOptions = new Element(), close = new Element(), root = new Element();
    const cardView = new Element(), listView = new Element();
    const collectionTabs = new Element();
    const collectionSelect = new Element();
    const filtersToggle = new Element();
    const tagSearch = new Element(), selectedTags = new Element(), tagLimit = new Element(), tagMatchToggle = new Element();
    const matchCurrent = new Element(), matchAlternate = new Element();
    matchCurrent.className = 'queue-state-current'; matchAlternate.className = 'queue-state-alternate';
    tagMatchToggle.append(matchCurrent, matchAlternate);
    tagLimit.hidden = true;
    const categorySearch = new Element(), categoryOptions = new Element();
    const sizeSlider = new Element(); sizeSlider.value = '1';
    const browseTab = new Element(), favoritesTab = new Element(), teamTab = new Element(), developerTab = new Element(), manageButton = new Element(), manager = new Element();
    const managerClose = new Element(), managerStatus = new Element(), favoriteList = new Element(), blockedList = new Element();
    const previewDialog = new Element();
    const previewControls = {};
    for (const name of ['video', 'chat', 'raid', 'status', 'back', 'close', 'identity', 'stream-title', 'meta', 'tags', 'description', 'body', 'badges', 'events', 'teams', 'favorite', 'menu', 'block', 'main', 'details', 'footer'])
        previewControls[`[data-raid-preview-${name}]`] = new Element();
    previewDialog.querySelector = selector => previewControls[selector] || previewControls['[data-raid-preview-badges]'].querySelector(selector)
        || previewControls['[data-raid-preview-video]'].querySelector(selector);
    const previewPaneButtons = ['video', 'chat'].map(pane => {
        const button = new Element(); button.dataset.raidPreviewPane = pane; return button;
    });
    previewDialog.querySelectorAll = () => previewPaneButtons;
    const favoriteTab = new Element(), blacklistTab = new Element(), favoritePanel = new Element(), blacklistPanel = new Element();
    favoriteTab.dataset.raidListTab = 'favorites'; blacklistTab.dataset.raidListTab = 'blacklist';
    blacklistPanel.hidden = true;
    browseTab.dataset.raidBrowserTab = 'browse'; favoritesTab.dataset.raidBrowserTab = 'favorites';
    teamTab.dataset.raidBrowserTab = 'team';
    favoritesTab.hidden = true; teamTab.hidden = true;
    developerTab.dataset.raidBrowserTab = 'developer'; developerTab.hidden = true;
    for (const [button, label] of [[browseTab, 'Browse'], [favoritesTab, 'Favorites'], [teamTab, 'Stream team'], [developerTab, 'Developer']]) button.textContent = label;
    const managerControls = {'[data-raid-lists-close]': managerClose, '[data-raid-lists-status]': managerStatus,
        '[data-raid-favorite-list]': favoriteList, '[data-raid-blocked-list]': blockedList,
        '[data-raid-list-panel="favorites"]': favoritePanel, '[data-raid-list-panel="blacklist"]': blacklistPanel};
    manager.querySelector = selector => managerControls[selector];
    manager.querySelectorAll = () => [favoriteTab, blacklistTab];
    cardView.dataset.raidBrowserView = 'cards'; listView.dataset.raidBrowserView = 'list';
    const requests = [], events = [];
    const timers = new Map(), delays = new Map(); let nextTimer = 0;
    dialog.dataset.browserUrl = '/channel/api/raid-browser';
    dialog.dataset.channelId = account;
    const controls = {'[data-raid-browser-search]': search, '[data-raid-browser-results]': results,
        '[data-raid-collection-tabs]': collectionTabs,
        '[data-raid-collection-select]': collectionSelect,
        '[data-raid-filters-toggle]': filtersToggle,
        '[data-raid-browser-status]': status, '#raid-browser-category-options': categoryOptions, '#raid-browser-tag-options': tagOptions, '[data-raid-selected-tags]': selectedTags, '[data-raid-browser-close]': close,
        '[data-raid-lists-open]': manageButton, '[data-raid-browser-size]': sizeSlider};
    dialog.querySelector = selector => controls[selector];
    dialog.querySelectorAll = selector => selector === '[data-raid-browser-view]' ? [cardView, listView] : [browseTab, favoritesTab, teamTab, developerTab];
    const fields = {};
    const teamFilter = new Element(); teamFilter.hidden = true;
    for (const name of ['sort', 'category_id', 'tags', 'tag_match', 'follow_status', 'language', 'same_team', 'event', 'team']) {
        fields[name] = new Element();
        fields[name].type = ['tags', 'tag_match', 'language', 'category_id', 'sort', 'event', 'follow_status', 'team'].includes(name) ? 'text' : 'checkbox';
        if (name === 'tag_match') fields[name].value = 'all';
        fields[name].checked = false;
        if (name === 'sort') fields[name].value = 'for_you';
    }
    search.querySelector = selector => selector === '[data-raid-team-filter]' ? teamFilter : selector === 'input' ? input : selector === '[data-raid-tag-search]' ? tagSearch : selector === '[data-raid-tag-limit]' ? tagLimit : selector === '[data-raid-tag-match]' ? tagMatchToggle : selector === '[data-raid-category-search]' ? categorySearch : fields[selector.match(/name="([^"]+)"/)?.[1]];
    let onResize;
    const resizeCallbacks = [];
    const confirmations = []; let confirmResult = true;
    const viewport = {innerWidth: viewportWidth};
    const createdElements = [], intervals = [];
    vm.runInNewContext(source, {
        document: {dispatchEvent: event => events.push(event), querySelector: selector => ({'[data-raid-browser]': dialog, '[data-raid-browser-open]': opener, '[data-raid-lists]': manager, '[data-raid-preview]': previewDialog})[selector],
            documentElement: root, createElement: tag => { const element = new Element(); element.tagName = tag; createdElements.push(element); return element; }},
        window: Object.assign(viewport, {location, addEventListener: (name, handler) => { windowHandlers[name] = handler; },
            createRaidPreviewChat: (host, channel) => {
                const chat = new Element(); chat.channel = channel; host.replaceChildren(chat);
                return {destroy() { chat.destroyed = true; host.replaceChildren(); }};
            },
            history: {pushState: (_, __, url) => setLocation(url), replaceState: (_, __, url) => setLocation(url)},
            confirm: message => { confirmations.push(message); return confirmResult; }, localStorage: {
            getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value)}}), URL, URLSearchParams, AbortController,
        Date: class extends Date { static now() { return Date.now() + taskTimeOffset; } },
        CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
        ResizeObserver: class { constructor(callback) { onResize = callback; resizeCallbacks.push(callback); } observe() {} },
        requestAnimationFrame: callback => setImmediate(callback), cancelAnimationFrame: clearImmediate,
        setTimeout: (callback, delay) => { timers.set(++nextTimer, callback); delays.set(nextTimer, delay); return nextTimer; },
        clearTimeout: id => timers.delete(id),
        setInterval: callback => { intervals.push(callback); return intervals.length; }, clearInterval: () => {},
        fetch: (url, options) => new Promise(resolve => requests.push({url, options,
            respond: (payload, ok = true) => resolve({ok, json: async () => payload})}))
    });
    return {advanceTime: seconds => { taskTimeOffset += seconds * 1000; }, location, viewport, createdElements, tick: () => intervals.forEach(callback => callback()), windowHandlers, dialog, opener, search, input, results, status, tagOptions, close, root, requests, events, timers, delays, fields, storage, cardView, listView, filtersToggle, collectionTabs, collectionSelect,
        browseTab, favoritesTab, teamTab, developerTab, manageButton, manager, managerClose, managerStatus, favoriteList, blockedList, confirmations, previewDialog, previewControls, previewPaneButtons,
        sizeSlider, tagSearch, tagLimit, tagMatchToggle, selectedTags, categorySearch, categoryOptions, favoriteTab, blacklistTab, favoritePanel, blacklistPanel,
        confirm: value => { confirmResult = value; },
        grid: () => results.children[0].children[0], resize: () => onResize(), resizePreview: () => resizeCallbacks[0]()};
}
const flush = () => new Promise(resolve => setImmediate(() => setImmediate(resolve)));

for (const ready of [false, true]) test(`hover preload is reused on click when ${ready ? 'complete' : 'still running'}`, async () => {
    const app = setup();
    app.opener.handlers.pointerenter({pointerType: 'mouse'});
    app.opener.handlers.pointerenter({pointerType: 'mouse'});
    assert.equal(app.requests.length, 1);
    assert.ok(!app.dialog.open);
    if (ready) { app.requests[0].respond({channels: [channel()], cursor: ''}); await flush(); }
    app.opener.handlers.click();
    assert.equal(app.requests.length, 1);
    if (!ready) app.requests[0].respond({channels: [channel()], cursor: ''});
    await flush();
    assert.equal(app.grid().children.length, 1);
    assert.equal(app.requests.length, 1);
});

test('expired or mismatched hover preloads are aborted and replaced', async () => {
    for (const expired of [false, true]) {
        const app = setup(); app.opener.handlers.pointerenter({pointerType: 'mouse'});
        if (expired) app.advanceTime(61);
        else app.fields.language.value = 'ja';
        app.opener.handlers.click();
        assert.equal(app.requests[0].options.signal.aborted, true);
        assert.equal(app.requests.length, 2);
        app.requests[1].respond({channels: [channel('3')], cursor: ''}); await flush();
        assert.equal(app.grid().children[0].dataset.channelId, '3');
    }
});

test('failed hover preload retries on opening without showing an early error', async () => {
    const app = setup(); app.opener.handlers.pointerenter({pointerType: 'mouse'});
    app.requests[0].respond({detail: 'Temporary failure'}, false); await flush();
    assert.ok(!app.dialog.open);
    app.opener.handlers.click(); await flush();
    assert.equal(app.requests.length, 2);
    app.requests[1].respond({channels: [channel()], cursor: ''}); await flush();
    assert.equal(app.grid().children.length, 1);
});

test('touch entry does not preload and closing aborts an adopted hover request', () => {
    const app = setup(); app.opener.handlers.pointerenter({pointerType: 'touch'});
    assert.equal(app.requests.length, 0);
    app.opener.handlers.pointerenter({pointerType: 'mouse'});
    app.opener.handlers.click(); app.close.handlers.click();
    assert.equal(app.requests[0].options.signal.aborted, true);
});

test('compact layout toggle keeps its sliding bubble aligned with its buttons', () => {
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.match(styles, /\.raid-browser-size-control \{[^}]*height: 38px/);
    assert.match(styles, /\.raid-browser-dialog > \.raid-browser-header > button \{ height: 38px; min-height: 38px/);
    assert.match(styles, /\.raid-browser-view-toggle \{ --raid-view-size: 30px;[^}]*align-self: center/);
    assert.match(styles, /\.raid-browser-view-toggle::before \{[^}]*transform: translateX\(var\(--raid-view-size\)\)/);
    assert.match(styles, /\.raid-browser-view-toggle button \{[^}]*width: var\(--raid-view-size\); height: var\(--raid-view-size\)/);
});

test('shared tab background follows selection and returns to Browse on reset', async () => {
    const app = setup();
    app.collectionTabs.getBoundingClientRect = () => ({left: 40, top: 60, right: 500, bottom: 110});
    app.browseTab.getBoundingClientRect = () => ({left: 40, top: 60, right: 140, bottom: 110});
    app.teamTab.getBoundingClientRect = () => ({left: 250, top: 60, right: 380, bottom: 110});
    app.opener.handlers.click();
    assert.equal(app.collectionTabs.style['--raid-tab-x'], '0px');
    assert.equal(app.collectionTabs.style['--raid-tab-width'], '100px');
    app.requests[0].respond({channels: [], cursor: '', team_available: true}); await flush();
    app.teamTab.hidden = false;
    app.teamTab.handlers.click();
    assert.equal(app.collectionTabs.style['--raid-tab-x'], '210px');
    assert.equal(app.collectionTabs.style['--raid-tab-width'], '130px');
    assert.equal(app.collectionTabs.style['--raid-tab-height'], '51px');
    app.search.handlers.reset({preventDefault() {}});
    assert.equal(app.collectionTabs.style['--raid-tab-x'], '0px');
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.match(styles, /transition: transform .22s ease, width .22s ease, height .22s ease/);
    assert.match(styles, /@media \(prefers-reduced-motion: reduce\) \{ \.raid-browser-heading-group \.raid-browser-tabs.has-tab-indicator::before \{ transition: none/);
});

test('raid browser uses dashboard surfaces and primary action colors', () => {
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.match(styles, /\.raid-browser-dialog \{ --raid-collection-background: var\(--background\)/);
    const card = styles.split('\n.raid-browser-channel {')[1].split('}')[0];
    assert.match(card, /background: var\(--surface\)/);
    assert.match(styles, /\.raid-browser-channel\.is-favorite \{ border-color: rgb\(250 204 21 \/ \.5\); \}/);
    const raid = styles.split('\n.raid-browser-start-raid {')[1].split('}')[0];
    assert.match(raid, /background: var\(--accent\)/);
    assert.match(styles, /\.raid-browser-start-raid:not\(:disabled\):is\(:hover,:focus-visible\) \{ background: var\(--accent-hover\)/);
    assert.match(styles, /\.raid-browser-reset, \.raid-browser-mobile-filter-button \{[^}]*background: var\(--surface-raised\); color: var\(--text\)/);
});

test('mobile filters open on demand and apply edits only on Submit', async () => {
    const app = setup(new Map(), '1', '', 390);
    app.opener.handlers.click();
    app.requests[0].respond({channels: [], cursor: ''}); await flush();
    assert.ok(!app.input.focused);
    app.filtersToggle.handlers.click();
    assert.equal(app.filtersToggle.attributes['aria-expanded'], 'true');
    assert.ok(app.dialog.classes.has('is-filters-open'));
    app.input.value = 'new search';
    app.search.handlers.input({target: app.input});
    app.fields.language.value = 'ja';
    app.search.handlers.change({target: app.fields.language});
    app.fields.follow_status.value = 'not_following';
    app.search.handlers.change({target: app.fields.follow_status});
    app.tagSearch.value = 'Artist';
    app.tagSearch.handlers.keydown({key: 'Enter', preventDefault() {}});
    assert.equal(app.requests.length, 1);
    app.search.handlers.submit({preventDefault() {}});
    assert.equal(app.requests.length, 2);
    assert.equal(app.requests[1].url.searchParams.get('query'), 'new search');
    assert.equal(app.requests[1].url.searchParams.get('language'), 'ja');
    assert.equal(app.requests[1].url.searchParams.get('tags'), 'Artist');
    assert.equal(app.requests[1].url.searchParams.get('not_following'), 'true');
    assert.equal(app.filtersToggle.attributes['aria-expanded'], 'false');
    const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
    assert.match(template, /raid-browser-filter-submit"><button[^>]*type="submit">Submit/);
});

test('returning to the wide layout applies pending mobile filters once', async () => {
    const app = setup(new Map(), '1', '', 390);
    app.opener.handlers.click();
    app.requests[0].respond({channels: [], cursor: ''}); await flush();
    app.filtersToggle.handlers.click();
    app.fields.event.value = 'drops_enabled';
    app.search.handlers.change({target: app.fields.event});
    app.viewport.innerWidth = 1000;
    app.windowHandlers.resize();
    assert.equal(app.requests.length, 2);
    assert.equal(app.requests[1].url.searchParams.get('event'), 'drops_enabled');
    assert.equal(app.filtersToggle.attributes['aria-expanded'], 'false');
    app.windowHandlers.resize();
    assert.equal(app.requests.length, 2);
});

test('mobile filters dismiss on outside press or Escape without submitting', async () => {
    const app = setup(new Map(), '1', '', 390);
    app.opener.handlers.click();
    app.requests[0].respond({channels: [], cursor: ''}); await flush();
    app.filtersToggle.handlers.click();
    app.dialog.handlers.pointerdown({target: app.search});
    assert.equal(app.filtersToggle.attributes['aria-expanded'], 'true');
    app.dialog.handlers.pointerdown({target: app.results});
    assert.equal(app.filtersToggle.attributes['aria-expanded'], 'false');
    app.filtersToggle.handlers.click();
    app.dialog.handlers.keydown({key: 'Escape', preventDefault() {}, stopPropagation() {}});
    assert.equal(app.filtersToggle.attributes['aria-expanded'], 'false');
    assert.equal(app.dialog.open, true);
    assert.equal(app.requests.length, 1);
});
test('expanding card tags stay top anchored with a fixed offset instead of bottom aligning', () => {
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.match(styles, /\.raid-browser-dialog:not\(\.is-list-view\) \.raid-browser-channel-footer \{[^}]*align-items: flex-start/);
    assert.match(styles, /\.raid-browser-dialog:not\(\.is-list-view\) \.raid-browser-channel-footer \{[^}]*margin-top: 0/);
    assert.match(styles, /\.raid-browser-channel-footer \.raid-browser-tags \{[^}]*align-items: flex-start/);
    assert.match(styles, /margin-top: max\(0px, calc\(30px - var\(--raid-tags-height\)\)\); align-content: flex-start/);
    assert.match(styles, /\.raid-browser-dialog:not\(\.is-list-view\) \.raid-browser-tags span \{ box-sizing: border-box; min-height: var\(--raid-tags-height\)/);
});

test('title tabs and view controls sit together above the results card', () => {
    const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
    const header = template.split('<div class="raid-browser-header">')[1].split('<div class="raid-browser-body">')[0];
    const toolbar = template.split('<div class="raid-browser-results-toolbar">')[1].split('<div class="raid-browser-results"')[0];
    assert.ok(toolbar.indexOf('id="raid-browser-title"') < toolbar.indexOf('class="raid-browser-tabs"'));
    assert.match(toolbar, /data-raid-browser-tab="browse"/);
    assert.match(toolbar, /class="raid-browser-size-control"/);
    assert.match(toolbar, /class="raid-browser-size-small" aria-hidden="true">Small/);
    assert.match(toolbar, /class="raid-browser-size-large" aria-hidden="true">Large/);
    assert.ok(!toolbar.includes('data-raid-browser-size-label'));
    assert.ok(!header.includes('id="raid-browser-title"'));
    assert.ok(!header.includes('class="raid-browser-size-control"'));
    assert.ok(!header.includes('class="raid-browser-view-toggle"'));
    assert.match(header, /class="button raid-browser-reset" type="reset" form="raid-browser-filters"/);
    assert.match(header, /class="raid-browser-search-heading" for="raid-browser-channel-search">Search/);
    assert.ok(header.indexOf('raid-browser-search-heading') < header.indexOf('raid-browser-reset'));
    assert.match(template, /id="raid-browser-channel-search" type="search" name="query"/);
    assert.match(template, /<form id="raid-browser-filters" class="raid-browser-filters"/);
    assert.equal((template.match(/type="reset"/g) || []).length, 2);
    assert.ok(!template.includes('raid-browser-collection-toolbar'));
    assert.ok(template.indexOf('data-raid-lists-open') < template.indexOf('class="raid-browser-collection"'));
    assert.ok(template.indexOf('class="raid-browser-size-control"') < template.indexOf('class="raid-browser-results-shell"'));
    assert.ok(template.indexOf('class="raid-browser-view-toggle"') < template.indexOf('class="raid-browser-results"'));
    assert.match(template, /class="raid-browser-manage-lists"[^>]*aria-label="Manage favorites and blacklist"[^>]*><svg[^>]*>.*<circle cx="12" cy="19"/);
});

test('mobile is large one-column grid and restores desktop size and layout across the breakpoint', async () => {
    const storage = new Map([['ratsboombot:raid-browser-view:1', 'list'], ['ratsboombot:raid-browser-size:1', '0']]);
    const app = setup(storage, '1', '', 750);
    assert.ok(!app.dialog.classes.has('is-list-view'));
    assert.equal(app.dialog.dataset.resultSize, '2');
    app.opener.handlers.click();
    app.requests[0].respond({channels: [{id: '2', login: 'target', title: '', tags: [], viewers: 2}], cursor: ''});
    await flush();
    app.sizeSlider.value = '0'; app.sizeSlider.handlers.input(); await flush();
    assert.equal(app.grid().style.gridTemplateColumns, 'repeat(1,minmax(0,1fr))');
    assert.equal(app.dialog.dataset.resultSize, '2');
    assert.equal(app.grid().style.gridAutoRows, `${Math.ceil((app.results.clientWidth - 22) * 9 / 16 + 164)}px`);
    assert.equal(storage.get('ratsboombot:raid-browser-size:1'), '0');
    app.listView.handlers.click();
    assert.ok(!app.dialog.classes.has('is-list-view'));
    assert.equal(storage.get('ratsboombot:raid-browser-view:1'), 'list');
    app.viewport.innerWidth = 751; app.windowHandlers.resize(); await flush();
    assert.ok(app.dialog.classes.has('is-list-view'));
    assert.equal(app.dialog.dataset.resultSize, '0');
    app.viewport.innerWidth = 750; app.windowHandlers.resize(); await flush();
    assert.ok(!app.dialog.classes.has('is-list-view'));
    assert.equal(app.dialog.dataset.resultSize, '2');
    assert.equal(app.grid().style.gridTemplateColumns, 'repeat(1,minmax(0,1fr))');
});

test('mobile Reset stays inside the filter panel and mobile-only controls share its breakpoint', () => {
    const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
    const form = template.split('<form id="raid-browser-filters"')[1].split('</form>')[0];
    assert.match(form, /raid-browser-filter-submit">.*type="submit">Submit.*type="reset">Reset/);
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    const mobile = styles.split(/@media \(max-width: 750px\) \{\r?\n    \.raid-browser-search-heading/)[1].split(/\r?\n\}/)[0];
    assert.match(mobile, /\.raid-browser-header > \.raid-browser-reset, \.raid-browser-view-toggle, \.raid-browser-size-control \{ display: none/);
    assert.match(mobile, /raid-browser-mobile-filter-button \{[^}]*margin-left: auto/);
    assert.ok(!template.includes('data-raid-size-toggle'));
});

test('status and countdown help live in the search side without reserving a card footer', () => {
    const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.ok(!template.includes('raid-browser-footer'));
    assert.ok(!styles.includes('raid-browser-footer'));
    const filters = template.split('<form id="raid-browser-filters"')[1].split('</form>')[0];
    assert.match(filters, /class="raid-browser-feedback">\s*<p class="raid-browser-status" data-raid-browser-status/);
    assert.ok(!template.includes('raid-browser-raid-note'));
    assert.match(source, /showStatus\("Starting a raid queues Twitch’s countdown\. Use Twitch chat for Raid Now\.", false, 4000\)/);
    assert.ok(!styles.includes('.raid-browser-dialog > .raid-browser-status:not(:empty)'));
});

test('countdown guidance uses the status, fades after four seconds, and does not repeat on tab changes', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel()], cursor: ''}); await flush();
    assert.match(app.status.textContent, /Starting a raid queues Twitch’s countdown/);
    const fade = [...app.timers.keys()].find(id => app.delays.get(id) === 4000);
    app.timers.get(fade)();
    assert.equal(app.status.classes.has('is-fading'), true);
    const clear = [...app.timers.keys()].find(id => app.delays.get(id) === 350);
    app.timers.get(clear)();
    assert.equal(app.status.textContent, '');
    assert.equal(app.status.classes.has('is-fading'), false);
    app.teamTab.handlers.click();
    app.requests[1].respond({channels: [channel()], cursor: ''}); await flush();
    assert.equal(app.status.textContent, '');
});

test('an old guidance fade cannot hide a newer error, and closing cancels its timer', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel()], cursor: ''}); await flush();
    const fade = [...app.timers.keys()].find(id => app.delays.get(id) === 4000);
    const staleFade = app.timers.get(fade);
    app.search.handlers.submit({preventDefault() {}});
    app.requests[1].respond({detail: 'Reconnect Twitch.'}, false); await flush();
    staleFade();
    assert.equal(app.status.textContent, 'Reconnect Twitch.');
    assert.equal(app.status.classes.has('is-fading'), false);
    assert.equal(app.timers.has(fade), false);
    app.dialog.close(); app.opener.handlers.click();
    app.requests[2].respond({channels: [channel()], cursor: ''}); await flush();
    const reopened = [...app.timers.keys()].find(id => app.delays.get(id) === 4000);
    assert.ok(reopened);
    app.dialog.close();
    assert.equal(app.timers.has(reopened), false);
});

test('results header stays on one line, compresses spacing and scrolls tabs without shrinking them', () => {
    const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.match(template, /class="raid-browser-tab-scroll">\s*<div class="raid-browser-tabs" data-raid-collection-tabs/);
    assert.match(styles, /\.raid-browser-results-toolbar \{[^}]*container-type: inline-size;[^}]*flex-wrap: nowrap/);
    assert.match(styles, /\.raid-browser-heading-group \{[^}]*flex-wrap: nowrap;[^}]*gap: clamp/);
    assert.match(styles, /\.raid-browser-result-controls \{[^}]*flex-wrap: nowrap/);
    assert.match(styles, /\.raid-browser-tab-scroll \{[^}]*padding-bottom: 12px;[^}]*margin-bottom: -12px;[^}]*overflow-x: auto;[^}]*overflow-y: hidden/);
    assert.match(styles, /\.raid-browser-heading-group \.raid-browser-tabs \{[^}]*width: max-content;[^}]*flex-wrap: nowrap/);
    assert.match(styles, /\.raid-browser-heading-group \.raid-browser-tabs button \{[^}]*flex: 0 0 auto/);
    assert.match(styles, /\.raid-browser-size-control input \{ width: clamp\(48px,/);
});

test('mobile collection dropdown mirrors available tabs, selects them and resets to Browse', async () => {
    const app = setup(new Map(), '1', '', 390);
    app.opener.handlers.click();
    assert.deepEqual(app.collectionSelect.children.map(option => option.value), ['browse']);
    app.requests[0].respond({channels: [], cursor: '', team_live: true, developers_live: true, favorites_live: false});
    await flush();
    assert.deepEqual(app.collectionSelect.children.map(option => option.value), ['browse', 'team', 'developer']);
    assert.deepEqual(app.collectionSelect.children.map(option => option.textContent), ['Browse', 'Stream team', 'Developer']);
    app.collectionSelect.value = 'team'; app.collectionSelect.handlers.change();
    assert.equal(app.teamTab.attributes['aria-pressed'], 'true');
    assert.equal(app.requests.length, 2);
    app.requests[1].respond({channels: [], cursor: '', team_live: true}); await flush();
    app.viewport.innerWidth = 1000; app.windowHandlers.resize();
    assert.equal(app.collectionSelect.value, 'team');
    app.developerTab.handlers.click();
    assert.equal(app.collectionSelect.value, 'developer');
    app.search.handlers.reset({preventDefault() {}});
    assert.equal(app.collectionSelect.value, 'browse');
    const count = app.requests.length;
    app.collectionSelect.value = 'favorites'; app.collectionSelect.handlers.change();
    assert.equal(app.requests.length, count, 'Hidden collections cannot be selected');
    assert.equal(app.collectionSelect.value, 'browse');
});

test('mobile title and actions share the same grid row and the full title never shrinks', () => {
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    const mobile = styles.split(/@media \(max-width: 750px\) \{\r?\n    \.raid-browser-search-heading/)[1].split(/\r?\n\}/)[0];
    assert.match(styles, /\.raid-browser-heading-group h3 \{ flex: 0 0 auto;[^}]*white-space: nowrap/);
    assert.match(mobile, /\.raid-browser-dialog\[open\] \{ display: grid;[^}]*grid-template-rows: max-content minmax\(0,1fr\);/);
    assert.match(mobile, /\.raid-browser-dialog > \.raid-browser-header \{ grid-column: 2; grid-row: 1; flex-wrap: nowrap/);
    assert.match(mobile, /\.raid-browser-dialog \.raid-browser-results-toolbar \{ grid-column: 1; grid-row: 1/);
    assert.match(mobile, /\.raid-browser-tab-scroll, \.raid-browser-results-toolbar \.raid-browser-result-controls \{ display: none/);
    assert.match(mobile, /\.raid-browser-collection-select \{ display: block/);
});

test('wide toolbar shares a header row with Reset and results sit directly below', () => {
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    const layout = styles.slice(styles.indexOf('@media (min-width: 751px) {', styles.indexOf('.raid-browser-body {'))).split('\n}')[0];
    assert.match(layout, /grid-template-rows: max-content minmax\(0,1fr\);/);
    assert.match(layout, /grid-template-columns: minmax\(0,1fr\) min\(320px, 28vw\)/);
    assert.match(layout, /column-gap: 16px/);
    assert.match(styles, /\.raid-browser-body \{[^}]*grid-template-columns: minmax\(0,1fr\) min\(320px, 28vw\)/);
    assert.match(styles, /\.raid-browser-filters \{[^}]*min-width: 0/);
    assert.match(styles, /\.raid-browser-dialog > \.raid-browser-header \{[^}]*flex-wrap: nowrap;[^}]*gap: clamp/);
    // Match the filter fields' 20px inset plus their 1px left border at every width.
    assert.match(styles, /\.raid-browser-search-heading \{[^}]*padding-left: 21px;[^}]*white-space: nowrap/);
    assert.match(styles, /\.raid-browser-dialog > \.raid-browser-header > :is\(\.raid-browser-manage-lists, \.raid-browser-close\) \{[^}]*flex: 0 0 38px/);
    assert.match(layout, /\.raid-browser-dialog \.raid-browser-collection \{ display: contents/);
    assert.match(layout, /\.raid-browser-dialog \.raid-browser-results-toolbar \{ grid-column: 1; grid-row: 1/);
    assert.match(layout, /\.raid-browser-dialog \.raid-browser-results-shell \{ grid-column: 1; grid-row: 2/);
    assert.match(layout, /\.raid-browser-dialog > \.raid-browser-header \{ grid-column: 2; grid-row: 1/);
    assert.match(layout, /\.raid-browser-dialog > \.raid-browser-header \{[^}]*align-self: start/);
    assert.match(layout, /\.raid-browser-dialog \.raid-browser-results-toolbar \{[^}]*margin-top: -4px/);
    assert.match(layout, /\.raid-browser-tabs \{ align-self: stretch; align-items: stretch/);
    assert.ok(!layout.includes('margin-block: 0'));
    assert.match(layout, /\.raid-browser-dialog \.raid-browser-filters \{ grid-column: 2; grid-row: 2/);
    assert.match(layout, /\.raid-browser-dialog \.raid-browser-filters \{[^}]*margin-top: 10px/);
});

test('solid selected tab connects to the results background without a gradient or gap', () => {
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    const rule = styles.split('.raid-browser-heading-group .raid-browser-tabs button {')[1].split('}')[0];
    assert.match(rule, /margin-bottom: -1px/);
    assert.match(rule, /height: 38px/);
    assert.match(rule, /padding: 0 clamp\(6px, calc\(\(100cqi - 480px\) \/ 20\), 12px\)/);
    assert.match(styles, /\.raid-browser-dialog \.raid-browser-heading-group \{ align-items: center; \}/);
    assert.match(styles, /\.raid-browser-results-toolbar \{[^}]*align-items: center/);
    assert.match(rule, /border-radius: 12px/);
    assert.match(styles, /\.raid-browser-heading-group \.raid-browser-tabs.has-tab-indicator::before \{[^}]*border-radius: 12px 12px 0 0/);
    assert.match(styles, /\.raid-browser-heading-group \.raid-browser-tabs.has-tab-indicator::after \{[^}]*radial-gradient\(circle at left top/);
    assert.match(styles, /radial-gradient\(circle at right top/);
    const active = styles.split('.raid-browser-heading-group .raid-browser-tabs button[aria-pressed="true"] {')[1].split('}')[0];
    assert.match(active, /background: var\(--raid-collection-background\)/);
    assert.match(active, /border-bottom-color: var\(--raid-collection-background\)/);
    assert.ok(!styles.includes('mask-image: linear-gradient(to bottom, black 35%, transparent)'));
    assert.match(styles, /\.raid-browser-results-toolbar \{[^}]*margin-bottom: 0/);
    assert.match(styles, /\.raid-browser-results-shell \{[^}]*margin-top: var\(--raid-tab-gap\); padding: 10px/);
    assert.match(styles, /\.raid-browser-filters \{[^}]*padding: 10px 4px 10px 20px;/);
    assert.match(styles, /height: calc\(var\(--raid-tab-height\) \+ var\(--raid-tab-gap\)\)/);
    assert.match(styles, /top: calc\(var\(--raid-tab-height\) \+ var\(--raid-tab-gap\) - 12px\)/);
    assert.match(styles, /\[data-raid-collection-tabs\] \{ --raid-tab-gap: 4px;[^}]*transform: translateY\(6px\)/);
    assert.ok(!styles.includes('--raid-tab-background'));
    assert.ok(!fs.readFileSync('web/templates/channel/dashboard.html', 'utf8').includes('raid-browser-tab-content'));
    assert.match(rule, /border-bottom-color: transparent/);
    assert.ok(!styles.includes('.raid-browser-heading-group .raid-browser-tabs button[aria-pressed="true"]::after'));
});
const channel = (id = '2') => ({id, login: 'viewer' + id, display_name: 'Viewer' + id,
    title: '<unsafe title>', category: 'Retro', viewers: 42,
    thumbnail_url: 'https://static-cdn.jtvnw.net/test.jpg'});

test('tab swaps retain existing results while loading and animate only shared channel IDs', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel('2'), channel('3')], cursor: '', team_live: true});
    await flush();
    const previous = app.grid().children[1];
    previous.getBoundingClientRect = () => ({left: 220, top: 20, right: 480, bottom: 300});
    app.teamTab.handlers.click();
    assert.equal(app.grid().children[1], previous);
    app.requests[1].respond({channels: [channel('3'), channel('4')], cursor: '', team_live: true});
    await flush();
    const shared = app.grid().children.find(card => card.dataset.channelId === '3');
    const added = app.grid().children.find(card => card.dataset.channelId === '4');
    assert.equal(shared.animations.length, 1);
    assert.equal(shared.animations[0].frames[0].transform, 'translate(200px, 0px)');
    assert.equal(shared.animations[0].options.duration, 260);
    assert.ok(!added.animations);
});

test('card hover labels use short names rather than explanations or ranking reasons', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [{...channel(), followed: true, mutual: true,
        reasons: ['Same category', 'Shared tags'], verified: true}], cursor: ''});
    await flush();
    const card = app.grid().children[0];
    assert.equal(card.querySelector('.raid-browser-name').title, 'Viewer2');
    assert.equal(card.querySelector('.raid-browser-pin').title, 'Favorite');
    assert.equal(card.querySelector('.raid-browser-more').title, 'Options');
    assert.equal(card.querySelector('.raid-browser-start-raid').title, 'Raid');
    assert.equal(card.querySelector('.raid-browser-verified').title, 'Verified');
});

test('console match toggle shows per-card score breakdowns without fetching or changing ranking', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [{...channel(), relevance: 480,
        match_breakdown: {'Following': 400, 'Mutual following': 80}}], cursor: ''});
    await flush();
    const card = app.grid().children[0];
    const info = card.querySelector('.raid-browser-match-debug');
    assert.equal(info.textContent, 'Match score: 480\nFollowing: +400\nMutual following: +80');
    assert.ok(!app.dialog.classes.has('show-match-values'));
    assert.equal(app.viewport.dashboardRaidDebug.matches(), true);
    assert.ok(app.dialog.classes.has('show-match-values'));
    assert.equal(app.viewport.dashboardRaidDebug.matches(false), false);
    assert.ok(!app.dialog.classes.has('show-match-values'));
    assert.equal(app.grid().children[0], card);
    assert.equal(app.requests.length, 1);
});

test('channel preview layers over browsing and Back restores the same cards and scroll', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [{...channel(), title: '<full stream title>', description: 'Channel bio',
        tags: ['VTuber', 'Art'], language: 'en'}], cursor: ''}); await flush();
    const card = app.grid().children[0];
    const thumbnail = card.querySelector('.raid-browser-thumbnail'); thumbnail.isConnected = true;
    app.results.scrollTop = 120;
    thumbnail.handlers.click();
    assert.equal(app.previewDialog.open, true);
    assert.equal(app.location.hash, '#raidbrowser?channel=viewer2');
    assert.equal(app.dialog.open, true);
    assert.equal(app.results.scrollTop, 120);
    assert.equal(app.grid().children[0], card);
    const control = name => app.previewControls[`[data-raid-preview-${name}]`];
    const player = new URL(control('video').children[0].src);
    assert.equal(player.origin, 'https://player.twitch.tv');
    assert.equal(player.searchParams.get('channel'), 'viewer2');
    assert.equal(player.searchParams.get('parent'), 'localhost');
    assert.equal(player.searchParams.get('autoplay'), 'true');
    assert.equal(player.searchParams.get('muted'), 'true');
    assert.equal(control('video').children[0].allow, 'autoplay; fullscreen');
    const chat = control('chat').children[0];
    assert.equal(chat.channel.login, 'viewer2');
    assert.equal(chat.src, undefined);
    assert.equal(control('stream-title').textContent, '<full stream title>');
    assert.equal(control('description').textContent, 'Channel bio');
    assert.equal(control('tags').children.length, 2);
    control('back').handlers.click();
    assert.equal(app.previewDialog.open, false);
    assert.equal(app.location.hash, '#raidbrowser');
    assert.equal(app.dialog.open, true);
    assert.equal(control('video').children.length, 0);
    assert.equal(control('chat').children.length, 0);
    assert.equal(chat.destroyed, true);
    assert.equal(thumbnail.focused, true);
    assert.equal(app.requests.length, 1);
});

test('compact preview stacks video, details and chat without a stretched video row or pane tabs', async () => {
    const app = setup(new Map(), '1', '', 390); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel()], cursor: ''}); await flush();
    const thumbnail = app.grid().children[0].querySelector('.raid-browser-thumbnail');
    thumbnail.handlers.click();
    const body = app.previewControls['[data-raid-preview-body]'];
    const player = app.previewControls['[data-raid-preview-video]'].children[0];
    assert.equal(body.dataset.pane, undefined);
    assert.equal(app.previewControls['[data-raid-preview-video]'].children[0], player);
    assert.equal(app.requests.length, 1);
    app.previewDialog.close(); thumbnail.handlers.click();
    assert.equal(body.dataset.pane, undefined);
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.match(styles, /\.raid-preview-main \{ display: flex; flex-direction: column;[^}]*overflow: auto/);
    assert.match(styles, /\.raid-preview-body \{[^}]*overflow: hidden/);
    assert.ok(!styles.includes('.raid-preview-body { display: block; overflow: auto; }'));
    assert.match(styles, /\.raid-preview-body \{ grid-template-columns: minmax\(0,1fr\); grid-template-rows: minmax\(440px,3fr\) minmax\(160px,1\.75fr\); gap: 8px; overflow: auto;/);
    assert.match(styles, /\.raid-preview-video \{ width: min\(100%, max\(400px, calc\(300px \* 16 \/ 9\)\)\); align-self: start;/);
    assert.match(styles, /\.raid-preview-video \{[^}]*min-width: 400px; min-height: 300px;/);
    assert.ok(!styles.includes('.raid-preview-video-stats'));
    assert.match(styles, /\.raid-preview-details-upper \{ display: block; flex: 1; min-height: 0; overflow-y: auto;/);
    assert.match(styles, /\.raid-preview-chat \{ height: auto; min-height: 0; margin-top: 0;/);
    assert.match(styles, /\.raid-preview-chat \{ display: flex; flex-direction: column; align-self: stretch; height: auto;/);
    assert.match(styles, /\.raid-preview-chat \{ height: auto;[^}]*align-self: stretch;/);
    assert.ok(!fs.readFileSync('web/templates/channel/dashboard.html', 'utf8').includes('data-raid-preview-pane='));
});

test('preview width follows available 16:9 video height without recreating the player', async () => {
    const app = setup(new Map(), '1', '', 2000);
    app.previewDialog.getBoundingClientRect = () => ({left: 100, right: 1500, top: 20, bottom: 900});
    app.previewControls['[data-raid-preview-main]'].clientWidth = 1000;
    app.previewControls['[data-raid-preview-main]'].clientHeight = 700;
    app.previewControls['[data-raid-preview-details]'].getBoundingClientRect = () => ({top: 0, bottom: 250});
    app.previewControls['[data-raid-preview-footer]'].getBoundingClientRect = () => ({top: 0, bottom: 50});
    app.opener.handlers.click();
    app.requests[0].respond({channels: [channel()], cursor: ''}); await flush();
    app.grid().children[0].querySelector('.raid-browser-thumbnail').handlers.click();
    assert.equal(app.previewDialog.style['--raid-preview-width'], '1200px');
    const player = app.previewControls['[data-raid-preview-video]'].children[0];
    app.previewControls['[data-raid-preview-main]'].clientHeight = 600;
    app.resizePreview(); await flush();
    assert.equal(app.previewDialog.style['--raid-preview-width'], '1022px');
    assert.equal(app.previewControls['[data-raid-preview-video]'].children[0], player);
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.match(styles, /\.raid-preview-video \{[^}]*height: auto;[^}]*aspect-ratio: 16 \/ 9; align-self: start/);
    const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
    assert.match(template, /class="raid-preview-video" data-raid-preview-video/);
    assert.ok(!template.includes('raid-preview-video dashboard-video-frame'));
    assert.match(styles, /\.raid-preview-tags \{[^}]*flex-wrap: wrap;/);
    assert.match(styles, /\.raid-preview-tags span \{[^}]*max-width: 100%; white-space: normal;/);
    assert.match(styles, /\.raid-preview-details-copy \{[^}]*overflow-y: auto;/);
    assert.match(styles, /\.raid-preview-description \{ display: block; white-space: pre-wrap; overflow-wrap: anywhere; \}/);
    assert.ok(!styles.includes('.raid-preview-description { display: none; }'));
});

test('widening the window recalculates a constrained preview even when its observed dimensions have not changed', async () => {
    const app = setup(new Map(), '1', '', 1000);
    app.previewDialog.getBoundingClientRect = () => ({left: 0, right: 800, top: 20, bottom: 900});
    app.previewControls['[data-raid-preview-main]'].clientWidth = 400;
    app.previewControls['[data-raid-preview-main]'].clientHeight = 700;
    app.previewControls['[data-raid-preview-details]'].getBoundingClientRect = () => ({top: 0, bottom: 250});
    app.opener.handlers.click(); app.requests[0].respond({channels: [channel()], cursor: ''}); await flush();
    app.grid().children[0].querySelector('.raid-browser-thumbnail').handlers.click();
    const player = app.previewControls['[data-raid-preview-video]'].children[0];
    assert.equal(app.previewDialog.style['--raid-preview-width'], '952px');
    app.viewport.innerWidth = 390; app.windowHandlers.resize(); await flush();
    app.viewport.innerWidth = 2000; app.windowHandlers.resize(); await flush();
    assert.equal(app.previewDialog.style['--raid-preview-width'], '1200px');
    assert.equal(app.previewControls['[data-raid-preview-video]'].children[0], player);
    assert.equal(app.requests.length, 1);
});

test('expanded cards include badges, special tags, viewers, follower count and live uptime', async () => {
    const app = setup(); app.previewDialog.dataset.detailsUrl = '/channel/api/raid-browser/preview';
    app.opener.handlers.click();
    app.requests[0].respond({channels: [{...channel(), verified: true, language: 'ja', followed: true, mutual: true,
        tags: ['VTuber'], suggested: true, dev_priority: true, recent_raider: true,
        events: ['Drops Enabled'], teams: ['Team name'], started_at: new Date(Date.now() - 3_600_000).toISOString()}], cursor: ''});
    await flush();
    app.grid().children[0].querySelector('.raid-browser-thumbnail').handlers.click();
    const identity = app.previewControls['[data-raid-preview-identity]'];
    assert.ok(identity.querySelector('.raid-browser-verified'));
    assert.ok(identity.querySelector('.raid-browser-language'));
    assert.ok(identity.querySelector('.raid-browser-follow-badge'));
    assert.equal(identity.querySelector('.raid-preview-marker'), undefined);
    const nameIndex = identity.children.findIndex(child => child.tagName === 'a');
    assert.ok(identity.children.indexOf(identity.querySelector('.raid-browser-language')) < nameIndex);
    assert.ok(identity.children.indexOf(identity.querySelector('.raid-browser-follow-badge')) < nameIndex);
    assert.ok(identity.children.indexOf(identity.querySelector('.raid-preview-followers')) > nameIndex);
    const badges = app.previewControls['[data-raid-preview-badges]'];
    const video = app.previewControls['[data-raid-preview-video]'];
    assert.equal(badges.querySelector('.raid-preview-viewers').textContent, '42 viewers');
    assert.match(badges.querySelector('.raid-preview-live-time').textContent, /^1:00:/);
    assert.equal(video.querySelector('.raid-preview-live-time'), undefined);
    assert.equal(video.querySelector('.raid-preview-viewers'), undefined);
    const events = app.previewControls['[data-raid-preview-events]'];
    assert.ok(events.children.some(badge => badge.textContent === 'Drops Enabled'));
    assert.ok(!badges.children.some(badge => badge.textContent === 'Drops Enabled'));
    assert.ok(app.previewControls['[data-raid-preview-teams]'].children.some(badge => badge.textContent === 'Team name'));
    assert.ok(!badges.children.some(badge => badge.textContent === 'Team name'));
    assert.equal(app.requests[1].url.pathname, '/channel/api/raid-browser/preview');
    assert.equal(app.requests[1].url.searchParams.get('target_id'), '2');
    app.requests[1].respond({follower_count: 1234}); await flush();
    assert.equal(identity.querySelector('.raid-preview-followers').textContent, '1,234 followers');
    const tags = app.previewControls['[data-raid-preview-tags]'].children.map(tag => tag.textContent);
    assert.ok(tags.includes('Developer') && tags.includes('Suggested') && tags.includes('Raided you recently'));
    assert.equal(app.previewControls['[data-raid-preview-status]'].textContent, '');
    const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
    const left = template.split('<section class="raid-preview-main"')[1].split('</section>')[0];
    assert.ok(left.includes('data-raid-preview-raid'));
    assert.ok(left.indexOf('data-raid-preview-raid') > left.indexOf('data-raid-preview-description'));
    const actions = left.split('<div class="raid-preview-details-actions">')[1].split('<div class="raid-preview-details-copy">')[0];
    assert.ok(!actions.includes('data-raid-preview-events'));
    assert.ok(!actions.includes('data-raid-preview-teams'));
    assert.ok(actions.includes('data-raid-preview-badges'));
    assert.ok(!actions.includes('data-raid-preview-favorite') && !actions.includes('data-raid-preview-menu'));
    const header = template.split('<header class="raid-preview-header">')[1].split('</header>')[0];
    assert.match(header, /data-raid-preview-back[^>]*><svg[^>]*aria-hidden="true"[^>]*><path d="M19 12H5m6-6-6 6 6 6"/);
    assert.ok(header.indexOf('data-raid-preview-events') < header.indexOf('data-raid-preview-teams'));
    assert.ok(header.indexOf('data-raid-preview-teams') < header.indexOf('data-raid-preview-favorite'));
    assert.ok(header.indexOf('data-raid-preview-favorite') < header.indexOf('data-raid-preview-menu'));
    assert.ok(header.indexOf('data-raid-preview-menu') < header.indexOf('data-raid-preview-close'));
    assert.ok(!header.includes('data-raid-preview-badges'));
    assert.ok(left.includes('data-raid-preview-badges'));
    const footer = left.split('<footer class="raid-preview-footer"')[1].split('</footer>')[0];
    assert.ok(footer.includes('data-raid-preview-raid'));
    assert.ok(footer.includes('data-raid-preview-description'));
    assert.ok(footer.includes('class="raid-preview-footer-copy"'));
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.match(header, /class="raid-preview-header-labels" tabindex="0" role="region"/);
    assert.match(styles, /\.raid-preview-header-labels \{[^}]*min-width: 0;[^}]*max-width: 45%;[^}]*overflow-x: auto; overflow-y: hidden;/);
    assert.match(styles, /\.raid-preview-header-labels :is\(\.raid-preview-events, \.raid-preview-teams\) \{ flex: 0 0 auto; flex-wrap: nowrap; \}/);
    assert.match(styles, /@media \(min-width: 751px\) \{\s*\.raid-preview-main \{ position: relative; \}\s*\.raid-preview-footer \{ min-height: 44px; padding-right: 84px; \}\s*\.raid-preview-footer > \[data-raid-preview-raid\] \{ position: absolute; right: 12px; bottom: 12px;/);
    assert.ok(!footer.includes('data-raid-preview-favorite'));
    assert.match(left, /<\/footer>\s*<\/div>\s*$/);
});

test('preview favorite and blacklist controls share the original card actions', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel()], cursor: ''}); await flush();
    const card = app.grid().children[0]; card.querySelector('.raid-browser-thumbnail').handlers.click();
    card.querySelector('.raid-browser-channel-menu').querySelector('button').click = () => {
        throw new Error('Preview must not click controls behind the active dialog');
    };
    app.previewControls['[data-raid-preview-favorite]'].handlers.click();
    assert.equal(card.querySelector('.raid-browser-pin').attributes['aria-pressed'], 'true');
    const favorite = app.previewControls['[data-raid-preview-favorite]'];
    assert.equal(favorite.title, 'Unfavorite');
    assert.equal(favorite.attributes['aria-label'], 'Unfavorite');
    assert.equal(favorite.attributes['aria-pressed'], 'true');
    assert.equal(favorite.innerHTML, card.querySelector('.raid-browser-pin').innerHTML);
    assert.match(favorite.innerHTML, /<svg/);
    assert.match(favorite.innerHTML, /m12 2 3\.09 6\.26L22 9\.27/);
    app.confirm(false); app.previewControls['[data-raid-preview-block]'].handlers.click();
    assert.equal(app.previewDialog.open, true);
    app.confirm(true); app.previewControls['[data-raid-preview-block]'].handlers.click();
    assert.equal(app.previewDialog.open, false);
    assert.equal(app.grid().children.length, 0);
    assert.deepEqual(JSON.parse(app.storage.get('ratsboombot:raid-blacklist:1')), ['2']);
});

test('preview follower lookups abort on close and stale counts cannot replace a newer channel', async () => {
    const app = setup(); app.previewDialog.dataset.detailsUrl = '/channel/api/raid-browser/preview';
    app.opener.handlers.click();
    app.requests[0].respond({channels: [channel('2'), channel('3')], cursor: ''}); await flush();
    app.grid().children[0].querySelector('.raid-browser-thumbnail').handlers.click();
    app.previewDialog.close(); assert.equal(app.requests[1].options.signal.aborted, true);
    app.grid().children[1].querySelector('.raid-browser-thumbnail').handlers.click();
    app.requests[2].respond({follower_count: 0}); await flush();
    app.requests[1].respond({follower_count: 999}); await flush();
    assert.equal(app.previewControls['[data-raid-preview-identity]'].querySelector('.raid-preview-followers').textContent, '0 followers');
});

test('preview backdrop needs both press and release outside and parent close unloads frames', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel()], cursor: ''}); await flush();
    const open = () => app.grid().children[0].querySelector('.raid-browser-thumbnail').handlers.click();
    open();
    app.previewDialog.handlers.pointerdown({target: new Element(), clientX: 10, clientY: 10});
    app.previewDialog.handlers.click({target: app.previewDialog, clientX: 10, clientY: 10});
    assert.equal(app.previewDialog.open, true);
    app.previewDialog.handlers.pointerdown({target: app.previewDialog, clientX: 10, clientY: 10});
    app.previewDialog.handlers.click({target: app.previewDialog, clientX: 10, clientY: 10});
    assert.equal(app.previewDialog.open, false);
    assert.equal(app.dialog.open, true);
    open(); app.close.handlers.click();
    assert.equal(app.previewDialog.open, false);
    assert.equal(app.previewControls['[data-raid-preview-video]'].children.length, 0);
});

test('preview helper path does not create an unused fallback iframe', async () => {
    const app = setup(); let starts = 0;
    app.viewport.createRaidPreviewPlayer = () => { starts++; return {destroy() {}}; };
    app.opener.handlers.click(); app.requests[0].respond({channels: [channel()], cursor: ''}); await flush();
    app.grid().children[0].querySelector('.raid-browser-thumbnail').handlers.click();
    assert.equal(starts, 1);
    assert.equal(app.createdElements.filter(element => element.tagName === 'iframe').length, 0);
});

test('uptime refresh skips unchanged DOM writes while still updating elapsed time', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [{...channel(), started_at: new Date(Date.now() + 600000).toISOString()}], cursor: ''}); await flush();
    const timer = app.grid().children[0].querySelector('.raid-browser-live-time');
    const setAttribute = timer.setAttribute.bind(timer); let writes = 0;
    timer.setAttribute = (...args) => { writes++; setAttribute(...args); };
    app.tick(); app.tick(); assert.equal(writes, 0); assert.equal(timer.textContent, '0:00:00');
    timer.dataset.startedAt = String(Date.now() - 3000); app.tick();
    assert.equal(writes, 1); assert.equal(timer.textContent, '0:00:03');
    assert.equal(timer.attributes['aria-label'], 'Live for 0:00:03');
});

test('preview counters stay outside the video instead of overlaying the Twitch iframe', () => {
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.ok(!styles.includes('.raid-preview-video-stats'));
    assert.ok(!source.includes('videoStats'));
    assert.match(source, /viewers\.textContent[^\n]*badges\.append\(viewers\)/);
    assert.match(source, /timer\.dataset\.startedAt[^\n]*badges\.append\(timer\)/);
    assert.match(styles, /\.raid-preview-badges \{ display: flex; flex-wrap: wrap;/);
});

test('preview raid reuses the confirmed action and closes both overlays only on success', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel()], cursor: ''}); await flush();
    app.grid().children[0].querySelector('.raid-browser-thumbnail').handlers.click();
    const raid = app.previewControls['[data-raid-preview-raid]'];
    app.previewControls['[data-raid-preview-main]'].getBoundingClientRect = () => ({left: 40, top: 60, width: 900, height: 700});
    app.confirm(false); raid.handlers.click();
    assert.equal(app.requests.length, 1);
    app.confirm(true); raid.handlers.click();
    assert.equal(raid.disabled, true);
    app.requests[1].respond({detail: 'Not allowed'}, false); await flush();
    assert.equal(app.previewDialog.open, true);
    assert.equal(app.previewControls['[data-raid-preview-status]'].textContent, 'Not allowed');
    assert.equal(raid.disabled, false);
    raid.handlers.click();
    app.requests[2].respond({raid: {target_id: '2', target_login: 'viewer2'}}); await flush();
    assert.equal(app.previewDialog.open, false);
    assert.equal(app.dialog.open, false);
    assert.equal(app.events.filter(event => event.type === 'dashboard-raid-started').length, 1);
    assert.equal(app.events.find(event => event.type === 'dashboard-raid-started').detail.sourceRect.width, 900);
});

test('thumbnail subtly expands on hover and focus without changing layout, respecting reduced motion', () => {
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.match(styles, /\.raid-browser-thumbnail \{ transition: transform \.18s ease; transform-origin: center; \}/);
    assert.match(styles, /\.raid-browser-thumbnail:hover \{ transform: scale\(1\.02\); \}/);
    assert.match(styles, /\.raid-browser-thumbnail:focus-visible \{ transform: scale\(1\.02\); \}/);
    assert.match(styles, /\.raid-browser-thumbnail:is\(:hover, :focus-visible\) \{ transform: none; \}/);
});

test('only the thumbnail opens preview, not the surrounding card', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel()], cursor: ''}); await flush();
    const card = app.grid().children[0];
    assert.equal(card.handlers.click, undefined);
    assert.ok(!app.previewDialog.open);
    assert.equal(card.querySelector('.raid-browser-thumbnail').title, undefined);
    card.querySelector('.raid-browser-thumbnail').handlers.click();
    assert.equal(app.previewDialog.open, true);
});

test('reduced motion skips shared-card movement and rapid tab changes ignore stale results', async () => {
    const app = setup(); app.viewport.matchMedia = () => ({matches: true});
    app.opener.handlers.click();
    app.requests[0].respond({channels: [channel('2')], cursor: '', team_live: true, developers_live: true});
    await flush();
    app.teamTab.handlers.click();
    app.developerTab.handlers.click();
    app.requests[2].respond({channels: [Object.assign(channel('2'), {dev_priority: true})], cursor: '', developers_live: true});
    await flush();
    app.requests[1].respond({channels: [channel('3')], cursor: '', team_live: true});
    await flush();
    assert.equal(app.grid().children.length, 1);
    assert.equal(app.grid().children[0].dataset.channelId, '2');
    assert.ok(!app.grid().children[0].animations);
});

test('tag limit warning appears only at the limit and clears after editing or adding', async () => {
    const app = setup();
    app.opener.handlers.click();
    assert.equal(app.tagLimit.hidden, true);
    app.tagSearch.value = 'x'.repeat(24);
    app.search.handlers.input({target: app.tagSearch});
    assert.equal(app.tagLimit.hidden, true);
    app.tagSearch.value += 'x';
    app.search.handlers.input({target: app.tagSearch});
    assert.equal(app.tagLimit.hidden, false);
    app.tagSearch.value = 'short';
    app.search.handlers.input({target: app.tagSearch});
    assert.equal(app.tagLimit.hidden, true);
    app.tagSearch.value = 'x'.repeat(25);
    app.search.handlers.input({target: app.tagSearch});
    app.tagSearch.handlers.keydown({key: 'Enter', preventDefault() {}});
    assert.equal(app.tagSearch.value, '');
    assert.equal(app.tagLimit.hidden, true);
    const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
    assert.ok(!template.includes('Type any tag and press Enter'));
    assert.match(template, /data-raid-tag-limit role="status" hidden>Maximum 25 characters/);
    assert.match(template, /class="raid-browser-tag-input-row"/);
    assert.match(template, /class="queue-state-toggle live"[^>]*data-raid-tag-match[^>]*><span class="queue-state-current">All<\/span><span class="queue-state-alternate" aria-hidden="true">Any<\/span>/);
});

test('reset explicitly clears every filter and collection without deleting saved lists', async () => {
    const storage = new Map([['ratsboombot:raid-favorites:1', '["2"]'], ['ratsboombot:raid-blacklist:1', '["3"]']]);
    const app = setup(storage); app.opener.handlers.click();
    app.requests[0].respond({channels: [], cursor: ''}); await flush();
    app.teamTab.handlers.click();
    app.input.value = 'streamer'; app.categorySearch.value = 'Retro'; app.tagSearch.value = 'x'.repeat(25);
    for (const name of ['category_id','tags','language','event','sort','tag_match']) app.fields[name].value = 'selected';
    app.fields.follow_status.value = 'mutual';
    app.fields.follow_status.disabled = true;
    let prevented = false;
    app.search.handlers.reset({preventDefault() { prevented = true; }});
    assert.equal(prevented, true);
    assert.equal(app.input.value, ''); assert.equal(app.categorySearch.value, ''); assert.equal(app.tagSearch.value, '');
    for (const name of ['category_id','tags','language','event']) assert.equal(app.fields[name].value, '');
    assert.equal(app.fields.sort.value, 'for_you'); assert.equal(app.fields.tag_match.value, 'all');
    assert.equal(app.tagMatchToggle.querySelector('.queue-state-current').textContent, 'All');
    assert.equal(app.tagMatchToggle.attributes['aria-pressed'], 'true');
    assert.equal(app.fields.follow_status.value, '');
    assert.equal(app.fields.follow_status.disabled, false);
    assert.equal(app.browseTab.attributes['aria-pressed'], 'true');
    assert.equal(app.teamTab.attributes['aria-pressed'], 'false');
    assert.equal(app.tagLimit.hidden, true); assert.equal(app.selectedTags.children.length, 0);
    const url = app.requests.at(-1).url;
    assert.equal(url.searchParams.get('sort'), 'for_you');
    assert.equal(url.searchParams.get('tag_match'), null);
    for (const key of ['query','tags','category_id','event','language','same_team','after','following','mutual']) assert.equal(url.searchParams.has(key), false);
    assert.equal(url.searchParams.get('favorites'), '2'); assert.equal(url.searchParams.get('blocked'), '3');
    assert.equal(storage.get('ratsboombot:raid-favorites:1'), '["2"]');
});

test('official fallback discloses fetched-only sorting and bounded search without an error', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel()], cursor: '', sort_scope: 'fetched', search_limited: true});
    await flush();
    assert.match(app.status.textContent, /Sorting applies to fetched channels/);
    assert.match(app.status.textContent, /500 streams/);
    assert.equal(app.status.classes.has('error'), false);
    assert.equal(app.requests.length, 1);
});

test('tag match toggle defaults to All and refreshes only when selected tags exist', async () => {
    const app = setup(); app.opener.handlers.click();
    assert.equal(app.requests[0].url.searchParams.get('tag_match'), null);
    assert.equal(app.tagMatchToggle.querySelector('.queue-state-current').textContent, 'All');
    app.requests[0].respond({channels: [], cursor: ''}); await flush();
    app.tagMatchToggle.handlers.click();
    assert.equal(app.fields.tag_match.value, 'any');
    assert.equal(app.tagMatchToggle.querySelector('.queue-state-current').textContent, 'Any');
    assert.equal(app.tagMatchToggle.querySelector('.queue-state-alternate').textContent, 'All');
    assert.equal(app.tagMatchToggle.classes.has('live'), false);
    assert.equal(app.tagMatchToggle.attributes['aria-pressed'], 'false');
    assert.equal(app.requests.length, 1);
    app.fields.tags.value = 'VTuber';
    app.tagMatchToggle.handlers.click();
    assert.equal(app.fields.tag_match.value, 'all');
    assert.equal(app.tagMatchToggle.querySelector('.queue-state-current').textContent, 'All');
    assert.equal(app.tagMatchToggle.querySelector('.queue-state-alternate').textContent, 'Any');
    assert.equal(app.tagMatchToggle.classes.has('live'), true);
    assert.equal(app.requests[1].url.searchParams.get('tag_match'), 'all');
    app.tagMatchToggle.handlers.click();
    assert.equal(app.requests[2].url.searchParams.get('tag_match'), 'any');
});

test('tag matching mode changes refresh results and carry through lazy loading', async () => {
    const app = setup();
    app.opener.handlers.click();
    app.requests[0].respond({channels: [], cursor: ''});
    await flush();
    app.fields.tags.value = 'VTuber,Art';
    app.fields.tag_match.value = 'all';
    app.search.handlers.change({target: app.fields.tag_match});
    assert.equal(app.requests[1].url.searchParams.get('tag_match'), 'all');
    assert.equal(app.requests[1].url.searchParams.get('tags'), 'VTuber,Art');
    app.requests[1].respond({channels: [channel()], cursor: 'next'});
    await flush();
    assert.equal(app.requests[2].url.searchParams.get('tag_match'), 'all');
});

test('raidbrowser hash opens on page load and closes cleanly without losing query parameters', () => {
    const app = setup(new Map(), '1', '#raidbrowser');
    assert.equal(app.dialog.open, true);
    assert.equal(app.requests.length, 1);
    assert.equal(app.input.focused, true);
    app.close.handlers.click();
    assert.equal(app.location.hash, '');
    assert.equal(app.location.pathname, '/channel');
    assert.equal(app.location.search, '?test=1');
});

test('hash changes and browser history open or close the browser without duplicate loads', () => {
    const app = setup(new Map(), '1', '#unrelated');
    assert.equal(app.requests.length, 0);
    app.location.hash = '#raidbrowser'; app.windowHandlers.hashchange();
    assert.equal(app.dialog.open, true); assert.equal(app.requests.length, 1);
    app.windowHandlers.popstate();
    assert.equal(app.requests.length, 1);
    app.location.hash = '#unrelated'; app.windowHandlers.hashchange();
    assert.equal(app.dialog.open, false);
    assert.equal(app.location.hash, '#unrelated');
    app.opener.handlers.click();
    assert.equal(app.location.hash, '#raidbrowser');
    assert.equal(app.dialog.open, true);
});

test('channel URL restores a preview after refresh without replacing the browse filters', async () => {
    const app = setup(new Map(), '1', '#raidbrowser?channel=Viewer2');
    assert.equal(app.dialog.open, true); assert.equal(app.requests.length, 2);
    assert.equal(app.requests[1].url.searchParams.get('query'), 'viewer2');
    assert.equal(app.input.value, '');
    app.windowHandlers.popstate(); app.windowHandlers.hashchange();
    assert.equal(app.requests.length, 2, 'History events share the pending lookup');
    app.requests[0].respond({channels: [], cursor: ''});
    app.requests[1].respond({channels: [channel()], cursor: ''}); await flush();
    assert.equal(app.previewDialog.open, true);
    assert.equal(app.previewControls['[data-raid-preview-chat]'].children[0].channel.login, 'viewer2');
    assert.equal(app.location.hash, '#raidbrowser?channel=viewer2');
    app.close.handlers.click();
    assert.equal(app.previewDialog.open, false); assert.equal(app.location.hash, '');
    assert.equal(app.location.search, '?test=1');
});

test('Back and Forward switch between the browser and cached preview without extra requests', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel()], cursor: ''}); await flush();
    app.grid().children[0].querySelector('.raid-browser-thumbnail').handlers.click();
    app.location.hash = '#raidbrowser'; app.windowHandlers.popstate();
    assert.equal(app.previewDialog.open, false); assert.equal(app.dialog.open, true);
    app.location.hash = '#raidbrowser?channel=viewer2'; app.windowHandlers.popstate();
    assert.equal(app.previewDialog.open, true); assert.equal(app.requests.length, 1);
    app.windowHandlers.hashchange(); assert.equal(app.requests.length, 1);
});

test('channel URL ignores stale lookups and preserves unrelated navigation', async () => {
    const app = setup(new Map(), '1', '#raidbrowser?channel=viewer2');
    app.requests[0].respond({channels: [], cursor: ''}); await flush();
    app.location.hash = '#raidbrowser?channel=viewer3'; app.windowHandlers.hashchange();
    assert.equal(app.requests[1].options.signal.aborted, true);
    app.requests[2].respond({channels: [channel('3')], cursor: ''}); await flush();
    app.requests[1].respond({channels: [channel()], cursor: ''}); await flush();
    assert.equal(app.previewControls['[data-raid-preview-chat]'].children[0].channel.login, 'viewer3');
    app.location.hash = '#other'; app.windowHandlers.hashchange();
    assert.equal(app.previewDialog.open, false); assert.equal(app.dialog.open, false);
    assert.equal(app.location.hash, '#other');
});

test('offline channel URL stays in the browser and malformed names never trigger a channel lookup', async () => {
    const app = setup(new Map(), '1', '#raidbrowser?channel=viewer2');
    app.requests[0].respond({channels: [], cursor: ''});
    app.requests[1].respond({channels: [], cursor: ''}); await flush();
    assert.ok(!app.previewDialog.open); assert.match(app.status.textContent, /offline or unavailable/);
    assert.equal(setup(new Map(), '1', '#raidbrowser?channel=bad%2Fname').requests.length, 1);
});

test('matching selected tags come first and get purple emphasis in cards and rows', async () => {
    const app = setup();
    app.fields.tags.value = ' artist , VTUBER ';
    app.opener.handlers.click();
    app.requests[0].respond({channels: [Object.assign(channel(), {tags: ['English', 'vtuber', 'Cozy', 'Artist'], suggested: true})], cursor: ''});
    await flush();
    for (const list of [false, true]) {
        if (list) { app.listView.handlers.click(); await flush(); }
        const tags = app.grid().children[0].querySelector('.raid-browser-tags').children;
        assert.deepEqual(tags.map(tag => tag.textContent), ['vtuber', 'Artist', 'Suggested', 'English', 'Cozy']);
        assert.equal(tags[0].className, 'raid-browser-tag-matched');
        assert.equal(tags[1].className, 'raid-browser-tag-matched');
        assert.notEqual(tags[3].className, 'raid-browser-tag-matched');
    }
});

test('opening modal loads channels, focuses search, and restores focus on closing', async () => {
    const app = setup();
    app.opener.handlers.click();
    assert.equal(app.dialog.open, true);
    assert.equal(app.input.focused, true);
    assert.equal(app.requests[0].url.pathname, '/channel/api/raid-browser');
    app.requests[0].respond({channels: [channel()], cursor: ''});
    await flush();
    assert.equal(app.grid().children.length, 1);
    assert.equal(app.grid().children[0].querySelector('.raid-browser-stream-title').textContent, '<unsafe title>');
    app.close.handlers.click();
    assert.equal(app.dialog.open, false);
    assert.equal(app.opener.focused, true);
    assert.equal(app.root.classes.has('raid-browser-open'), false);
});

test('search aborts old results, resets scroll, and uses current query', async () => {
    const app = setup(); app.opener.handlers.click();
    app.results.scrollTop = 100;
    app.input.value = 'Retro';
    app.search.handlers.submit({preventDefault() {}});
    assert.equal(app.requests[0].options.signal.aborted, true);
    assert.equal(app.results.scrollTop, 0);
    assert.equal(app.requests[1].url.searchParams.get('query'), 'Retro');
    app.requests[1].respond({channels: [channel('3')], cursor: ''});
    app.requests[0].respond({channels: [channel('2')], cursor: ''});
    await flush();
    assert.equal(app.grid().children.length, 1);
    assert.match(app.grid().children[0].querySelector('.raid-browser-name').textContent, /Viewer3/);
});

test('lazy loading appends channels without duplicates or resetting scroll', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: Array.from({length: 20}, (_, index) => channel(String(index + 2))), cursor: 'next'});
    await flush();
    assert.equal(app.requests.length, 1);
    const total = parseFloat(app.results.children[0].style.height);
    app.results.scrollTop = total - app.results.clientHeight;
    const previousScroll = app.results.scrollTop;
    app.results.handlers.scroll(); await flush();
    assert.equal(app.requests[1].url.searchParams.get('after'), 'next');
    app.results.handlers.scroll(); await flush();
    assert.equal(app.requests.length, 2);
    app.requests[1].respond({channels: [channel('21'), channel('22')], cursor: ''});
    await flush();
    assert.equal(app.status.textContent, '');
    assert.equal(app.results.scrollTop, previousScroll);
});

for (const mobile of [false, true]) test(`lazy loading restores the visible channel after expanding the scroll range (${mobile ? 'mobile' : 'desktop'})`, async () => {
    const app = setup(new Map(), '1', '', mobile ? 390 : 1280); app.opener.handlers.click();
    app.requests[0].respond({channels: Array.from({length: 20}, (_, index) => channel(String(index + 2))), cursor: 'next'});
    await flush();
    const spacer = app.results.children[0];
    let position = 0;
    // A real scroll container clamps writes to its current content height.
    Object.defineProperty(app.results, 'scrollTop', {
        get: () => position,
        set: value => { position = Math.max(0, Math.min(value, parseFloat(spacer.style.height) - app.results.clientHeight)); },
    });
    const stride = parseFloat(app.grid().style.gridAutoRows) + 12;
    const columns = mobile ? 1 : 2;
    app.results.scrollTop = parseFloat(spacer.style.height) - app.results.clientHeight - 31;
    const before = app.results.scrollTop;
    const anchorIndex = Math.floor(before / stride) * columns;
    app.results.handlers.scroll(); await flush();
    const anchor = app.grid().children.find(card => Number(card.dataset.channelIndex) === anchorIndex).dataset.channelId;
    // The user can keep scrolling while a request is in flight.
    app.results.scrollTop = before + 7;
    app.requests[1].respond({channels: Array.from({length: 20}, (_, index) => ({...channel(String(index + 100)), relevance: 1000})), cursor: ''});
    await flush();
    assert.equal(app.results.scrollTop, before + 7 + (20 / columns) * stride);
    const sameChannel = app.grid().children.find(card => card.dataset.channelId === anchor);
    assert.equal(Number(sameChannel.dataset.channelIndex), anchorIndex + 20);
    assert.equal(app.results.scrollTop % stride, (before + 7) % stride);
});

test('closing aborts requests and late results cannot repopulate the popup', async () => {
    const app = setup(); app.opener.handlers.click();
    app.dialog.close();
    assert.equal(app.requests[0].options.signal.aborted, true);
    app.requests[0].respond({channels: [channel()], cursor: ''});
    await flush();
    assert.equal(app.grid().children.length, 0);
});

for (const name of ['dialog', 'manager']) test(`${name} dismisses only when both press and release occur on the backdrop`, () => {
    const app = setup(); app.opener.handlers.click();
    if (name === 'manager') app.manageButton.handlers.click();
    const popup = app[name];
    const inside = {target: popup, clientX: 40, clientY: 40, button: 0};
    const outside = {target: popup, clientX: 0, clientY: 0, button: 0};
    popup.handlers.click(outside);
    assert.equal(popup.open, true, 'release without outside press stays open');
    popup.handlers.pointerdown(inside); popup.handlers.click(outside);
    assert.equal(popup.open, true, 'drag from inside to outside stays open');
    popup.handlers.pointerdown(outside); popup.handlers.click(inside);
    assert.equal(popup.open, true, 'drag from outside to inside stays open');
    popup.handlers.pointerdown(outside); popup.handlers.pointercancel(); popup.handlers.click(outside);
    assert.equal(popup.open, true, 'cancelled gesture stays open');
    popup.handlers.pointerdown({...outside, button: 2}); popup.handlers.click(outside);
    assert.equal(popup.open, true, 'right click stays open');
    popup.handlers.pointerdown(outside); popup.handlers.click(outside);
    assert.equal(popup.open, false);
    if (name === 'manager') {
        assert.equal(app.dialog.open, true);
        assert.equal(app.manageButton.focused, true);
    }
});

test('failed requests display an error rather than an empty success', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({detail: 'Reconnect Twitch.'}, false);
    await flush();
    assert.equal(app.status.textContent, 'Reconnect Twitch.');
    assert.equal(app.status.classes.has('error'), true);
});

test('a large loaded list renders only nearby cards and recreates earlier cards when scrolling back', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: Array.from({length: 1000}, (_, index) => channel(String(index))), cursor: ''});
    await flush();
    const first = app.grid().children[0];
    assert.equal(first.dataset.channelIndex, '0');
    assert.ok(app.grid().children.length < 30);
    app.results.scrollTop = 25000;
    app.results.handlers.scroll(); await flush();
    assert.ok(Number(app.grid().children[0].dataset.channelIndex) > 100);
    assert.equal(first.parent, null);
    assert.ok(app.grid().children.length < 30);
    app.results.scrollTop = 0;
    app.results.handlers.scroll(); await flush();
    assert.equal(app.grid().children[0].dataset.channelIndex, '0');
    assert.notEqual(app.grid().children[0], first);
    assert.equal(app.requests.length, 1);
});

test('resizing recomputes the number of columns and card window', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: Array.from({length: 100}, (_, index) => channel(String(index))), cursor: ''});
    await flush();
    assert.equal(app.grid().style.gridTemplateColumns, 'repeat(2,minmax(0,1fr))');
    app.results.clientWidth = 320;
    app.resize(); await flush();
    assert.equal(app.grid().style.gridTemplateColumns, 'repeat(1,minmax(0,1fr))');
    assert.ok(app.grid().children.length < 10);
});

test('a failed lazy load stops automatic retries and a filter update starts a fresh search', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel()], cursor: 'next'});
    await flush();
    assert.equal(app.requests.length, 2);
    app.requests[1].respond({detail: 'Try again later.'}, false);
    await flush();
    assert.match(app.status.textContent, /Couldn't load more channels/);
    assert.equal(app.grid().children.length, 1);
    app.results.handlers.scroll(); await flush();
    assert.equal(app.requests.length, 2);
    app.fields.follow_status.value = 'following';
    app.search.handlers.change({target: app.fields.follow_status});
    assert.equal(app.requests[2].url.searchParams.get('after'), null);
});

test('filters reset the window and are included in subsequent lazy-load requests', async () => {
    const app = setup(); app.opener.handlers.click();
    app.fields.category_id.value = '509658';
    app.fields.tags.value = 'VTuber';
    app.fields.language.value = 'ja';
    app.search.handlers.change({target: app.fields.language});
    const url = app.requests[1].url;
    assert.equal(url.searchParams.get('category_id'), '509658');
    assert.equal(url.searchParams.get('tags'), 'VTuber');
    assert.equal(url.searchParams.get('language'), 'ja');
    app.requests[1].respond({channels: [channel()], cursor: 'next'});
    await flush();
    assert.equal(app.requests[2].url.searchParams.get('language'), 'ja');
    assert.equal(app.requests[2].url.searchParams.get('after'), 'next');
});

test('following dropdown defaults to Any and maps each choice to exclusive API filters', () => {
    const app = setup(); app.opener.handlers.click();
    assert.equal(app.fields.follow_status.value, '');
    for (const choice of ['', 'not_following', 'following', 'mutual', '']) {
        app.fields.follow_status.value = choice;
        app.search.handlers.change({target: app.fields.follow_status});
        const params = app.requests.at(-1).url.searchParams;
        assert.equal(params.has('not_following'), choice === 'not_following');
        assert.equal(params.has('following'), choice === 'following' || choice === 'mutual');
        assert.equal(params.has('mutual'), choice === 'mutual');
        assert.equal(params.has('follow_status'), false);
    }
    const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
    assert.match(template, /Following<select name="follow_status" data-hover-current-value><option value="">Any<\/option>/);
    assert.ok(!template.includes('raid-browser-follow-buttons'));
});

test('not following excludes incompatible filters and persists through pagination and reset', async () => {
    const app = setup(); app.opener.handlers.click();
    app.fields.follow_status.value = 'not_following';
    app.search.handlers.change({target: app.fields.follow_status});
    assert.equal(app.requests[1].url.searchParams.get('not_following'), 'true');
    assert.equal(app.requests[1].url.searchParams.has('following'), false);
    app.requests[1].respond({channels: [channel()], cursor: 'next'}); await flush();
    assert.equal(app.requests[2].url.searchParams.get('not_following'), 'true');
    assert.equal(app.requests[2].url.searchParams.get('after'), 'next');
    app.search.handlers.reset({preventDefault() {}});
    assert.equal(app.fields.follow_status.value, '');
    assert.equal(app.requests.at(-1).url.searchParams.has('not_following'), false);
});

test('changing from not following to following or mutual replaces the previous filter', () => {
    for (const name of ['following', 'mutual']) {
        const app = setup(); app.opener.handlers.click();
        app.fields.follow_status.value = 'not_following';
        app.search.handlers.change({target: app.fields.follow_status});
        app.fields.follow_status.value = name;
        app.search.handlers.change({target: app.fields.follow_status});
        assert.equal(app.requests[2].url.searchParams.has('not_following'), false);
        assert.equal(app.requests[2].url.searchParams.get(name), 'true');
    }
});

test('following filters remain enabled and apply on the favorites tab', async () => {
    const app = setup(new Map([['ratsboombot:raid-favorites:1', '["2"]']]));
    app.opener.handlers.click();
    app.fields.follow_status.value = 'not_following';
    app.favoritesTab.handlers.click();
    assert.notEqual(app.fields.follow_status.disabled, true);
    assert.equal(app.requests.at(-1).url.searchParams.get('not_following'), 'true');
    app.browseTab.handlers.click();
    assert.notEqual(app.fields.follow_status.disabled, true);
    assert.equal(app.requests.at(-1).url.searchParams.get('not_following'), 'true');
});

test('stream-team dropdown applies only in its collection and resets with the other filters', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel()], cursor: '', team_live: true}); await flush();
    const label = app.search.querySelector('[data-raid-team-filter]');
    assert.equal(label.hidden, true);
    app.teamTab.handlers.click();
    assert.equal(label.hidden, false);
    app.requests.at(-1).respond({channels: [channel()], cursor: '', teams: ['Team One', 'Team Two']}); await flush();
    assert.deepEqual(app.fields.team.children.map(option => option.textContent), ['All teams', 'Team One', 'Team Two']);
    app.fields.team.value = 'Team Two';
    app.search.handlers.change({target: app.fields.team});
    assert.equal(app.requests.at(-1).url.searchParams.get('team'), 'Team Two');
    app.browseTab.handlers.click();
    assert.equal(label.hidden, true);
    assert.equal(app.requests.at(-1).url.searchParams.has('team'), false);
    app.teamTab.handlers.click();
    assert.equal(app.requests.at(-1).url.searchParams.get('team'), 'Team Two');
    app.search.handlers.reset({preventDefault() {}});
    assert.equal(app.fields.team.value, '');
});

test('pinning saves immediately but preserves order and scroll until refresh', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [Object.assign(channel('2'), {relevance: 1000}), channel('3')], cursor: ''});
    await flush();
    const pin = app.grid().children[1].querySelector('.raid-browser-pin');
    assert.equal(pin.attributes['aria-pressed'], 'false');
    app.results.scrollTop = 25;
    pin.handlers.click();
    assert.equal(app.grid().children[0].dataset.channelId, '2');
    assert.equal(app.grid().children[1].querySelector('.raid-browser-pin'), pin);
    assert.equal(pin.attributes['aria-pressed'], 'true');
    assert.equal(app.results.scrollTop, 25);
    assert.deepEqual(JSON.parse(app.storage.get('ratsboombot:raid-favorites:1')), ['3']);
    app.dialog.close(); app.opener.handlers.click();
    app.requests[1].respond({channels: [channel('2'), channel('3')], cursor: ''}); await flush();
    assert.equal(app.grid().children[0].dataset.channelId, '3');
    app.grid().children[0].querySelector('.raid-browser-pin').handlers.click();
    assert.equal(app.grid().children[0].dataset.channelId, '3');
    assert.deepEqual(JSON.parse(app.storage.get('ratsboombot:raid-favorites:1')), []);
});

test('saved favorites are requested on refresh and do not leak across connected channels', async () => {
    const storage = new Map([['ratsboombot:raid-favorites:1', '["3"]']]);
    const app = setup(storage); app.opener.handlers.click();
    assert.equal(app.requests[0].url.searchParams.get('favorites'), '3');
    app.requests[0].respond({channels: [channel('2'), channel('3')], cursor: ''});
    await flush();
    assert.equal(app.grid().children[0].dataset.channelId, '3');
    const other = setup(storage, '99'); other.opener.handlers.click();
    assert.equal(other.requests[0].url.searchParams.has('favorites'), false);
});

test('malformed favorite storage does not block browsing', () => {
    const app = setup(new Map([['ratsboombot:raid-favorites:1', 'broken json']]));
    app.opener.handlers.click();
    assert.equal(app.requests.length, 1);
    assert.equal(app.requests[0].url.searchParams.has('favorites'), false);
});

test('tag length limit is per tag, not the combined comma-separated field', () => {
    const app = setup(); app.opener.handlers.click();
    app.fields.tags.value = 'a'.repeat(26);
    app.search.handlers.input({target: app.fields.tags});
    [...app.timers.values()].pop()();
    assert.equal(app.requests.length, 1);
    assert.match(app.status.textContent, /25 characters/);
    app.fields.tags.value = 'a'.repeat(25) + ', ' + 'b'.repeat(25);
    app.search.handlers.input({target: app.fields.tags});
    [...app.timers.values()].pop()();
    assert.equal(app.requests.length, 2);
});

test('list toggle virtualizes compact rows and saves the chosen layout', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: Array.from({length: 100}, (_, index) => channel(String(index))), cursor: ''});
    await flush();
    app.listView.handlers.click(); await flush();
    assert.equal(app.dialog.classes.has('is-list-view'), true);
    assert.equal(app.grid().style.gridTemplateColumns, 'repeat(1,minmax(0,1fr))');
    assert.equal(app.grid().style.gridAutoRows, '156px');
    assert.ok(app.grid().children.length < 10);
    assert.equal(app.listView.attributes['aria-pressed'], 'true');
    assert.equal(app.storage.get('ratsboombot:raid-browser-view:1'), 'list');
    const refreshed = setup(app.storage);
    assert.equal(refreshed.dialog.classes.has('is-list-view'), true);
    app.cardView.handlers.click(); await flush();
    assert.equal(app.dialog.classes.has('is-list-view'), false);
    assert.equal(app.grid().style.gridTemplateColumns, 'repeat(2,minmax(0,1fr))');
});

test('follow badges distinguish following from confirmed mutual following', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [Object.assign(channel('2'), {language: 'en', followed: true, mutual: true}),
        Object.assign(channel('3'), {language: 'en', followed: true, mutual: null}), channel('4')], cursor: ''});
    await flush();
    const tags = app.grid().children.map(card => card.querySelector('.raid-browser-tags'));
    const headings = app.grid().children.map(card => card.querySelector('.raid-browser-channel-heading'));
    assert.equal(headings[0].children[0].className, 'raid-browser-language');
    assert.equal((headings[0].children[1].innerHTML.match(/<path /g) || []).length, 2);
    assert.equal(headings[0].children[1].className, 'raid-browser-follow-badge is-mutual');
    assert.match(headings[0].children[1].title, /Mutual following/);
    assert.equal((headings[1].children[1].innerHTML.match(/<path /g) || []).length, 1);
    assert.match(headings[1].children[1].attributes['aria-label'], /Following/);
    assert.equal(headings[0].children[1].attributes.role, 'img');
    assert.equal(tags[0].children.length, 0);
    assert.equal(tags[2].children.length, 0);
    assert.deepEqual(app.grid().children.map(card => card.classes.has('is-following')), [true, true, false]);
    assert.deepEqual(app.grid().children.map(card => card.classes.has('is-mutual')), [true, false, false]);
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.match(styles, /\.raid-browser-channel\.is-mutual \{ background: linear-gradient\(rgb\(236 72 153 \/ \.13\), rgb\(236 72 153 \/ \.13\)\), var\(--surface\); \}/);
    assert.match(styles, /\.raid-browser-channel\.is-following \{ background: linear-gradient\(rgb\(236 72 153 \/ \.07\), rgb\(236 72 153 \/ \.07\)\), var\(--surface\); \}/);
});

test('thumbnails offer native responsive sources without scripted resolution switching', async () => {
    const app = setup(); app.opener.handlers.click();
    const item = Object.assign(channel(), {thumbnail_url_medium: 'https://static-cdn.jtvnw.net/test-640x360.jpg',
        thumbnail_url_large: 'https://static-cdn.jtvnw.net/test-1280x720.jpg'});
    app.requests[0].respond({channels: [item], cursor: ''}); await flush();
    const image = app.grid().children[0].querySelector('img');
    assert.equal(image.src, item.thumbnail_url);
    assert.equal(image.srcset, `${item.thumbnail_url} 320w, ${item.thumbnail_url_medium} 640w, ${item.thumbnail_url_large} 1280w`);
    assert.equal(image.sizes, 'auto, 100vw');
    assert.equal(image.loading, 'lazy');
    assert.equal(image.width / image.height, 16 / 9);
    const sources = image.srcset;
    app.sizeSlider.value = '2'; app.sizeSlider.handlers.input(); await flush();
    assert.equal(image.src, item.thumbnail_url);
    app.sizeSlider.value = '1'; app.sizeSlider.handlers.input(); await flush();
    assert.equal(image.src, item.thumbnail_url);
    app.sizeSlider.value = '0'; app.sizeSlider.handlers.input(); await flush();
    assert.equal(image.src, item.thumbnail_url);
    assert.equal(image.srcset, sources);
});

test('overscan thumbnails wait for visibility and activate without rebuilding cards', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: Array.from({length: 20}, (_, index) => channel(String(index + 2))), cursor: ''}); await flush();
    const cards = [...app.grid().children];
    const images = cards.map(card => card.querySelector('.raid-browser-thumbnail').querySelector('img'));
    assert.equal(images[0].fetchPriority, 'high');
    assert.equal(images[0].decoding, 'async');
    assert.ok(images.some(image => image.src));
    const deferredIndex = images.findIndex(image => !image.src);
    assert.ok(deferredIndex > 0, 'Cards below the viewport must not start image requests');
    assert.ok(images[deferredIndex].dataset.thumbnailSrc);
    assert.equal(images[deferredIndex].srcset, undefined);
    const stride = parseInt(app.grid().style.gridAutoRows) + 12;
    app.results.scrollTop = stride * Math.floor(deferredIndex / 2);
    app.results.handlers.scroll(); await flush();
    assert.equal(app.grid().children.includes(cards[deferredIndex]), true);
    assert.ok(images[deferredIndex].src);
    assert.equal(images[deferredIndex].fetchPriority, 'high');
    assert.equal(images[deferredIndex].dataset.thumbnailSrc, undefined);
    assert.equal(app.requests.length, 1);
});

test('missing profile pictures load after visible cards without replacing them or repeating requests', async () => {
    const app = setup(); app.opener.handlers.click();
    assert.equal(app.requests[0].url.searchParams.get('defer_profiles'), 'true');
    app.requests[0].respond({channels: [channel('2'), channel('3')], cursor: '', profile_pending_ids: ['2', '3']}); await flush();
    const cards = [...app.grid().children];
    assert.equal(cards.length, 2);
    assert.equal(app.requests[1].url.pathname, '/channel/api/raid-browser/profiles');
    assert.equal(app.requests[1].url.searchParams.get('ids'), '2,3');
    const image = 'https://static-cdn.jtvnw.net/jtv_user_pictures/target.png';
    app.requests[1].respond({profiles: [{id: '2', profile_image_url: image, verified: true, description: 'Bio'}]}); await flush();
    assert.equal(app.grid().children[0], cards[0]);
    assert.equal(app.grid().children[1], cards[1]);
    assert.equal(cards[0].querySelector('.raid-browser-avatar').src, image);
    assert.ok(cards[0].querySelector('.raid-browser-verified'));
    app.results.handlers.scroll(); await flush();
    assert.equal(app.requests.length, 2);
});

test('late profile response cannot modify a different filter result', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel('2')], cursor: '', profile_pending_ids: ['2']}); await flush();
    app.fields.language.value = 'ja'; app.search.handlers.change({target: app.fields.language});
    app.requests[2].respond({channels: [channel('3')], cursor: ''}); await flush();
    const card = app.grid().children[0];
    app.requests[1].respond({profiles: [{id: '2', profile_image_url: 'https://static-cdn.jtvnw.net/old.png'}]}); await flush();
    assert.equal(app.grid().children[0], card);
    assert.equal(card.querySelector('.raid-browser-avatar'), undefined);
});

test('responsive thumbnails omit untrusted and duplicate source URLs', async () => {
    const app = setup(); app.opener.handlers.click();
    const item = Object.assign(channel(), {thumbnail_url_medium: channel().thumbnail_url,
        thumbnail_url_large: 'https://example.com/image.jpg'});
    app.requests[0].respond({channels: [item], cursor: ''}); await flush();
    const image = app.grid().children[0].querySelector('img');
    assert.equal(image.srcset, `${item.thumbnail_url} 320w`);
});

test('stream events appear alongside category without an empty label on other channels', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [Object.assign(channel('2'), {events: ['Drops Enabled']}), channel('3')], cursor: ''}); await flush();
    const [active, ordinary] = app.grid().children;
    const info = active.querySelector('.raid-browser-stream-info');
    assert.equal(info.children[0].className, 'raid-browser-category-name');
    assert.equal(info.children[0].textContent, 'Retro');
    assert.equal(info.children[1].textContent, 'Drops Enabled');
    assert.equal(info.children[1].title, 'Drops Enabled');
    assert.equal(ordinary.querySelector('.raid-browser-stream-info').children.length, 1);
});

test('VTuber channels retain their tag and get a thumbnail badge in both layouts', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [Object.assign(channel('2'), {tags: ['vTuBeR']}), channel('3')], cursor: ''}); await flush();
    for (const list of [false, true]) {
        if (list) { app.listView.handlers.click(); await flush(); }
        const [vtuber, other] = app.grid().children;
        const badge = vtuber.querySelector('.raid-browser-thumbnail').querySelector('.raid-browser-vtuber');
        assert.equal(badge.textContent, 'VT');
        assert.equal(badge.attributes['aria-label'], 'VTuber');
        assert.equal(vtuber.querySelector('.raid-browser-tags').children[0].textContent, 'vTuBeR');
        assert.equal(other.querySelector('.raid-browser-vtuber'), undefined);
    }
});

test('tag suggestions populate from results, stay available across searches, and toggle filters', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [Object.assign(channel(), {tags: ['Art', 'VTuber', 'x'.repeat(26)]})], channel_tags: ['Art', 'VTuber'], cursor: ''});
    await flush();
    assert.deepEqual(app.tagOptions.children.map(button => button.textContent), ['VTuber', 'Art']);
    assert.equal(app.selectedTags.children.length, 0);
    app.tagOptions.children[1].handlers.click();
    assert.equal(app.fields.tags.value, 'Art');
    assert.equal(app.requests[1].url.searchParams.get('tags'), 'Art');
    app.requests[1].respond({channels: [], cursor: ''}); await flush();
    assert.equal(app.tagSearch.value, '');
    assert.equal(app.selectedTags.children[0].textContent, 'Art ×');
    app.selectedTags.children[0].handlers.click();
    assert.equal(app.fields.tags.value, '');
});

test('tag searching only filters suggestions and prioritizes current channel tags', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [Object.assign(channel(), {tags: ['Art', 'VTuber', 'Party']})], channel_tags: ['Art'], cursor: ''});
    await flush();
    assert.deepEqual(app.tagOptions.children.map(button => button.textContent), ['VTuber', 'Art']);
    app.tagSearch.value = 'ar';
    app.search.handlers.input({target: app.tagSearch});
    assert.deepEqual(app.tagOptions.children.map(button => button.textContent), ['VTuber', 'Art', 'Party']);
    assert.equal(app.fields.tags.value, '');
    assert.equal(app.requests.length, 1);
    assert.ok([...app.timers.keys()].every(id => app.delays.get(id) === 4000), 'Tag searches must not schedule a results reload');
});

test('arrow keys navigate all tag suggestions and Enter selects the focused result', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [], channel_tags: ['Art', 'Cozy'], cursor: ''}); await flush();
    app.tagSearch.handlers.keydown({key: 'ArrowDown', preventDefault() {}});
    const [first, second, last] = app.tagOptions.children;
    assert.equal(first.focused, true);
    assert.equal(first.attributes['data-hover-pointer-only'], '');
    const key = (target, key) => app.tagOptions.handlers.keydown({target, key, preventDefault() {}, stopPropagation() {}});
    key(first, 'ArrowDown'); assert.equal(second.focused, true);
    key(second, 'ArrowDown'); assert.equal(last.focused, true);
    key(last, 'ArrowUp'); assert.equal(second.focused, true);
    key(second, 'Home'); assert.equal(first.focused, true);
    key(first, 'End'); assert.equal(last.focused, true);
    key(last, 'Enter'); assert.equal(app.fields.tags.value, 'Cozy');
    assert.equal(app.tagSearch.focused, true);
    assert.equal(app.requests[1].url.searchParams.get('tags'), 'Cozy');
    app.tagSearch.handlers.keydown({key: 'ArrowUp', preventDefault() {}});
    assert.equal(app.tagOptions.children.at(-1).focused, true);
    key(app.tagOptions.children[0], 'ArrowUp'); assert.equal(app.tagSearch.focused, true);
    key(app.tagOptions.children[0], 'Escape'); assert.equal(app.tagOptions.hidden, true);
});

test('Enter adds arbitrary tags without requiring a suggestion and deduplicates casing', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [], cursor: ''}); await flush();
    let prevented = false;
    app.tagSearch.value = 'MyCustomTag';
    app.tagSearch.handlers.keydown({key: 'Enter', preventDefault() { prevented = true; }});
    assert.equal(prevented, true);
    assert.equal(app.fields.tags.value, 'MyCustomTag');
    assert.equal(app.requests[1].url.searchParams.get('tags'), 'MyCustomTag');
    assert.equal(app.tagSearch.value, '');
    app.tagSearch.value = 'mycustomtag';
    app.tagSearch.handlers.keydown({key: 'Enter', preventDefault() {}});
    assert.equal(app.fields.tags.value, 'MyCustomTag');
    app.tagSearch.value = 'x'.repeat(26);
    app.tagSearch.handlers.keydown({key: 'Enter', preventDefault() {}});
    assert.equal(app.fields.tags.value, 'MyCustomTag');
});

test('tag suggestions open as a dropdown on focus and close on dismissal', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [], channel_tags: ['Art'], cursor: ''}); await flush();
    assert.equal(app.tagOptions.hidden, true);
    app.tagSearch.handlers.focus();
    assert.equal(app.tagOptions.hidden, false);
    assert.equal(app.tagSearch.attributes['aria-expanded'], 'true');
    assert.equal(app.tagOptions.popoverOpen, true);
    app.tagSearch.handlers.blur({relatedTarget: app.input});
    assert.equal(app.tagOptions.hidden, true);
    assert.equal(app.tagSearch.attributes['aria-expanded'], 'false');
});

test('typing waits 500 milliseconds and blur does not bypass the delay', () => {
    const app = setup(); app.opener.handlers.click();
    app.input.value = 'mina';
    app.search.handlers.input({target: app.input});
    const timer = [...app.timers.keys()].pop();
    assert.equal(app.delays.get(timer), 500);
    app.search.handlers.change({target: app.input});
    assert.equal(app.requests.length, 1);
    app.timers.get(timer)();
    assert.equal(app.requests[1].url.searchParams.get('query'), 'mina');
});

test('language appears in a rounded-badge heading before the channel name, not among tags', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [Object.assign(channel(), {language: 'ja', tags: ['VTuber']})], cursor: ''});
    await flush();
    const card = app.grid().children[0];
    const heading = card.querySelector('.raid-browser-channel-heading');
    assert.equal(heading.className, 'raid-browser-channel-heading');
    assert.equal(heading.children[0].className, 'raid-browser-language');
    assert.equal(heading.children[0].textContent, 'JA');
    assert.equal(heading.children[0].title, 'Japanese');
    assert.equal(heading.children[1].textContent, 'Viewer2');
    assert.equal(heading.children[1].tagName, 'a');
    assert.equal(heading.children[1].href, 'https://www.twitch.tv/viewer2');
    assert.equal(heading.children[1].rel, 'noopener noreferrer');
    assert.equal(heading.children[2].className, 'raid-browser-stream-actions');
    assert.equal(heading.children[3].className, 'raid-browser-pin');
    assert.equal(heading.children[4].className, 'raid-browser-more');
    assert.equal(heading.children[4].textContent, '⋮');
    assert.equal(card.children.filter(child => child.tagName === 'a').length, 0);
    assert.equal(card.querySelector('.raid-browser-tags').children.length, 1);
    assert.equal(card.querySelector('.raid-browser-tags').children[0].textContent, 'VTuber');
});

test('verified badge is immediately after the name only for confirmed partners', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [Object.assign(channel('2'), {verified: true}),
        Object.assign(channel('3'), {verified: false}), channel('4')], cursor: ''});
    await flush();
    const headings = app.grid().children.map(card => card.querySelector('.raid-browser-channel-heading'));
    assert.equal(headings[0].children[0].tagName, 'a');
    assert.equal(headings[0].children[1].className, 'raid-browser-verified');
    assert.equal(headings[0].children[1].attributes['aria-label'], 'Verified Twitch Partner');
    assert.equal(headings[1].children.length, 4);
    assert.equal(headings[2].children.length, 4);
});

test('unfavoriting requires confirmation and cancelling preserves the pin', async () => {
    const app = setup(new Map([['ratsboombot:raid-favorites:1', '["2"]']])); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel()], cursor: ''}); await flush();
    app.confirm(false);
    app.grid().children[0].querySelector('.raid-browser-pin').handlers.click();
    assert.equal(app.confirmations.length, 1);
    assert.equal(app.grid().children[0].querySelector('.raid-browser-pin').attributes['aria-pressed'], 'true');
    assert.equal(app.storage.get('ratsboombot:raid-favorites:1'), '["2"]');
});

test('Favorites tab requests only favorites and excludes unrelated returned channels', async () => {
    const app = setup(new Map([['ratsboombot:raid-favorites:1', '["3"]']])); app.opener.handlers.click();
    app.favoritesTab.handlers.click();
    assert.equal(app.requests[1].url.searchParams.get('favorites_only'), 'true');
    assert.equal(app.requests[1].url.searchParams.has('recommended'), false);
    app.requests[1].respond({channels: [channel('2'), channel('3')], cursor: ''}); await flush();
    assert.equal(app.grid().children.length, 1);
    assert.equal(app.grid().children[0].dataset.channelId, '3');
    assert.equal(app.favoritesTab.attributes['aria-pressed'], 'true');
});

test('suggestions survive their opening press and close only on an outside press', async () => {
    const app = setup(); app.opener.handlers.click();
    app.dialog.handlers.pointerdown({target: app.tagSearch});
    app.tagSearch.handlers.focus();
    assert.equal(app.tagOptions.hidden, false);
    app.dialog.handlers.pointerdown({target: app.tagSearch});
    assert.equal(app.tagOptions.hidden, false);
    app.dialog.handlers.pointerdown({target: app.categorySearch});
    app.categorySearch.handlers.focus();
    assert.equal(app.tagOptions.hidden, true);
    assert.equal(app.categoryOptions.hidden, false);
    app.dialog.handlers.pointerdown({target: app.categoryOptions.children[0]});
    assert.equal(app.categoryOptions.hidden, false);
    app.dialog.handlers.pointerdown({target: app.input});
    assert.equal(app.categoryOptions.hidden, true);
    const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
    assert.match(template, /id="raid-browser-category-options"[^>]*popover="manual"/);
    assert.match(template, /id="raid-browser-tag-options"[^>]*popover="manual"/);
});

test('Stream team tab applies team filtering and clears it when returning to Browse', async () => {
    const app = setup(); app.opener.handlers.click();
    app.teamTab.handlers.click();
    assert.equal(app.requests[1].url.searchParams.get('same_team'), 'true');
    assert.equal(app.teamTab.attributes['aria-pressed'], 'true');
    assert.equal(app.browseTab.attributes['aria-pressed'], 'false');
    app.requests[1].respond({channels: [], cursor: ''}); await flush();
    assert.equal(app.status.textContent, 'No live stream team channels match your filters.');
    app.browseTab.handlers.click();
    assert.equal(app.requests[2].url.searchParams.has('same_team'), false);
    assert.equal(app.teamTab.attributes['aria-pressed'], 'false');
});

test('three-dot menu blacklists a channel and persists exclusion after refresh', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel(), channel('3')], cursor: ''}); await flush();
    const card = app.grid().children[0];
    const more = card.querySelector('.raid-browser-more'); more.handlers.click();
    assert.equal(more.attributes['aria-expanded'], 'true');
    card.querySelector('.raid-browser-channel-menu').querySelector('button').handlers.click();
    assert.deepEqual(JSON.parse(app.storage.get('ratsboombot:raid-blacklist:1')), ['2']);
    assert.equal(app.grid().children.length, 1);
    const refreshed = setup(app.storage); refreshed.opener.handlers.click();
    assert.equal(refreshed.requests[0].url.searchParams.get('blocked'), '2');
    refreshed.requests[0].respond({channels: [channel(), channel('3')], cursor: ''}); await flush();
    assert.equal(refreshed.grid().children.length, 1);
    assert.equal(refreshed.grid().children[0].dataset.channelId, '3');
});

test('list manager resolves offline names and restores blacklisted recommendations', async () => {
    const app = setup(new Map([['ratsboombot:raid-favorites:1', '["2"]'], ['ratsboombot:raid-blacklist:1', '["3"]']]));
    app.opener.handlers.click();
    app.manageButton.handlers.click();
    assert.equal(app.manager.open, true);
    assert.equal(app.requests[1].url.pathname, '/channel/api/raid-browser/lists');
    app.requests[1].respond({channels: [channel(), channel('3')]}); await flush();
    assert.equal(app.favoriteList.children[0].children[0].textContent, 'Viewer2');
    app.blockedList.children[0].querySelector('button').handlers.click();
    assert.deepEqual(JSON.parse(app.storage.get('ratsboombot:raid-blacklist:1')), []);
    assert.equal(app.blockedList.children.length, 0);
    app.confirm(false); app.favoriteList.children[0].querySelector('button').handlers.click();
    assert.equal(app.favoriteList.children.length, 1);
    app.managerClose.handlers.click();
    assert.equal(app.manager.open, false);
    assert.equal(app.manageButton.focused, true);
});

for (const [sort, order] of [
    ['viewers_asc', ['4', '2', '3']], ['viewers_desc', ['3', '2', '4']],
    ['name_asc', ['3', '4', '2']], ['name_desc', ['2', '4', '3']],
    ['uptime_asc', ['3', '2', '4']], ['uptime_desc', ['2', '3', '4']]]) {
    test(`sort dropdown orders loaded channels by ${sort}`, async () => {
        const app = setup(); app.opener.handlers.click();
        app.fields.sort.value = sort; app.search.handlers.change({target: app.fields.sort});
        assert.equal(app.requests[1].url.searchParams.get('sort'), sort);
        assert.equal(app.requests[1].url.searchParams.get('recommended'), 'true');
        app.requests[1].respond({channels: [
            Object.assign(channel('2'), {viewers: 10, display_name: 'Zulu', started_at: '2026-10-14T01:00:00Z'}),
            Object.assign(channel('3'), {viewers: 50, display_name: 'alpha', started_at: '2026-10-14T02:00:00Z'}),
            Object.assign(channel('4'), {viewers: 0, display_name: 'Middle', started_at: ''})], cursor: ''});
        await flush();
        assert.deepEqual(app.grid().children.map(card => card.dataset.channelId), order);
    });
}

for (const sort of ['for_you', 'viewers_asc', 'viewers_desc', 'name_asc', 'name_desc', 'uptime_asc', 'uptime_desc']) {
    test(`favorites remain above other channels when sorting by ${sort}`, async () => {
        const app = setup(new Map([['ratsboombot:raid-favorites:1', '["3","5"]']]));
        app.fields.sort.value = sort; app.opener.handlers.click();
        app.requests[0].respond({channels: [
            Object.assign(channel('2'), {viewers: 0, display_name: 'Alpha', relevance: 9999, started_at: '2026-10-14T01:00:00Z'}),
            Object.assign(channel('3'), {viewers: 50, display_name: 'Middle', started_at: '2026-10-14T02:00:00Z'}),
            Object.assign(channel('4'), {viewers: 100, display_name: 'Zulu', started_at: '2026-10-14T03:00:00Z'}),
            Object.assign(channel('5'), {viewers: 25, display_name: 'Beta', started_at: '2026-10-14T04:00:00Z'})], cursor: ''});
        await flush();
        const expected = ['viewers_asc', 'name_asc', 'uptime_asc'].includes(sort) ? ['5', '3'] : ['3', '5'];
        assert.deepEqual(app.grid().children.slice(0, 2).map(card => card.dataset.channelId), expected);
        app.grid().children[0].querySelector('.raid-browser-pin').handlers.click();
        app.results.handlers.scroll(); await flush();
        assert.deepEqual(app.grid().children.slice(0, 2).map(card => card.dataset.channelId), expected);
    });
}

test('personalized mix includes suggested streamers and labels cached fallback results', async () => {
    const app = setup(); app.opener.handlers.click();
    assert.equal(app.requests[0].url.searchParams.get('recommended'), 'true');
    assert.equal(app.requests[0].url.searchParams.has('suggested'), false);
    app.requests[0].respond({channels: [Object.assign(channel(), {suggested: true})], cursor: '', suggested_status: 'stale'});
    await flush();
    assert.equal(app.grid().children[0].querySelector('.raid-browser-tags').children[0].textContent, 'Suggested');
    assert.match(app.status.textContent, /last saved suggested streamers/);
    app.favoritesTab.handlers.click();
    assert.equal(app.requests[1].url.searchParams.has('recommended'), false);
});

test('clearing category search refreshes channels only when removing a selected category', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [], cursor: ''}); await flush();
    app.categorySearch.value = 'Retro'; app.search.handlers.input({target: app.categorySearch});
    app.categorySearch.value = ''; app.search.handlers.input({target: app.categorySearch});
    assert.equal(app.requests.length, 1);
    app.fields.category_id.value = '123';
    app.search.handlers.input({target: app.categorySearch});
    assert.equal(app.requests.length, 2);
    assert.equal(app.fields.category_id.value, '');
    assert.equal(app.requests[1].url.searchParams.has('category_id'), false);
    app.search.handlers.input({target: app.categorySearch});
    assert.equal(app.requests.length, 2);
});

test('For You prioritizes search matches over relevance while respecting pinned favorites', async () => {
    const app = setup(new Map([['ratsboombot:raid-favorites:1', '["4"]']]));
    app.input.value = 'mina'; app.opener.handlers.click();
    app.requests[0].respond({channels: [Object.assign(channel('2'), {search_score: 500, relevance: 1000}),
        Object.assign(channel('3'), {search_score: 1000, relevance: 0}),
        Object.assign(channel('4'), {search_score: 100, relevance: 0})], cursor: ''}); await flush();
    assert.deepEqual(app.grid().children.map(card => card.dataset.channelId), ['4', '3', '2']);
});

test('event filter is sent on selection and omitted when Any event is selected', async () => {
    const app = setup(); app.opener.handlers.click();
    app.fields.event.value = 'drops_enabled';
    app.search.handlers.change({target: app.fields.event});
    assert.equal(app.requests[1].url.searchParams.get('event'), 'drops_enabled');
    app.fields.event.value = '';
    app.search.handlers.change({target: app.fields.event});
    assert.equal(app.requests[2].url.searchParams.has('event'), false);
});

test('live dev priority stays below favorites and cannot enable raiding yourself', async () => {
    const app = setup(new Map([['ratsboombot:raid-favorites:1', '["4"]']])); app.opener.handlers.click();
    app.requests[0].respond({channels: [Object.assign(channel('2'), {dev_priority: true, is_self: true}),
        Object.assign(channel('3'), {relevance: 9999}), channel('4')], cursor: ''}); await flush();
    assert.deepEqual(app.grid().children.map(card => card.dataset.channelId), ['4', '2', '3']);
    const ownRaid = app.grid().children[1].querySelector('.raid-browser-start-raid');
    assert.equal(app.grid().children[1].querySelector('.raid-browser-developer-tag').textContent, 'Developer');
    assert.equal(app.grid().children[2].querySelector('.raid-browser-developer-tag'), undefined);
    assert.equal(ownRaid.disabled, true);
    await ownRaid.handlers.click();
    assert.equal(app.requests.length, 1);
});

test('Developer tab appears only when live and falls back to Browse when both go offline', async () => {
    const app = setup(); app.opener.handlers.click();
    assert.equal(app.developerTab.hidden, true);
    app.requests[0].respond({channels: [], cursor: '', developers_live: true}); await flush();
    assert.equal(app.developerTab.hidden, false);
    app.developerTab.handlers.click();
    assert.equal(app.requests[1].url.searchParams.get('developer_only'), 'true');
    app.requests[1].respond({channels: [Object.assign(channel('2'), {dev_priority: true}), channel('3')], developers_live: true, cursor: ''}); await flush();
    assert.deepEqual(app.grid().children.map(card => card.dataset.channelId), ['2']);
    app.developerTab.handlers.click();
    app.requests[2].respond({channels: [], developers_live: false, cursor: ''}); await flush();
    assert.equal(app.developerTab.hidden, true);
    assert.equal(app.browseTab.attributes['aria-pressed'], 'true');
    assert.equal(app.requests[3].url.searchParams.has('developer_only'), false);
});

for (const [tab, property] of [['favoritesTab', 'favorites_live'], ['teamTab', 'team_live']]) {
    test(`${tab} hides when no channels are live and returns to Browse`, async () => {
        const app = setup(); app.opener.handlers.click();
        assert.equal(app[tab].hidden, true);
        app.requests[0].respond({channels: [], cursor: '', [property]: true}); await flush();
        assert.equal(app[tab].hidden, false);
        app[tab].handlers.click();
        app.requests[1].respond({channels: [], cursor: '', [property]: false}); await flush();
        assert.equal(app[tab].hidden, true);
        assert.equal(app.browseTab.attributes['aria-pressed'], 'true');
        assert.notEqual(app.fields.follow_status.disabled, true);
        assert.equal(app.requests[2].url.searchParams.has('same_team'), false);
        assert.equal(app.requests[2].url.searchParams.has('favorites_only'), false);
    });
}

test('overflow indicators track truncated titles and tags and clear after resizing', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel()], cursor: ''}); await flush();
    const card = app.grid().children[0];
    const title = card.querySelector('.raid-browser-stream-title');
    const tags = card.querySelector('.raid-browser-tags');
    title.scrollHeight = 72; tags.scrollHeight = 50;
    app.resize(); await flush();
    assert.equal(card.classes.has('has-title-overflow'), true);
    assert.equal(card.classes.has('has-tags-overflow'), true);
    title.scrollHeight = 36; tags.scrollHeight = 22; tags.scrollWidth = tags.clientWidth;
    app.resize(); await flush();
    assert.equal(card.classes.has('has-title-overflow'), false);
    assert.equal(card.classes.has('has-tags-overflow'), false);
});

test('pinning a live channel reveals Favorites immediately without reloading or reordering', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel('2'), channel('3')], cursor: '', favorites_live: false, live_favorite_ids: []}); await flush();
    assert.equal(app.favoritesTab.hidden, true);
    const originalOrder = app.grid().children.map(card => card.dataset.channelId);
    app.grid().children[1].querySelector('.raid-browser-pin').handlers.click();
    assert.equal(app.favoritesTab.hidden, false);
    assert.equal(app.requests.length, 1);
    assert.deepEqual(app.grid().children.map(card => card.dataset.channelId), originalOrder);
    app.grid().children[1].querySelector('.raid-browser-pin').handlers.click();
    assert.equal(app.favoritesTab.hidden, true);
    assert.equal(app.requests.length, 1);
});

test('tag ellipsis sits after the last whole first-line tag with space reserved for it', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [Object.assign(channel(), {tags: ['Art', 'English', 'VTuber']})], cursor: ''}); await flush();
    const tags = app.grid().children[0].querySelector('.raid-browser-tags');
    tags.clientWidth = 160; tags.scrollHeight = 50;
    tags.getBoundingClientRect = () => ({left: 0, right: 160, top: 0, bottom: 22});
    tags.children[0].getBoundingClientRect = () => ({left: 0, right: 50, top: 0, bottom: 22});
    tags.children[1].getBoundingClientRect = () => ({left: 55, right: 115, top: 0, bottom: 22});
    tags.children[2].getBoundingClientRect = () => ({left: 0, right: 70, top: 27, bottom: 49});
    app.resize(); await flush();
    assert.equal(tags.style['--raid-tags-more-left'], '120px');
    assert.equal(tags.children[1].classes.has('raid-browser-tag-overflowed'), false);
    assert.equal(tags.children[2].classes.has('raid-browser-tag-overflowed'), true);
});

test('card spacing is compact and Raid is anchored to the collapsed row height', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel()], cursor: ''}); await flush();
    assert.equal(app.grid().style.gridAutoRows, '352px');
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.match(styles, /\.raid-browser-dialog:not\(\.is-list-view\) \.raid-browser-start-raid \{ position: absolute; top: calc\(var\(--raid-browser-row-height\) - 41px\)/);
});

test('channel profile pictures appear immediately before the name inside its link', async () => {
    const app = setup(); app.opener.handlers.click();
    const url = 'https://static-cdn.jtvnw.net/jtv_user_pictures/viewer.png';
    app.requests[0].respond({channels: [Object.assign(channel(), {profile_image_url: url})], cursor: ''}); await flush();
    const name = app.grid().children[0].querySelector('.raid-browser-name');
    assert.equal(name.children[0].className, 'raid-browser-avatar');
    assert.equal(name.children[0].src, url);
    assert.equal(name.children[1].textContent, 'Viewer2');
    assert.match(name.href, /twitch.tv\/viewer2$/);
});

test('category arrows navigate every result and return focus without reopening the picker', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [], cursor: ''}); await flush();
    app.categorySearch.handlers.focus();
    app.requests[1].respond({games: [{id: '10', name: 'First'}, {id: '20', name: 'Second'}, {id: '30', name: 'Third'}], more_games: []});
    await flush();
    app.categorySearch.focus = () => { app.categorySearch.focused = true; app.categorySearch.handlers.focus(); };
    app.categorySearch.handlers.keydown({key: 'ArrowDown', preventDefault() {}});
    const [first, second, last] = app.categoryOptions.children;
    assert.equal(first.focused, true);
    assert.equal(first.attributes['data-hover-pointer-only'], '');
    const key = (target, key) => app.categoryOptions.handlers.keydown({target, key, preventDefault() {}, stopPropagation() {}});
    key(first, 'ArrowDown'); assert.equal(second.focused, true);
    key(second, 'ArrowDown'); assert.equal(last.focused, true);
    key(last, 'ArrowUp'); assert.equal(second.focused, true);
    key(second, 'Home'); assert.equal(first.focused, true);
    key(first, 'ArrowUp'); assert.equal(app.categorySearch.focused, true);
    assert.equal(app.requests.length, 2);
    key(first, 'End'); assert.equal(last.focused, true);
    key(last, 'Enter');
    assert.equal(app.fields.category_id.value, '30');
    assert.equal(app.categorySearch.value, 'Third');
    assert.equal(app.categoryOptions.hidden, true);
    assert.equal(app.requests.length, 3);
    assert.equal(app.requests[2].url.searchParams.get('category_id'), '30');
});

test('category More results and Escape work with keyboard navigation', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [], cursor: ''}); await flush();
    app.categorySearch.handlers.focus();
    app.requests[1].respond({games: [{id: '10', name: 'First'}], more_games: [{id: '20', name: 'More'}]}); await flush();
    app.categorySearch.handlers.keydown({key: 'ArrowUp', preventDefault() {}});
    const more = app.categoryOptions.children.at(-1);
    assert.equal(more.focused, true);
    assert.equal(more.attributes['data-hover-pointer-only'], '');
    app.categoryOptions.handlers.keydown({target: more, key: 'Enter', preventDefault() {}});
    assert.equal(app.categoryOptions.children.length, 2);
    assert.equal(app.categoryOptions.children[1].focused, true);
    app.categoryOptions.handlers.keydown({target: app.categoryOptions.children[1], key: 'Escape', preventDefault() {}, stopPropagation() {}});
    assert.equal(app.categoryOptions.hidden, true);
    assert.equal(app.categorySearch.focused, true);
});

test('category picker reuses ranked game search and only filters after selecting an option', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [], cursor: ''}); await flush();
    app.categorySearch.value = 'Retro'; app.categorySearch.handlers.focus();
    assert.equal(app.requests[1].url.pathname, '/channel/api/games');
    assert.equal(app.requests[1].url.searchParams.get('query'), 'Retro');
    app.requests[1].respond({games: [{id: '123', name: 'Retro'}], more_games: []}); await flush();
    assert.equal(app.fields.category_id.value, '');
    assert.equal(app.categoryOptions.children.length, 1);
    app.categoryOptions.children[0].handlers.click();
    assert.equal(app.fields.category_id.value, '123');
    assert.equal(app.requests[2].url.searchParams.get('category_id'), '123');
    assert.equal(app.categoryOptions.hidden, true);
});

test('saved lists use separate Favorites and Blacklist tabs with keyboard navigation', () => {
    const app = setup();
    app.blacklistTab.handlers.click();
    assert.equal(app.favoritePanel.hidden, true);
    assert.equal(app.blacklistPanel.hidden, false);
    assert.equal(app.blacklistTab.attributes['aria-selected'], 'true');
    app.blacklistTab.handlers.keydown({key: 'ArrowLeft', preventDefault() {}});
    assert.equal(app.favoritePanel.hidden, false);
    assert.equal(app.blacklistPanel.hidden, true);
    assert.equal(app.favoriteTab.focused, true);
});

test('raid button confirms, prevents duplicate requests, and transitions only after Twitch accepts', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel()], cursor: ''}); await flush();
    const button = app.grid().children[0].querySelector('.raid-browser-start-raid');
    app.confirm(false); await button.handlers.click();
    assert.equal(app.requests.length, 1);
    app.confirm(true); const pending = button.handlers.click();
    assert.equal(app.requests[1].options.method, 'POST');
    assert.equal(app.requests[1].options.body.get('target_id'), '2');
    assert.equal(button.disabled, true);
    await button.handlers.click(); assert.equal(app.requests.length, 2);
    app.requests[1].respond({raid: {target_id: '2', login: 'viewer2'}}); await pending;
    assert.equal(app.dialog.open, false);
    assert.equal(app.events[0].type, 'dashboard-raid-started');
    assert.equal(app.events[0].detail.raid.target_id, '2');
});

test('failed raid request stays in the browser without an arrival animation', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [channel()], cursor: ''}); await flush();
    const button = app.grid().children[0].querySelector('.raid-browser-start-raid');
    const pending = button.handlers.click();
    app.requests[1].respond({detail: 'Reconnect Twitch.'}, false); await pending;
    assert.equal(app.dialog.open, true);
    assert.equal(button.disabled, false);
    assert.equal(app.events.length, 0);
    assert.equal(app.status.textContent, 'Reconnect Twitch.');
});

test('team stays in the header while Raid sits beside tags in the footer', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: [Object.assign(channel(), {viewers: 42, teams: ['Our team'], started_at: new Date(Date.now() - 3661000).toISOString()})], cursor: ''});
    await flush();
    const card = app.grid().children[0];
    assert.equal(card.querySelector('.raid-browser-thumbnail').querySelector('.raid-browser-viewers').textContent, '42 viewers');
    assert.equal(card.querySelector('.raid-browser-live-time').textContent, '1:01:01');
    assert.equal(card.querySelector('.raid-browser-thumbnail').querySelector('.raid-browser-live-time').textContent, '1:01:01');
    assert.equal(card.querySelector('.raid-browser-category-name').textContent.includes('viewers'), false);
    const heading = card.querySelector('.raid-browser-channel-heading');
    const actions = heading.querySelector('.raid-browser-stream-actions');
    assert.deepEqual(actions.children.map(child => child.className), ['raid-browser-team']);
    assert.equal(actions.children[0].textContent, 'Our team');
    assert.deepEqual(heading.children.slice(-3).map(child => child.className), ['raid-browser-stream-actions', 'raid-browser-pin', 'raid-browser-more']);
    const footer = card.querySelector('.raid-browser-channel-footer');
    assert.deepEqual(footer.children.map(child => child.className), ['raid-browser-tags', 'raid-browser-start-raid']);
    assert.equal(footer.children[1].textContent, 'Raid');
    assert.equal(footer.children[1].disabled, false);
    app.listView.handlers.click(); await flush();
    assert.ok(app.grid().children[0].querySelector('.raid-browser-live-time'));
    assert.equal(app.grid().children[0].querySelector('.raid-browser-channel-footer').children[1].textContent, 'Raid');
});

test('medium cards use at most four columns and medium rows use the previous large height', async () => {
    const app = setup(); app.results.clientWidth = 1500; app.opener.handlers.click();
    app.requests[0].respond({channels: Array.from({length: 30}, (_, index) => channel(String(index))), cursor: ''});
    await flush();
    assert.equal(app.grid().style.gridTemplateColumns, 'repeat(4,minmax(0,1fr))');
    app.listView.handlers.click(); await flush();
    assert.equal(app.grid().style.gridAutoRows, '156px');
});

test('three size steps resize virtualized cards and rows and persist the selection', async () => {
    const app = setup(); app.opener.handlers.click();
    app.requests[0].respond({channels: Array.from({length: 100}, (_, index) => channel(String(index))), cursor: ''});
    await flush();
    assert.equal(app.sizeSlider.attributes['aria-valuetext'], 'Medium');
    app.sizeSlider.value = '0'; app.sizeSlider.handlers.input(); await flush();
    assert.equal(app.sizeSlider.attributes['aria-valuetext'], 'Small');
    assert.equal(app.grid().style.gridTemplateColumns, 'repeat(4,minmax(0,1fr))');
    app.sizeSlider.value = '2'; app.sizeSlider.handlers.input(); await flush();
    assert.equal(app.sizeSlider.attributes['aria-valuetext'], 'Large');
    assert.equal(app.grid().style.gridTemplateColumns, 'repeat(2,minmax(0,1fr))');
    assert.equal(app.sizeSlider.attributes['aria-valuetext'], 'Large');
    app.listView.handlers.click(); await flush();
    assert.equal(app.grid().style.gridAutoRows, '220px');
    assert.equal(app.grid().style['--raid-browser-row-height'], '220px');
    app.sizeSlider.value = '0'; app.sizeSlider.handlers.input(); await flush();
    assert.equal(app.grid().style.gridAutoRows, '116px');
    assert.equal(app.grid().style['--raid-browser-row-height'], '116px');
    const refreshed = setup(app.storage);
    assert.equal(refreshed.sizeSlider.attributes['aria-valuetext'], 'Small');
    assert.equal(refreshed.sizeSlider.value, '0');
});
