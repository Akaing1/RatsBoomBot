const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('the complete panel group stays centered and slides between two and three columns', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true, args: ['--disable-frame-rate-limit']});
    try {
        const page = await browser.newPage({viewport: {width: 1800, height: 900}});
        await page.setContent(`<body class="channel-page-settings"><div data-settings-book><div class="settings-workspace">
            <main class="settings-main"><div class="settings-pages"><section data-settings-page="events"><section class="settings-group"><header class="settings-group-heading"><h4>Events</h4></header><div class="settings-switch-row"><div class="settings-command-reference-region" data-settings-command-reference><aside class="settings-command-reference"><h4>Commands</h4><ul><li><code>!test</code></li></ul></aside></div></div></section></section>
            <section data-settings-page="timers" hidden><h3>Timers</h3></section></div></main>
            <aside class="settings-tools">Navigation</aside><div class="settings-extra-panel settings-commands-rail"></div>
        </div></div></body>`);
        await page.addStyleTag({path: 'web/static/css/channel-settings.css'});
        await page.addStyleTag({content: 'body{margin:0}*{box-sizing:border-box}'});
        await page.addScriptTag({path: 'web/static/js/settings-command-references.js'});
        await page.waitForFunction(() => document.querySelector('[data-settings-book]').classList.contains('has-command-references'));
        const centered = async () => {
            const gap = await page.evaluate(() => {
                const workspace = document.querySelector('.settings-workspace').getBoundingClientRect();
                const panels = [...document.querySelector('.settings-workspace').children].map(node => node.getBoundingClientRect()).filter(bounds => bounds.width);
                return (Math.min(...panels.map(bounds => bounds.left)) + Math.max(...panels.map(bounds => bounds.right))) / 2 - (workspace.left + workspace.width / 2);
            });
            assert.ok(Math.abs(gap) < 1, `Panel group differs from center by ${gap}px`);
        };
        const change = key => page.evaluate(section => {
            document.querySelectorAll('[data-settings-page]').forEach(node => { node.hidden = node.dataset.settingsPage !== section; });
            document.querySelector('[data-settings-book]').dispatchEvent(new CustomEvent('settings-section-changed'));
            return document.querySelector('.settings-main').getAnimations().length;
        }, key);
        const finish = () => page.locator('.settings-workspace').evaluate(node => Promise.all([...node.children].flatMap(panel => panel.getAnimations()).map(animation => animation.finished)));
        await centered();
        const initial = await page.locator('.settings-main').boundingBox();
        assert.equal(await change('timers'), 1);
        await finish();
        await centered();
        const two = await page.locator('.settings-main').boundingBox();
        assert.ok(two.x > initial.x);
        assert.equal(two.width, initial.width);
        assert.equal(await change('events'), 1);
        await finish();
        await centered();
        assert.ok(Math.abs((await page.locator('.settings-main').boundingBox()).x - initial.x) < 1);
        await page.emulateMedia({reducedMotion: 'reduce'});
        assert.equal(await change('timers'), 0);
        await centered();
    } finally { await browser.close(); }
});

test('expanding commands at the page bottom keeps the scroll position and hover target stable', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true, args: ['--disable-frame-rate-limit']});
    try {
        const page = await browser.newPage({viewport: {width: 1300, height: 600}});
        const commands = (title, count) => `<div class="settings-command-reference-region" data-settings-command-reference><aside class="settings-command-reference"><h4>${title}</h4><ul>${Array.from({length: count}, (_, index) => `<li><code>!command${index}</code><span>Command description</span></li>`).join('')}</ul></aside></div>`;
        await page.setContent(`<body class="channel-page-settings"><div data-settings-book><div class="settings-workspace"><main class="settings-main settings-pages"><section data-settings-page="chat">
            <div style="height:800px"></div><section class="settings-command-cluster" id="groups" style="height:200px"><h4>Command groups</h4><div class="settings-switch-row">Settings commands${commands('Command groups', 15)}</div></section>
            <section class="settings-group" id="other" style="height:100px"><header class="settings-group-heading"><h4>Commands</h4></header><div class="profile-setting-card">Lurk${commands('Lurk', 1)}</div></section>
        </section></main><div class="settings-extra-panel settings-commands-rail"></div></div></div></body>`);
        await page.addStyleTag({path: 'web/static/css/channel-settings.css'});
        await page.addStyleTag({content: 'body{margin:0}.settings-workspace{display:flex;align-items:flex-start}.settings-main{flex:1}.settings-command-cluster,.settings-group{box-sizing:border-box;margin:0}'});
        for (const file of ['settings-command-references.js', 'channel-settings.js']) await page.addScriptTag({path: `web/static/js/${file}`});
        await page.waitForFunction(() => document.querySelector('.settings-commands-rail').style.height);
        await page.mouse.move(0, 0);
        await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
        await page.waitForTimeout(100);
        const before = await page.evaluate(() => ({height: document.documentElement.scrollHeight, scroll: scrollY}));
        await page.locator('#groups>h4').hover();
        await page.waitForTimeout(700);
        assert.equal(await page.locator('.settings-commands-rail .is-selected h4').textContent(), 'Command groups');
        assert.deepEqual(await page.evaluate(() => ({height: document.documentElement.scrollHeight, scroll: scrollY})), before);
        await page.locator('#other .settings-group-heading').hover();
        await page.waitForTimeout(700);
        assert.equal(await page.locator('.settings-commands-rail .is-selected h4').textContent(), 'Lurk');
        assert.deepEqual(await page.evaluate(() => ({height: document.documentElement.scrollHeight, scroll: scrollY})), before);
    } finally { await browser.close(); }
});

