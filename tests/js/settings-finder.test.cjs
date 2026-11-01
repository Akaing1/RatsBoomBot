const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('settings hashes use stable short names within their section', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({reducedMotion: 'reduce'});
        let extra = false;
        const html = () => `<div data-settings-book data-selected="events" data-channel="links"><nav class="settings-menu">${['events', 'timers'].map(key => `<details class="settings-menu-section" open><summary><a data-settings-tab="${key}">${key}</a><span class="settings-dirty-dot" hidden></span></summary><div data-settings-links="${key}"></div></details>`).join('')}</nav>
            <main class="settings-main settings-pages"><section data-settings-page="events"><header class="settings-page-heading"><h3>Events</h3></header>${extra ? '<section class="settings-group"><header class="settings-group-heading"><h4>New feature</h4></header></section>' : ''}<section class="settings-group" id="settings-group-shoutouts"><header class="settings-group-heading"><h4>Shoutouts</h4></header><article class="profile-setting-card" data-setting-key="shoutout_messages.with_game"><div class="toggle-card-heading"><h4>Shoutout with game</h4></div></article></section></section>
            <section data-settings-page="timers" hidden><header class="settings-page-heading"><h3>Timers</h3></header><form class="settings-timer-manager"><section class="panel"><h3>Create timer</h3></section><section class="panel"><h3>Your timers</h3></section></form></section></main>
            <aside data-settings-finder><input><p data-settings-result-count></p><div data-settings-results></div></aside></div>`;
        await page.route('http://settings.test/**', route => route.fulfill({body: html(), contentType: 'text/html'}));
        const scripts = async () => {
            for (const file of ['channel-settings.js', 'settings-finder.js']) await page.addScriptTag({path: `web/static/js/${file}`});
        };
        await page.goto('http://settings.test/channel/settings?section=events#shoutouts');
        await scripts();
        assert.ok(page.url().endsWith('#shoutouts'));
        const firstIds = await page.locator('[data-settings-location]').evaluateAll(nodes => nodes.map(node => node.dataset.settingsLocation));
        assert.ok(firstIds.includes('settings-timers-create-timer'));
        assert.ok(firstIds.includes('settings-timers-your-timers'));
        assert.equal(firstIds.some(id => /^settings-location-\d+$/.test(id)), false);
        const settingId = await page.locator('[data-setting-key]').getAttribute('id');
        assert.equal(settingId, 'settings-events-shoutout-messages-with-game');
        extra = true;
        await page.reload();
        await scripts();
        const nextIds = await page.locator('[data-settings-location]').evaluateAll(nodes => nodes.map(node => node.dataset.settingsLocation));
        assert.ok(firstIds.every(id => nextIds.includes(id)));
        assert.equal(await page.locator('[data-setting-key]').getAttribute('id'), settingId);
        assert.ok(page.url().endsWith('#shoutouts'));
        await page.locator('[data-settings-tab="timers"]').click();
        await page.locator('[data-settings-location="settings-timers-create-timer"]').click();
        assert.ok(page.url().endsWith('#create-timer'));
        await page.goto('http://settings.test/channel/settings?section=timers#your-timers');
        await scripts();
        assert.ok(page.url().endsWith('?section=timers#your-timers'));
        assert.equal(await page.locator('[data-settings-page="timers"]').isVisible(), true);
        await page.goto('http://settings.test/channel/settings?section=timers#settings-timers-your-timers');
        await scripts();
        assert.ok(page.url().endsWith('?section=timers'));
        const internal = page.locator('[data-settings-location="settings-timers-your-timers"]');
        await page.evaluate(() => {
            const target = document.querySelector('[data-settings-page="timers"] .settings-timer-manager>.panel:last-child');
            document.querySelector('[data-settings-book]').dispatchEvent(new CustomEvent('settings-location-changed', {detail: target}));
        });
        assert.ok(page.url().endsWith('?section=timers#your-timers'));
        await internal.click();
        assert.ok(page.url().endsWith('?section=timers#your-timers'));
    } finally { await browser.close(); }
});

