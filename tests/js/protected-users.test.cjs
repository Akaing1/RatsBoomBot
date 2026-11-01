const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('cached suggestions rank exact names before relationships and other partial matches', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage();
        await page.setContent(`<form data-protected-user-search data-search-url="/search"><input name="query"><p data-protected-search-message></p></form>
            <form data-protected-user-result hidden><input data-protected-result-id><strong data-protected-result-label></strong><button data-protected-add>Add</button></form>`);
        await page.evaluate(() => {
            window.fetch = async url => !url.includes('cached_only')
                ? new Promise(resolve => { window.respond = users => resolve({ok: true, json: async () => ({users})}); })
                : ({ok: true, json: async () => ({users: [
                {id: 'near', login: 'viewernamf', display_name: 'viewernamf'},
                {id: 'partial', login: 'viewername_other', display_name: 'viewername_other'},
                {id: 'related', login: 'viewername_friend', display_name: 'viewername_friend', related: true},
                {id: 'display', login: 'otherlogin', display_name: 'Viewername'},
                {id: 'exact', login: 'viewername', display_name: 'Different'},
            ]})});
        });
        await page.addScriptTag({path: 'web/static/js/protected-users.js'});
        await page.locator('input[name=query]').fill('viewername');
        assert.deepEqual(await page.locator('.protected-user-results [data-protected-result-id]').evaluateAll(inputs => inputs.map(input => input.value)),
            ['display', 'exact', 'related', 'partial', 'near']);
        await page.locator('[data-protected-user-search]').dispatchEvent('submit');
        await page.evaluate(() => respond([
            {id: 'remote', login: 'viewername_new', display_name: 'viewername_new'},
        ]));
        assert.deepEqual(await page.locator('.protected-user-results [data-protected-result-id]').evaluateAll(inputs => inputs.map(input => input.value)),
            ['related', 'remote'], 'Twitch results add to cached relationships even when the response omits those people');
        await page.locator('[data-protected-user-search]').dispatchEvent('submit');
        await page.evaluate(() => respond([]));
        assert.deepEqual(await page.locator('.protected-user-results [data-protected-result-id]').evaluateAll(inputs => inputs.map(input => input.value)),
            ['related'], 'An empty Twitch response must not clear matching followers');
    } finally { await browser.close(); }
});

test('user searches select available results with arrows and Enter while keeping input focus', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage();
        await page.clock.install();
        await page.clock.pauseAt(new Date(Date.now() + 1000));
        const widget = blacklist => `<section id="${blacklist ? 'blacklist' : 'protected'}">
            <form data-protected-user-search data-search-url="/search"><input name="query"><button>Search</button><p data-protected-search-message></p></form>
            <form data-protected-user-result ${blacklist ? 'data-user-search-blacklist' : ''} hidden>
                <input type="hidden" name="user_id" data-protected-result-id>
                <input type="hidden" name="username" data-protected-result-login>
                <strong data-protected-result-label></strong><button data-protected-add>Add</button>
            </form></section>`;
        await page.setContent(`<div data-settings-book>${widget(false)}${widget(true)}<div data-queue-blacklist-members><input name="username" value="viewer2"></div></div>`);
        await page.evaluate(() => {
            window.users = [1, 2, 3].map(n => ({id: `user${n}`, login: `viewer${n}`, display_name: `Viewer${n}`, already_protected: n === 2}));
            window.fetch = async url => url.includes('cached_only')
                ? {ok: true, json: async () => ({users})}
                : new Promise(resolve => { window.respond = incoming => resolve({ok: true, json: async () => ({users: incoming})}); });
            document.addEventListener('submit', event => {
                if (!event.target.matches('[data-protected-user-result]')) return;
                event.preventDefault();
                window.submitted = Object.fromEntries(new FormData(event.target));
            });
        });
        await page.addScriptTag({path: 'web/static/js/protected-users.js'});
        for (const kind of ['protected', 'blacklist']) {
            const section = page.locator(`#${kind}`);
            const input = section.locator('input[name="query"]');
            const selected = section.locator('.is-keyboard-selected [data-protected-result-id]');
            await input.fill('viewer');
            await input.press('ArrowDown');
            assert.equal(await selected.inputValue(), 'user1');
            await input.press('ArrowDown');
            assert.equal(await selected.inputValue(), 'user3', 'Unavailable results are skipped');
            await input.press('ArrowDown');
            assert.equal(await selected.inputValue(), 'user1', 'Navigation wraps');
            await input.press('ArrowUp');
            assert.equal(await selected.inputValue(), 'user3');
            assert.equal(await input.evaluate(element => element === document.activeElement), true);
            await input.press('Enter');
            assert.deepEqual(await page.evaluate(() => submitted), {user_id: 'user3', username: 'viewer3'});
            await input.fill('viewe');
            assert.equal(await selected.count(), 0, 'Changing the query clears selection');
            await input.press('ArrowDown');
            await page.clock.fastForward(1000);
            await section.locator('[data-protected-user-search]').dispatchEvent('submit');
            await page.evaluate(() => respond([users[2], users[0]]));
            assert.equal(await selected.inputValue(), 'user1', 'Async reordering preserves the selected identity');
            await input.press('Escape');
            assert.equal(await section.locator('[data-protected-user-result]').count(), 0);
            assert.equal(await input.getAttribute('aria-expanded'), 'false');
        }
    } finally { await browser.close(); }
});

