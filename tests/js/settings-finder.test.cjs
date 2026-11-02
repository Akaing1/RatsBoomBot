const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('settings search ranks close names first and also includes name and category substrings', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage();
        await page.setContent(`<div data-settings-book><div data-settings-finder><input><p data-settings-result-count></p><div data-settings-results></div></div>
            ${[['Chat', 'Controls', ['Lurking message', 'Alerts', 'Lurk message', 'Lurk']], ['Lurk tools', 'Utilities', ['Enabled', 'Cooldown']]].map(([category, group, names], index) => `<section data-settings-page="page${index}"><header class="settings-page-heading"><h3>${category}</h3></header><section class="settings-group"><header class="settings-group-heading"><h4>${group}</h4></header>${names.map(name => `<article class="profile-setting-card"><h4>${name}</h4><div class="toggle-card-heading"><p>Contains lurk only in the description.</p></div><textarea>Private lurk value</textarea></article>`).join('')}</section></section>`).join('')}</div>`);
        await page.addScriptTag({path: 'web/static/js/settings-finder.js'});
        const input = page.locator('[data-settings-finder] input');
        const names = () => page.locator('[data-settings-results] button>span').allTextContents();
        await input.fill('lurk');
        const matches = await names();
        assert.equal(matches[0], 'Lurk', 'Exact names come before partial names');
        assert.ok(matches.indexOf('Lurk message') < matches.indexOf('Lurking message'), 'Closer partial names rank first');
        assert.ok(matches.indexOf('Lurking message') < matches.indexOf('Enabled'), 'Name matches precede category-only matches');
        assert.ok(matches.includes('Cooldown'));
        assert.ok(!matches.includes('Alerts'), 'Descriptions and stored values do not create unrelated name/category matches');
        await input.fill('lurk mesage');
        assert.equal((await names())[0], 'Lurk message', 'Small spelling mistakes still find the closest setting name');
        await input.fill('utilities');
        assert.ok((await names()).includes('Enabled'), 'Subcategory names are searchable');
        await input.fill('LURK MESSAGE');
        assert.equal((await names())[0], 'Lurk message');
    } finally { await browser.close(); }
});