test('timer headings, controls, and saved rows select their own menu subsection', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({viewport: {width: 1300, height: 900}, reducedMotion: 'reduce'});
        await page.route('http://settings.test/**', route => route.fulfill({body: '<html></html>', contentType: 'text/html'}));
        await page.goto('http://settings.test/channel/settings?section=timers');
        await page.setContent(`<style>.settings-menu{position:fixed;left:0;top:20px;width:180px}.settings-main{margin-left:220px}.panel{height:300px;padding:20px}</style>
            <div data-settings-book data-selected="timers"><nav class="settings-menu"><details class="settings-menu-section" open><summary><a data-settings-tab="timers">Timers</a></summary><div data-settings-links="timers"></div></details></nav>
            <main class="settings-main settings-pages"><section data-settings-page="timers"><header class="settings-page-heading"><h3>Timers</h3></header>
                <form class="settings-timer-manager"><section class="panel" data-timer-create><h3>Create timer</h3><label>Message<textarea></textarea></label><button>Create timer</button></section>
                <section class="panel" data-timer-saved><h3>Your timers</h3><article class="settings-timer-row"><label>Message<textarea>Saved timer</textarea></label><button>Remove timer</button></article></section></form>
            </section></main><aside data-settings-finder><input><p data-settings-result-count></p><div data-settings-results></div></aside></div>`);
        for (const file of ['channel-settings.js', 'settings-finder.js', 'settings-menu-highlight.js']) {
            await page.addScriptTag({path: `web/static/js/${file}`});
        }
        const current = label => page.waitForFunction(text => document.querySelector('[data-settings-location][aria-current="location"]')?.textContent === text, label);
        await page.locator('[data-timer-create] h3').hover();
        await current('Create timer');
        await page.locator('[data-timer-saved] textarea').hover();
        await current('Your timers');
        await page.mouse.move(190, 400);
        await current('Your timers');
        await page.locator('[data-timer-create] textarea').hover();
        await current('Create timer');
        await page.locator('[data-timer-saved] button').hover();
        await current('Your timers');
    } finally { await browser.close(); }
});