test('protected user search waits for idle typing, limits results, and ignores stale responses', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage();
        await page.route('http://settings.test/**', route => route.fulfill({body: '<html></html>', contentType: 'text/html'}));
        await page.goto('http://settings.test/settings');
        await page.clock.install({time: new Date('2026-01-01T00:00:00Z')});
        await page.clock.pauseAt(new Date('2026-01-01T00:00:01Z'));
        const editor = `<div data-settings-book data-channel="1">
            <form data-protected-user-search data-search-url="/search"><input name="query"><button>Search</button><p data-protected-search-message></p></form>
            <form data-protected-user-result hidden><input type="hidden" data-protected-result-id><strong data-protected-result-label></strong><small data-protected-result-user-id></small><button data-protected-add>Add User</button></form>
        </div><button id="outside">Outside</button>`;
        await page.setContent(editor);
        await page.evaluate(() => {
            window.requests = [];
            document.addEventListener('submit', event => {
                if (event.target.matches('[data-protected-user-result]')) {
                    event.preventDefault();
                    window.addedId = event.target.querySelector('[data-protected-result-id]').value;
                }
            });
            // Deliberately ignore abort, to also verify the revision guard.
            window.fetch = (url, options) => url.includes('cached_only=true') && requests.length ? Promise.resolve({ok: true, json: async () => ({users: []})}) : new Promise(resolve => requests.push({url, signal: options.signal, respond: users => resolve({ok: true, json: async () => ({users})})}));
        });
        await page.addScriptTag({path: 'web/static/js/protected-users.js'});
        const input = page.locator('input[name="query"]');
        const results = page.locator('[data-protected-user-result]');
        assert.match(await page.evaluate(() => requests[0].url), /query=&cached_only=true/);
        await input.focus();
        assert.equal(await results.count(), 0, 'Focus alone does not show suggestions');
        await input.fill('v');
        await input.fill('vi');
        await input.fill('vie');
        assert.equal(await page.evaluate(() => requests.length), 1, 'Typing does not start a request per keystroke');
        assert.equal(await page.evaluate(() => (requests[0].signal?.aborted || false)), false, 'Typing does not cancel the cached-name preload');
        await page.evaluate(() => requests[0].respond([
            {id: 'cached', display_name: 'Viewer', login: 'viewer'},
            {id: 'cached-add', display_name: 'Cached Viewer', login: 'cachedviewer'},
        ]));
        assert.equal(await results.first().locator('[data-protected-result-id]').inputValue(), 'cached');
        await input.fill('view');
        assert.equal(await results.first().locator('[data-protected-result-id]').inputValue(), 'cached', 'Cached matches update synchronously while typing');
        await input.fill('viewr');
        assert.equal(await results.first().locator('[data-protected-result-id]').inputValue(), 'cached', 'Local suggestions include fuzzy matches');
        await page.clock.fastForward(999);
        assert.equal(await page.evaluate(() => requests.length), 1);
        await page.clock.fastForward(1);
        assert.equal(await page.evaluate(() => requests.length), 2);
        assert.equal(await results.count(), 1, 'Cached matches remain usable while Twitch loads');
        await input.fill('  @VIEWR  ');
        await page.clock.fastForward(1000);
        assert.equal(await page.evaluate(() => requests[1].signal.aborted), false, 'Equivalent text edits preserve the pending Twitch lookup');
        assert.equal(await page.evaluate(() => requests.length), 2, 'Equivalent text does not schedule duplicate searches');

        await input.fill('newviewer');
        assert.equal(await page.evaluate(() => requests[1].signal.aborted), true);
        await page.clock.fastForward(1000);
        await page.evaluate(() => requests[2].respond(Array.from({length: 6}, (_, index) => ({id: String(index), display_name: 'New Viewer', login: 'newviewer' + index, already_protected: index === 1}))));
        assert.equal(await results.count(), 5);
        assert.equal(await results.first().locator('[data-protected-result-label]').textContent(), 'New Viewer (newviewer0)');
        assert.equal(await results.nth(1).locator('[data-protected-add]').isDisabled(), true);
        await page.evaluate(() => requests[1].respond([{id: 'old', display_name: 'Old Viewer', login: 'oldviewer'}]));
        assert.equal(await results.first().locator('[data-protected-result-id]').inputValue(), '0');
        await input.fill('manualviewer');
        await page.locator('[data-protected-user-search] button').click();
        assert.equal(await page.evaluate(() => requests.length), 4, 'Search starts Twitch lookup without waiting');
        await page.evaluate(() => requests[3].respond([{id: 'manual', display_name: 'Manual', login: 'manual'}]));
        assert.equal(await results.first().locator('[data-protected-result-id]').inputValue(), 'manual');
        await input.fill('cachedviewer');
        assert.equal(await results.first().locator('[data-protected-result-id]').inputValue(), 'cached-add');
        await page.clock.fastForward(1000);
        await input.press('ArrowDown');
        assert.equal(await page.evaluate(() => requests[4].signal.aborted), true, 'Arrow navigation interrupts the pending Twitch lookup');
        await page.evaluate(() => requests[4].respond([{id: 'late-add', display_name: 'Late', login: 'lateviewer'}]));
        assert.equal(await results.first().locator('[data-protected-result-id]').inputValue(), 'cached-add', 'Late replies leave the prepopulated selection in place');
        await input.press('Enter');
        assert.equal(await page.evaluate(() => requests[4].signal.aborted), true);
        assert.equal(await page.evaluate(() => window.addedId), 'cached-add');
        await page.evaluate(() => requests[4].respond([{id: 'late-add', display_name: 'Late', login: 'lateviewer'}]));
        assert.equal(await results.first().locator('[data-protected-result-id]').inputValue(), 'cached-add');
        await input.fill('leavingviewer');
        await page.locator('#outside').click();
        await page.clock.fastForward(1500);
        assert.equal(await page.evaluate(() => requests.length), 5, 'Clicking away cancels the scheduled Twitch lookup');
        assert.equal(await results.count(), 0);
        await input.fill('remoteviewer');
        await page.clock.fastForward(1000);
        await page.locator('#outside').click();
        assert.equal(await page.evaluate(() => requests[5].signal.aborted), true);
        await page.evaluate(() => requests[5].respond([{id: 'late-remote', display_name: 'Late', login: 'lateviewer'}]));
        assert.equal(await results.count(), 0, 'Late responses do not reopen dismissed results');
        await page.reload();
        await page.setContent(editor);
        await page.evaluate(() => { window.fetch = () => new Promise(() => {}); });
        await page.addScriptTag({path: 'web/static/js/protected-users.js'});
        await page.locator('input[name="query"]').fill('cachedviewer');
        assert.equal(await page.locator('[data-protected-user-result]').first().locator('[data-protected-result-id]').inputValue(), 'cached-add', 'Previously loaded names match immediately after refresh, before any server reply');

    } finally { await browser.close(); }
});