test('settings search floats above the menu, supports keyboard selection, and dismisses cleanly', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({viewport: {width: 1200, height: 800}, reducedMotion: 'reduce'});
        await page.route('http://settings.test/**', route => route.fulfill({body: '<html></html>', contentType: 'text/html'}));
        await page.goto('http://settings.test/channel/settings');
        await page.setContent(`<body class="channel-page-settings"><div data-settings-book data-selected="events">
            <div class="settings-main settings-pages">${[['events', 'Follow'], ['chat', 'Lurk']].map(([key, title]) => `<section data-settings-page="${key}"><header class="settings-page-heading"><h3>${key}</h3></header><section class="settings-group"><header class="settings-group-heading"><h4>${title} settings</h4></header><article class="profile-setting-card"><h4>${title} message</h4><textarea>Saved value</textarea></article></section></section>`).join('')}</div>
            <aside class="settings-tools"><div class="settings-finder" data-settings-finder hidden><input placeholder="Search settings"><p data-settings-result-count></p><div class="settings-finder-results" data-settings-results></div></div>
            <nav class="settings-menu">${['events', 'chat'].map(key => `<details class="settings-menu-section" open><summary><a data-settings-tab="${key}">${key}</a><span class="settings-dirty-dot" hidden></span></summary><div data-settings-links="${key}"></div></details>`).join('')}</nav></aside></div></body>`);
        await page.addStyleTag({path: 'web/static/css/channel-settings.css'});
        await page.addStyleTag({content: '.settings-tools{display:block!important;position:fixed!important;left:20px;top:40px;width:260px!important;height:240px;overflow:auto!important}.settings-main{margin-left:320px}'});
        for (const file of ['channel-settings.js', 'settings-finder.js']) await page.addScriptTag({path: `web/static/js/${file}`});
        const input = page.locator('[data-settings-finder] input');
        const popup = page.locator('.settings-search-popup');
        const menu = page.locator('.settings-menu');
        const menuText = await menu.textContent();
        const menuBounds = await menu.boundingBox();
        const toolsHeight = await page.locator('.settings-tools').evaluate(node => node.scrollHeight);
        await input.fill('message');
        assert.equal(await popup.evaluate(node => node.matches(':popover-open')), true);
        assert.equal(await page.locator('[data-settings-results] button').count(), 2);
        assert.equal(await menu.textContent(), menuText);
        assert.deepEqual(await menu.boundingBox(), menuBounds, 'Search results do not push down the menu');
        assert.equal(await page.locator('.settings-tools').evaluate(node => node.scrollHeight), toolsHeight);
        const bounds = await popup.boundingBox();
        assert.ok(bounds.y >= (await input.boundingBox()).y + (await input.boundingBox()).height);
        await input.press('ArrowDown');
        await input.press('ArrowDown');
        await input.press('ArrowUp');
        assert.equal(await input.evaluate(node => node === document.activeElement), true);
        await input.press('Enter');
        assert.equal(await popup.evaluate(node => node.matches(':popover-open')), false);
        assert.equal(await page.locator('[data-settings-page="chat"]').isVisible(), true);
        assert.equal(await page.locator('[data-settings-page="chat"] textarea').evaluate(node => node === document.activeElement), true);
        await input.fill('follow');
        await input.press('Escape');
        assert.equal(await input.getAttribute('aria-expanded'), 'false');
        assert.equal(await popup.isVisible(), false);
        await input.fill('lurk');
        await page.mouse.click(1190, 750);
        await page.waitForFunction(() => document.querySelector('[data-settings-finder] input').getAttribute('aria-expanded') === 'false');
        assert.equal(await popup.isVisible(), false);
        await page.setViewportSize({width: 390, height: 844});
        await input.fill('message');
        const mobileBounds = await popup.boundingBox();
        assert.ok(mobileBounds.x >= 0 && mobileBounds.x + mobileBounds.width <= 390);
        await page.setViewportSize({width: 280, height: 844});
        await page.waitForFunction(() => document.querySelector('.settings-search-popup').getBoundingClientRect().right <= innerWidth);
        await input.fill('');
        assert.equal(await popup.isVisible(), false);
    } finally { await browser.close(); }
});