test('settings context follows hover, retains it on exit, and resumes at the scroll edge', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true, args: ['--disable-frame-rate-limit']});
    try {
        const page = await browser.newPage({viewport: {width: 1500, height: 900}, reducedMotion: 'reduce'});
        await page.route('http://settings.test/**', route => route.fulfill({body: '<html></html>', contentType: 'text/html'}));
        await page.goto('http://settings.test/channel/settings');
        const reference = label => `<aside data-settings-command-reference><section class="settings-command-reference"><h4>${label}</h4><ul><li><code>!${label}</code></li></ul></section></aside>`;
        await page.setContent(`<style>
            body {margin:0} .settings-main {margin:100px 380px 0 200px}
            .settings-menu {position:fixed;left:0;top:80px;width:180px}
            .settings-commands-rail {position:fixed;right:0;top:80px;width:300px}
            .settings-group, .panel, .settings-command-cluster {box-sizing:border-box; margin:0;padding:10px}
            #queue {height:400px} #blacklist {height:200px} #shoutouts {height:500px}
            #groups {height:600px} .profile-setting-card {height:90%}
            [data-channel-sidebar] {display:none} [hidden] {display:none!important}
            @media(max-width:768px) { .settings-main {margin-left:200px;margin-right:0} [data-channel-sidebar] {display:block;position:fixed;top:0;height:62px;width:100%;background:white;z-index:2} }
        </style><div data-channel-sidebar></div><div data-settings-book data-selected="queue" data-channel="1">
            <nav class="settings-menu"><details class="settings-menu-section" open><summary><a data-settings-tab="queue">Viewer queue</a></summary>
                ${['queue', 'blacklist', 'shoutouts', 'groups'].map(id => `<button data-settings-location="${id}">${id}</button>`).join('')}
            </details></nav>
            <main class="settings-main settings-pages"><section class="settings-page" data-settings-page="queue">
                <section class="settings-group" id="queue"><header class="settings-group-heading">Viewer queue</header><article class="profile-setting-card">Queue settings${reference('queue')}</article></section>
                <section class="panel profile-settings-panel" id="blacklist"><h3>Queue blacklist</h3><p>Blocked viewers</p><button>Manage blacklist</button></section>
                <section class="settings-group" id="shoutouts" data-settings-hash="shoutouts"><header class="settings-group-heading">Shoutouts</header><article class="profile-setting-card">Shoutout settings${reference('shoutouts')}</article></section>
                <section class="settings-command-cluster" id="groups"><h4>Command groups</h4><div class="settings-switch-row">One${reference('one')}</div><div class="settings-switch-row">Two${reference('two')}</div></section>
            </section></main><aside class="settings-commands-rail"></aside>
        </div>`);
        for (const file of ['settings-command-references.js', 'channel-settings.js', 'settings-menu-highlight.js']) {
            await page.addScriptTag({content: fs.readFileSync(`web/static/js/${file}`, 'utf8')});
        }
        const current = () => page.locator('[data-settings-location][aria-current="location"]').getAttribute('data-settings-location');
        const waitForLocation = id => page.waitForFunction(value => document.querySelector('[data-settings-location][aria-current="location"]')?.dataset.settingsLocation === value, id);
        const scrollTo = async y => {
            await page.evaluate(value => window.scrollTo(0, value), y);
            await page.waitForFunction(value => window.scrollY === value, y);
            await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        };
        await page.waitForFunction(() => document.querySelectorAll('.settings-commands-rail [data-settings-command-reference]:not([hidden])').length === 3);
        await page.mouse.move(220, 550);
        await waitForLocation('blacklist');
        await page.mouse.move(190, 550);
        await page.waitForTimeout(200);
        assert.equal(await current(), 'blacklist');
        await scrollTo(250);
        await waitForLocation('queue');
        await page.mouse.move(220, 650);
        await waitForLocation('shoutouts');
        assert.equal(await page.locator('.settings-commands-rail [data-settings-command-reference]').nth(1).evaluate(node => node.style.zIndex), '4');
        await scrollTo(280);
        await waitForLocation('shoutouts');
        await page.mouse.move(190, 650);
        await page.waitForTimeout(200);
        assert.equal(await current(), 'shoutouts');
        await scrollTo(300);
        await waitForLocation('queue');
        await scrollTo(520);
        await waitForLocation('blacklist');
        await scrollTo(900);
        await page.mouse.move(220, 400);
        await waitForLocation('groups');
        const commands = page.locator('.settings-commands-rail [data-settings-command-reference]').filter({has: page.locator('h4', {hasText: 'Command groups'})});
        assert.equal(await commands.locator('li').count(), 2);
        await page.locator('.settings-commands-rail h4', {hasText: /^shoutouts$/}).click();
        await waitForLocation('shoutouts');
        assert.ok(page.url().endsWith('#shoutouts'));
        await page.mouse.move(190, 400);
        await page.setViewportSize({width: 750, height: 900});
        await scrollTo(470);
        await waitForLocation('blacklist');
    } finally { await browser.close(); }
});