test('protected and blacklist searches share cached names and submit the appropriate identity', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage();
        const widget = blacklist => `<section id="${blacklist ? 'blacklist' : 'protected'}">
            <form data-protected-user-search data-search-url="/search"><input name="query"><button>Search</button><p data-protected-search-message></p></form>
            <form data-protected-user-result ${blacklist ? 'data-user-search-blacklist' : ''} action="${blacklist ? '/channel/viewer-queue/blacklist' : '/channel/protected-users/add'}" hidden>
                <input type="hidden" ${blacklist ? '' : 'name="user_id"'} data-protected-result-id>
                ${blacklist ? '<input type="hidden" name="action" value="add"><input type="hidden" name="username" data-protected-result-login>' : ''}
                <strong data-protected-result-label></strong><small data-protected-result-user-id></small><button data-protected-add>Add User</button>
            </form></section>`;
        await page.setContent(`<div data-settings-book data-channel="1">${widget(false)}${widget(true)}<div data-queue-blacklist-members><input name="username" value="blocked"></div></div>`);
        await page.evaluate(() => {
            window.reads = 0;
            window.fetch = async () => {
                window.reads++;
                return {ok: true, json: async () => ({users: [
                    {id: '1', login: 'viewer', display_name: 'Viewer', already_protected: true},
                    {id: '2', login: 'blocked', display_name: 'Blocked', already_protected: false},
                ]})};
            };
            document.addEventListener('submit', event => {
                if (event.target.matches('[data-protected-user-result]')) {
                    event.preventDefault();
                    window.submitted = Object.fromEntries(new FormData(event.target));
                }
            });
        });
        await page.addScriptTag({path: 'web/static/js/protected-users.js'});
        assert.equal(await page.evaluate(() => window.reads), 1, 'Both fields share the initial cached-list request');
        await page.locator('#protected input[name="query"]').fill('viewer');
        assert.equal(await page.locator('#protected [data-protected-add]').isDisabled(), true);
        await page.locator('#blacklist input[name="query"]').fill('viewer');
        assert.equal(await page.locator('#blacklist [data-protected-add]').isEnabled(), true);
        assert.equal(await page.locator('#blacklist [data-protected-add]').textContent(), 'Blacklist');
        await page.locator('#blacklist [data-protected-add]').click();
        assert.deepEqual(await page.evaluate(() => window.submitted), {action: 'add', username: 'viewer'});
        await page.locator('#blacklist input[name="query"]').fill('blocked');
        assert.equal(await page.locator('#blacklist [data-protected-add]').isDisabled(), true);
        assert.equal(await page.locator('#blacklist [data-protected-add]').textContent(), 'Already blacklisted');
        await page.evaluate(() => {
            document.querySelector('[data-queue-blacklist-members]').replaceChildren();
            const form = document.createElement('form');
            form.dataset.settingsImmediateAction = 'queue-blacklist';
            document.querySelector('[data-settings-book]').dispatchEvent(new CustomEvent('settings-saved', {detail: {form, snapshot: JSON.stringify([['username', 'blocked'], ['action', 'remove']])}}));
        });
        await page.locator('#blacklist input[name="query"]').fill('block');
        assert.equal(await page.locator('#blacklist [data-protected-add]').isEnabled(), true, 'Membership refreshes after removing a blacklisted user');

    } finally { await browser.close(); }
});