test('settings history restores categories and subsections without losing drafts or adding hover entries', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({viewport: {width: 1300, height: 900}, reducedMotion: 'reduce'});
        const html = `<style>.settings-menu{position:fixed;left:0;top:0;width:180px}.settings-main{margin-left:220px}.settings-group{height:350px}body{padding-bottom:700px}[hidden]{display:none!important}</style>
            <div data-settings-book data-selected="events" data-channel="history"><nav class="settings-menu">${['events', 'chat'].map(key => `<details class="settings-menu-section" open><summary><a href="?section=${key}" data-settings-tab="${key}">${key}</a><span class="settings-dirty-dot" hidden></span></summary><div data-settings-links="${key}"></div></details>`).join('')}</nav>
            <main class="settings-main settings-pages">${['events', 'chat'].map(key => `<section data-settings-page="${key}"><header class="settings-page-heading"><h3>${key}</h3></header>${['first', 'second'].map(name => `<section class="settings-group" id="${key}-${name}"><header class="settings-group-heading" id="${key}-${name}-heading"><h4>${name}</h4></header><article class="profile-setting-card"><form method="post"><textarea>${key} ${name}</textarea></form></article></section>`).join('')}</section>`).join('')}</main>
            <aside data-settings-finder><input><p data-settings-result-count></p><div data-settings-results></div></aside></div>`;
        await page.route('http://settings.test/**', route => route.fulfill({body: html, contentType: 'text/html'}));
        const loadScripts = async () => {
            for (const file of ['channel-settings.js', 'settings-finder.js', 'settings-menu-highlight.js']) await page.addScriptTag({path: `web/static/js/${file}`});
        };
        await page.goto('http://settings.test/channel/settings?section=events');
        await loadScripts();
        await page.locator('#events-first textarea').fill('Unsaved draft');
        const initialLength = await page.evaluate(() => history.length);
        await page.locator('[data-settings-tab="chat"]').click();
        await page.waitForURL('**/settings?section=chat');
        assert.equal(await page.evaluate(() => history.length), initialLength + 1);
        await page.locator('[data-settings-location="chat-second-heading"]').click();
        await page.waitForURL('**/settings?section=chat#second');
        assert.equal(await page.evaluate(() => history.length), initialLength + 2);
        await page.goBack();
        await page.waitForURL('**/settings?section=chat');
        assert.equal(await page.locator('[data-settings-page="chat"]').isVisible(), true);
        await page.goBack();
        await page.waitForURL('**/settings?section=events');
        assert.equal(await page.locator('#events-first textarea').inputValue(), 'Unsaved draft');
        await page.goForward();
        await page.goForward();
        await page.waitForURL('**/settings?section=chat#second');
        assert.equal(await page.locator('[data-settings-location="chat-second-heading"]').getAttribute('aria-current'), 'location');
        await page.locator('#chat-first textarea').hover();
        await page.waitForURL('**/settings?section=chat#first');
        assert.equal(await page.evaluate(() => history.length), initialLength + 2);
        await page.reload();
        await loadScripts();
        assert.equal(await page.locator('[data-settings-page="chat"]').isVisible(), true);
        await page.waitForFunction(() => document.querySelector('[data-settings-location="chat-first-heading"]').getAttribute('aria-current') === 'location');
        await page.evaluate(() => {
            sessionStorage.setItem('ratsboombot-settings:history', 'chat');
            sessionStorage.setItem('ratsboombot-settings:history:location', '#first');
            sessionStorage.setItem('ratsboombot-settings:history:scroll', JSON.stringify({section: 'chat', y: 500, panelY: 100}));
        });
        await page.goto('http://settings.test/channel/settings');
        await loadScripts();
        await page.waitForURL('**/settings?section=events');
        assert.equal(await page.locator('[data-settings-page="events"]').isVisible(), true);
        assert.equal(await page.evaluate(() => scrollY), 0);
    } finally { await browser.close(); }
});