test('command panels expand into available space and the selected list opens over its neighbour', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true, args: ['--disable-frame-rate-limit']});
    try {
        const page = await browser.newPage({viewport: {width: 1300, height: 600}});
        const section = (id, height, count) => `<section class="settings-group" id="${id}" style="height:${height}px"><header class="settings-group-heading"><h4>${id}</h4></header>
            <section class="panel profile-settings-panel"><header class="panel-header" style="display:none">Hidden duplicate heading</header><div class="settings-switch-row"><div class="settings-command-reference-region" data-settings-command-reference><aside class="settings-command-reference"><h4>${id} commands</h4><ul>${Array.from({length: count}, (_, index) => `<li><code>!${id}${index}</code><span>Description</span></li>`).join('')}</ul></aside></div></div></section></section>`;
        await page.setContent(`<body class="channel-page-settings"><div data-settings-book><div class="settings-workspace">
            <main class="settings-main settings-pages"><section data-settings-page="events">${section('Raid', 1000, 1)}${section('Shoutouts', 500, 15)}${section('Short', 180, 30)}</section></main>
            <div class="settings-extra-panel settings-commands-rail"></div>
        </div></div></body>`);
        await page.addStyleTag({path: 'web/static/css/channel-settings.css'});
        await page.addStyleTag({content: 'body{margin:0;--border:#343644;--surface:#181c23;--text:#fff} .settings-workspace{display:flex;align-items:flex-start} .settings-main{flex:1} .settings-group{box-sizing:border-box;margin:0} .settings-group-heading{margin:0}'});
        const originalHeight = await page.locator('.settings-main').evaluate(node => node.getBoundingClientRect().height);
        await page.addScriptTag({path: 'web/static/js/settings-command-references.js'});
        await page.waitForFunction(() => document.querySelector('.settings-commands-rail').style.height);
        const panels = page.locator('.settings-commands-rail .settings-command-reference');
        assert.equal(await panels.count(), 3);
        assert.equal(await page.locator('.settings-main').evaluate(node => node.getBoundingClientRect().height), originalHeight);
        const alignment = await page.evaluate(() => [...document.querySelectorAll('.settings-group')].map((section, index) => {
            const heading = section.querySelector('.settings-group-heading').getBoundingClientRect();
            const panel = document.querySelectorAll('.settings-commands-rail .settings-command-reference')[index].getBoundingClientRect();
            return {heading: heading.top, panel: panel.top, region: document.querySelectorAll('.settings-commands-rail [data-settings-command-reference]')[index].getBoundingClientRect().top};
        }));
        alignment.forEach(bounds => assert.ok(Math.abs(bounds.heading - bounds.panel) < 2, JSON.stringify(bounds)));
        await page.evaluate(() => window.scrollTo(0, 300));
        await page.waitForFunction(() => window.scrollY === 300);
        assert.ok(Math.abs((await panels.nth(0).boundingBox()).y - 16) < 2);
        const shoutouts = await panels.nth(1).boundingBox();
        const heading = await page.locator('#Shoutouts .settings-group-heading').boundingBox();
        assert.ok(Math.abs(shoutouts.y - heading.y) < 2);
        await page.mouse.move(400, 800);
        assert.equal(await panels.count(), 3);
        await page.evaluate(() => window.scrollTo(0, 950));
        await page.waitForFunction(() => window.scrollY === 950);
        const raid = await panels.nth(0).boundingBox();
        const raidSection = await page.locator('#Raid').boundingBox();
        assert.ok(raid.y + raid.height <= raidSection.y + raidSection.height + 1);
        const short = await panels.nth(2).boundingBox();
        assert.ok(short.height > 180 && short.height <= 568);
        assert.equal(await panels.nth(2).evaluate(node => node.scrollHeight > node.clientHeight), true);
        assert.equal(await page.locator('.settings-main').evaluate(node => node.getBoundingClientRect().height), originalHeight);
        await page.evaluate(() => window.scrollTo(0, 1100));
        await page.waitForFunction(() => window.scrollY === 1100);
        const upper = await panels.nth(1).boundingBox();
        const lower = await panels.nth(2).boundingBox();
        assert.ok(upper.y + upper.height <= lower.y - 15, 'Unselected panels leave room for the next sticky');
        const foreground = () => page.evaluate(({x, y}) => document.elementFromPoint(x, y)?.closest('.settings-command-reference')?.querySelector('h4').textContent, {x: lower.x + lower.width / 2, y: lower.y + 20});
        assert.equal(await foreground(), 'Short commands');
        assert.equal(await page.evaluate(() => {
            document.querySelector('[data-settings-book]').dispatchEvent(new CustomEvent('settings-hover', {detail: document.querySelector('#Shoutouts')}));
            return document.querySelectorAll('.settings-commands-rail .settings-command-reference')[1].getAnimations().length;
        }), 1);
        await panels.nth(1).evaluate(node => Promise.all(node.getAnimations().map(animation => animation.finished)));
        await page.waitForFunction(() => document.querySelectorAll('.settings-commands-rail .settings-command-reference')[1].getBoundingClientRect().height > 500);
        assert.equal(await foreground(), 'Shoutouts commands');
        await page.evaluate(() => document.querySelector('[data-settings-book]').dispatchEvent(new CustomEvent('settings-hover-end')));
        assert.equal(await foreground(), 'Shoutouts commands');
        assert.equal(await page.evaluate(() => {
            document.querySelector('[data-settings-book]').dispatchEvent(new CustomEvent('settings-hover', {detail: document.querySelector('#Short')}));
            return document.querySelectorAll('.settings-commands-rail .settings-command-reference')[1].getAnimations().length;
        }), 1);
        await page.waitForFunction(height => document.querySelectorAll('.settings-commands-rail .settings-command-reference')[1].getBoundingClientRect().height <= height + 1, upper.height);
        assert.equal(await foreground(), 'Short commands');
        const shortRegion = panels.nth(2).locator('..');
        const shoutoutsRegion = panels.nth(1).locator('..');
        await panels.nth(1).locator('h4').hover();
        await page.waitForFunction(() => document.querySelectorAll('.settings-commands-rail .settings-command-reference')[1].getBoundingClientRect().height > 500);
        assert.equal(await shoutoutsRegion.evaluate(node => node.classList.contains('is-hovered')), true);
        assert.equal(await shortRegion.evaluate(node => node.classList.contains('is-selected')), true);
        await page.mouse.move(0, 100);
        await page.waitForFunction(height => document.querySelectorAll('.settings-commands-rail .settings-command-reference')[1].getBoundingClientRect().height <= height + 1, upper.height);
        assert.equal(await shoutoutsRegion.evaluate(node => node.classList.contains('is-hovered')), false);
        await panels.nth(1).locator('h4').click();
        await page.mouse.move(0, 100);
        await page.waitForFunction(() => document.querySelectorAll('.settings-commands-rail .settings-command-reference')[1].getBoundingClientRect().height > 500);
        assert.equal(await shoutoutsRegion.evaluate(node => node.classList.contains('is-selected')), true);
        assert.equal(await shoutoutsRegion.evaluate(node => node.classList.contains('is-hovered')), false);
        assert.equal(await shortRegion.evaluate(node => node.classList.contains('is-selected')), false);
    } finally { await browser.close(); }
});