test('missing pictures load in the background and both searches share one cached lookup', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage();
        await page.route('http://settings.test/**', route => route.fulfill({body: '<html></html>', contentType: 'text/html'}));
        await page.goto('http://settings.test/settings');
        await page.clock.install({time: new Date('2026-01-01T00:00:00Z')});
        await page.clock.pauseAt(new Date('2026-01-01T00:00:01Z'));
        const widget = key => `<section id="${key}"><form data-protected-user-search data-search-url="/channel/protected-users/search"><input name="query"><button>Search</button><p data-protected-search-message></p></form><form data-protected-user-result hidden><input type="hidden" data-protected-result-id><span><img data-protected-result-avatar width="28" height="28" hidden></span><strong data-protected-result-label></strong><small data-protected-result-user-id></small><button data-protected-add>Add User</button></form></section>`;
        await page.setContent(`<div data-settings-book data-channel="1">${widget('first')}${widget('second')}</div>`);
        await page.evaluate(() => {
            window.pictureLoads = [];
            window.cacheWrites = 0;
            const write = Storage.prototype.setItem;
            Storage.prototype.setItem = function (...args) { cacheWrites++; return write.apply(this, args); };
            window.fetch = (url) => url.includes('/profiles?')
                ? new Promise(resolve => pictureLoads.push({url, respond: () => resolve({ok: true, json: async () => ({profiles: [{id: '123', profile_image_url: 'https://example.test/avatar.png'}]})})}))
                : Promise.resolve({ok: true, json: async () => ({users: [{id: '123', login: 'viewer', display_name: 'Viewer', related: true}]})});
        });
        await page.addScriptTag({path: 'web/static/js/protected-users.js'});
        await page.locator('#first input[name="query"]').fill('v');
        assert.equal(await page.locator('#first [data-protected-result-label]').textContent(), 'Viewer', 'The name appears before picture loading finishes');
        await page.clock.fastForward(1);
        assert.equal(await page.evaluate(() => pictureLoads.length), 1);
        await page.locator('#second input[name="query"]').fill('v');
        await page.clock.fastForward(1);
        assert.equal(await page.evaluate(() => pictureLoads.length), 1, 'The second field shares the in-flight picture lookup');
        await page.evaluate(() => pictureLoads[0].respond());
        assert.equal(await page.locator('#second [data-protected-result-avatar]').getAttribute('src'), 'https://example.test/avatar.png');
        assert.equal(await page.locator('#second [data-protected-result-avatar]').isVisible(), true);
        await page.locator('#second input[name="query"]').fill('view');
        assert.equal(await page.locator('#second [data-protected-result-avatar]').getAttribute('src'), 'https://example.test/avatar.png');
        assert.equal(await page.evaluate(() => pictureLoads.length), 1, 'Subsequent input reuses the picture');
        assert.equal(await page.evaluate(() => cacheWrites), 2, 'One shared write for names and one for the completed picture batch');
    } finally { await browser.close(); }
});