test('scrolling prioritizes the middle-panel pointer including gaps, otherwise the viewport top', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({viewport: {width: 1200, height: 800}, reducedMotion: 'reduce'});
        await page.route('http://settings.test/**', route => route.fulfill({body: '<html></html>', contentType: 'text/html'}));
        await page.goto('http://settings.test/channel/settings?section=events');
        await page.setContent(`<style>
            body{margin:0;padding-bottom:1000px}.settings-menu{position:fixed;left:0;top:0;width:180px}
            .settings-main{margin-left:220px;width:700px}.settings-group{height:400px}
            .settings-group-heading{margin:0;height:40px}.profile-setting-card{height:60px}
            [hidden]{display:none!important}
            </style><div data-settings-book data-selected="events"><nav class="settings-menu"><details class="settings-menu-section" open>
            <summary><a data-settings-tab="events">Events</a><span class="settings-dirty-dot" hidden></span></summary><div data-settings-links="events"></div></details></nav>
            <main class="settings-main settings-pages"><section data-settings-page="events"><header class="settings-page-heading"><h3>Events</h3></header>${['first', 'second'].map(name => `<section class="settings-group" id="${name}"><header class="settings-group-heading" id="${name}-heading"><h4>${name}</h4></header><article class="profile-setting-card" id="${name}-card">Setting</article></section>`).join('')}</section></main>
            <aside data-settings-finder><input><p data-settings-result-count></p><div data-settings-results></div></aside></div>`);
        for (const file of ['channel-settings.js', 'settings-finder.js', 'settings-menu-highlight.js']) await page.addScriptTag({path: `web/static/js/${file}`});
        const selected = () => page.locator('[data-settings-location][aria-current="location"]').getAttribute('data-settings-location');
        await page.mouse.move(500, 650);
        await page.evaluate(() => window.scrollTo(0, 30));
        await page.waitForFunction(() => document.querySelector('[data-settings-location="second-heading"]')?.getAttribute('aria-current') === 'location');
        assert.equal(await selected(), 'second-heading', 'Empty space in the middle panel retains pointer context');
        await page.mouse.move(100, 100);
        await page.evaluate(() => window.scrollTo(0, 50));
        await page.waitForFunction(() => document.querySelector('[data-settings-location="first-heading"]')?.getAttribute('aria-current') === 'location');
        assert.equal(await selected(), 'first-heading', 'Scrolling outside the middle panel uses the viewport top');
        await page.mouse.move(500, 300);
        await page.evaluate(() => window.scrollTo(0, 200));
        await page.waitForFunction(() => document.querySelector('[data-settings-location="second-heading"]')?.getAttribute('aria-current') === 'location');
        assert.equal(await selected(), 'second-heading', 'A stationary pointer follows the section scrolling beneath it');
    } finally { await browser.close(); }
});

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
        await page.locator('[data-settings-results] button').filter({has: page.locator('span', {hasText: /^Follow message$/})}).click();
        const draft = page.locator('[data-settings-page="events"] textarea');
        await draft.fill('Unsaved draft');
        await page.waitForFunction(() => scrolledSettings.some(entry => entry.key === 'follow' && entry.block === 'start'));
        assert.equal(await page.locator('[data-settings-tab="events"] .settings-dirty-dot').evaluate(node => node.hidden), false);
        await page.locator('[data-settings-tab="chat"]').click();
        await page.locator('[data-settings-links="chat"] button').click();
        assert.equal(await page.locator('[data-settings-page="chat"]').isVisible(), true);
        assert.equal(await page.locator('[data-settings-tab="chat"]').getAttribute('aria-current'), 'page');
        await search.fill('lurk');
        await page.locator('[data-settings-results] button').filter({has: page.locator('span', {hasText: /^Lurk message$/})}).click();
        assert.equal(await page.locator('[data-settings-page="chat"] .settings-group').isVisible(), true);
        assert.equal(await page.locator('[data-settings-page="events"]').isVisible(), false);
        await search.fill('follow');
        await page.locator('[data-settings-results] button').filter({has: page.locator('span', {hasText: /^Follow message$/})}).click();
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
        await page.locator('[data-settings-results] button').filter({has: page.locator('span', {hasText: /^Lurk message$/})}).click();
        assert.equal(await drawer.isVisible(), true);
        await page.locator('[data-settings-links="events"]').waitFor({state: 'hidden'});
        assert.equal(await page.locator('[data-settings-page="chat"] textarea').evaluate(node => node === document.activeElement), true);
    } finally { await browser.close(); }
});


test('single-menu categories retain searchable child settings without nested menu entries', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage();
        await page.setContent(`<div data-settings-book>
            <nav class="settings-menu"><details class="settings-menu-section" open><summary><a data-settings-tab="events" aria-current="page">Events</a></summary><div data-settings-links="events"></div></details></nav>
            <section data-settings-page="events"><header class="settings-page-heading"><h3>Events</h3></header>
                <section class="settings-group" id="outgoing" data-settings-single-menu><header class="settings-group-heading"><h4>Outgoing raids</h4></header>
                    <section class="settings-group"><header class="settings-group-heading"><h4>Outgoing raid messages</h4></header><article class="profile-setting-card"><h4>Non-subscriber raid message</h4><textarea></textarea></article></section>
                    <section class="settings-group" id="follow"><header class="settings-group-heading"><h4>Follow outgoing raids</h4></header><p>Description</p></section>
                </section>
            </section>
            <div data-settings-finder><input><p data-settings-result-count></p><div data-settings-results></div></div>
        </div>`);
        for (const script of ['settings-finder.js', 'settings-menu-highlight.js']) await page.addScriptTag({path: `web/static/js/${script}`});
        assert.deepEqual(await page.locator('[data-settings-links] button').allTextContents(), ['Outgoing raids']);
        await page.evaluate(() => document.querySelector('[data-settings-book]').dispatchEvent(new CustomEvent('settings-hover', {detail: document.querySelector('#follow p')})));
        assert.equal(await page.locator('[data-settings-links] button[aria-current=location]').textContent(), 'Outgoing raids');
        await page.locator('[data-settings-finder] input').fill('follow outgoing');
        assert.ok((await page.locator('[data-settings-results] button>span').allTextContents()).includes('Follow outgoing raids'));
    } finally { await browser.close(); }
});