test('Connections keeps one complete Command groups reference alongside the entire page', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({viewport: {width: 1300, height: 600}});
        const reference = command => `<div class="settings-command-reference-region" data-settings-command-reference><aside class="settings-command-reference"><h4>Socials commands</h4><ul><li><code>${command}</code><span>Share a community link.</span></li></ul></aside></div>`;
        await page.setContent(`<body class="channel-page-settings"><div data-settings-book><div class="settings-workspace">
            <main class="settings-main settings-pages"><section data-settings-page="connections">
                <header class="settings-page-heading"><h3>Connections</h3></header>
                <section class="settings-command-cluster"><h4>Command groups</h4><div class="settings-switch-row">Socials commands${reference('!socials')}</div></section>
                <section class="settings-group" style="height:1400px"><header class="settings-group-heading"><h4>Social links</h4></header><article class="profile-setting-card">Discord URL${reference('!discord')}</article></section>
                <section class="settings-group" style="height:400px"><header class="settings-group-heading"><h4>Bot identity</h4></header></section>
            </section></main><div class="settings-extra-panel settings-commands-rail"></div>
        </div></div></body>`);
        await page.addStyleTag({path: 'web/static/css/channel-settings.css'});
        await page.addStyleTag({content: 'body{margin:0} .settings-workspace{display:flex;align-items:flex-start} .settings-main{flex:1}'});
        await page.addScriptTag({path: 'web/static/js/settings-command-references.js'});
        const region = page.locator('.settings-commands-rail [data-settings-command-reference]');
        await page.waitForFunction(() => document.querySelector('.settings-commands-rail').style.height);
        assert.equal(await region.count(), 1);
        assert.equal(await region.locator('h4').textContent(), 'Command groups');
        assert.equal(await region.locator('li').count(), 2);
        assert.equal(await region.locator('aside').evaluate(node => node.scrollHeight > node.clientHeight), false);
        const bounds = await region.boundingBox();
        const connections = await page.locator('[data-settings-page="connections"]').boundingBox();
        assert.ok(Math.abs(bounds.y + bounds.height - connections.y - connections.height) < 2);
        await page.evaluate(() => window.scrollTo(0, 1200));
        await page.waitForFunction(() => window.scrollY === 1200);
        assert.ok(Math.abs((await region.locator('aside').boundingBox()).y - 16) < 2);
    } finally { await browser.close(); }
});