test('expandable settings menu and search preserve drafts and open matching groups', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage();
        await page.route('http://settings.test/**', route => route.fulfill({body: '<html></html>', contentType: 'text/html'}));
        await page.goto('http://settings.test/channel/settings');
        await page.setContent(`<div data-settings-book data-selected="events" data-channel="1">
            <nav class="settings-menu">${['events', 'chat'].map(key => `<details class="settings-menu-section"><summary><a href="?section=${key}" data-settings-tab="${key}">${key}<span class="settings-dirty-dot" hidden></span></a></summary><div data-settings-links="${key}"></div></details>`).join('')}</nav>
            <div class="settings-pages">${[['events', 'Follow message', 'follow'], ['chat', 'Lurk message', 'lurk']].map(([key, title, setting]) => `
                <section data-settings-page="${key}"><div class="settings-page-heading"><h3>${key}</h3></div>
                <section class="settings-group"><header class="settings-group-heading"><h4>${title} group</h4></header>
                    <article class="profile-setting-card" data-setting-key="${setting}"><form method="post">
                    <div class="toggle-card-heading"><h4>${title}</h4></div><div class="settings-field-body"><textarea name="value">private_saved_message</textarea></div></form></article>
                </section></section>`).join('')}</div>
            <aside data-settings-finder hidden><input><p data-settings-result-count></p><div data-settings-results></div></aside>
        </div>`);
        await page.evaluate(() => {
            window.scrolledSettings = [];
            const scroll = Element.prototype.scrollIntoView;
            Element.prototype.scrollIntoView = function(options) {
                window.scrolledSettings.push({key: this.dataset.settingsPage || this.dataset.settingKey, block: options?.block});
                return scroll.call(this, options);
            };
        });
        for (const file of ['channel-settings.js', 'settings-finder.js']) {
            await page.addScriptTag({content: fs.readFileSync(`web/static/js/${file}`, 'utf8')});
        }
        const drawer = page.locator('[data-settings-finder]');
        const search = page.locator('[data-settings-finder] input');
        assert.equal(await drawer.isVisible(), true);
        assert.equal(await page.locator('[data-settings-tab="events"]').getAttribute('aria-current'), 'page');
        assert.match(await page.locator('[data-settings-links="events"]').textContent(), /Follow message group/);
        await page.locator('.settings-menu-section').first().locator('summary').evaluate(node => node.click());
        await page.locator('[data-settings-links="events"]').waitFor({state: 'hidden'});
        assert.equal(await page.locator('[data-settings-page="events"]').isVisible(), true);
        await page.locator('.settings-menu-section').first().locator('summary').evaluate(node => node.click());
        assert.equal(await page.locator('[data-settings-links="events"]').isVisible(), true);
        await page.locator('.settings-menu-section').last().locator('summary').evaluate(node => node.click());
        assert.equal(await page.locator('[data-settings-page="events"]').isVisible(), true);
        assert.equal(await page.locator('[data-settings-links="chat"]').isVisible(), true);
        assert.equal(await page.locator('[data-settings-links="events"]').isVisible(), true);
        await page.locator('.settings-menu-section').last().locator('summary').dblclick();
        await page.locator('[data-settings-links="events"]').waitFor({state: 'hidden'});
        assert.equal(await page.locator('[data-settings-links="chat"]').isVisible(), true);
        await page.locator('[data-settings-tab="chat"]').click();
        assert.equal(await page.locator('[data-settings-page="chat"]').isVisible(), true);
        await page.locator('[data-settings-tab="events"]').click();
        assert.equal(await page.locator('[data-settings-links="chat"]').isVisible(), true);
        await page.waitForFunction(() => scrolledSettings.some(entry => entry.key === 'chat' && entry.block === 'start'));
        await page.locator('[data-settings-tab="events"]').press('ArrowDown');
        assert.equal(await page.locator('[data-settings-page="chat"]').isVisible(), true);
        await page.locator('[data-settings-tab="chat"]').press('ArrowUp');
        assert.equal(await page.locator('[data-settings-page="events"]').isVisible(), true);
        await search.fill('follow');
        await page.locator('[data-settings-results] button').filter({hasText: 'Follow message'}).last().click();
        const draft = page.locator('[data-settings-page="events"] textarea');
        await draft.fill('Unsaved draft');
        await page.waitForFunction(() => scrolledSettings.some(entry => entry.key === 'follow' && entry.block === 'start'));
        assert.equal(await page.locator('[data-settings-tab="events"] .settings-dirty-dot').evaluate(node => node.hidden), false);
        await page.locator('[data-settings-tab="chat"]').click();
        await page.locator('[data-settings-links="chat"] button').click();
        assert.equal(await page.locator('[data-settings-page="chat"]').isVisible(), true);
        assert.equal(await page.locator('[data-settings-tab="chat"]').getAttribute('aria-current'), 'page');
        await search.fill('lurk');
        await page.locator('[data-settings-results] button').filter({hasText: 'Lurk message'}).last().click();
        assert.equal(await page.locator('[data-settings-page="chat"] .settings-group').isVisible(), true);
        assert.equal(await page.locator('[data-settings-page="events"]').isVisible(), false);
        await search.fill('follow');
        await page.locator('[data-settings-results] button').filter({hasText: 'Follow message'}).last().click();
        assert.equal(await draft.inputValue(), 'Unsaved draft');
        assert.equal(await draft.evaluate(node => node === document.activeElement), true);
        for (const query of ['private_saved_message', 'Unsaved draft', 'nonexistent']) {
            await search.fill(query);
            assert.equal(await page.locator('[data-settings-results] button').count(), 0);
            assert.match(await page.locator('[data-settings-result-count]').textContent(), /No settings found/);
        }
        await search.fill('');
        assert.equal(await page.locator('[data-settings-results]').isVisible(), false);
        await page.setViewportSize({width: 390, height: 844});
        await page.locator('[data-settings-links="chat"]').waitFor({state: 'hidden'});
        await search.fill('lurk');
        await page.locator('[data-settings-results] button').filter({hasText: 'Lurk message'}).last().click();
        assert.equal(await drawer.isVisible(), true);
        await page.locator('[data-settings-links="events"]').waitFor({state: 'hidden'});
        assert.equal(await page.locator('[data-settings-page="chat"] textarea').evaluate(node => node === document.activeElement), true);
    } finally { await browser.close(); }
});
