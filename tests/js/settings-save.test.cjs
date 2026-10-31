const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('settings save without navigation, preserve drafts, refresh dependent switches, and float feedback for five seconds', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    let server;
    try {
        const page = await browser.newPage({viewport: {width: 1300, height: 900}, reducedMotion: 'reduce'});
        await page.clock.install();
        let enabled = true;
        let followRaid = true;
        let fail = false;
        const posts = [];
        const html = () => `<body class="channel-page-settings"><div class="toggle-feedback success">Earlier update saved.</div><div data-settings-book data-selected="events" data-channel="1">
            <nav class="settings-menu">${['events', 'chat'].map(key => `<details class="settings-menu-section" open><summary><a href="?section=${key}" data-settings-tab="${key}">${key}</a><span class="settings-dirty-dot" hidden></span></summary></details>`).join('')}</nav>
            <main class="settings-main settings-pages"><section data-settings-page="events"><header class="settings-page-heading"><h3>Events</h3></header>
                <span class="settings-inline-switch"><button id="master" role="switch" type="submit" form="toggle-master" name="action" value="${enabled ? 'disable' : 'enable'}" aria-checked="${enabled}">${enabled ? 'Enabled' : 'Disabled'}</button></span>
                <form id="save-follow" method="post" action="/channel/customization"><input type="hidden" name="csrf_token" value="test-token"><input type="hidden" name="setting_name" value="follow"><textarea name="value">Follow message</textarea><button name="action" value="save">Save</button></form>
                <form id="save-raid" method="post" action="/channel/customization"><input type="hidden" name="setting_name" value="dashboard.follow_raid"><input type="hidden" name="action" value="save"><button role="switch" name="value" value="${followRaid ? '0' : '1'}" aria-checked="${followRaid}">Follow raid</button></form>
            </section><section data-settings-page="chat" hidden><header class="settings-page-heading"><h3>Chat</h3></header><article id="lurk-card" class="profile-setting-card${enabled ? '' : ' is-disabled'}">
                <span class="settings-inline-switch"><button id="child" role="switch" type="submit" form="toggle-child" name="action" value="disable" ${enabled ? '' : 'disabled'} aria-checked="${enabled}">${enabled ? 'Enabled' : 'Disabled'}</button></span>
                <form id="save-lurk" method="post" action="/channel/customization"><input type="hidden" name="setting_name" value="lurk"><textarea name="value">Lurk message</textarea><button name="action" value="save">Save</button></form>
            </article></section></main>
            ${['master', 'child'].map(name => `<form id="toggle-${name}" method="post" action="/channel/features/toggles"><input type="hidden" name="toggle_name" value="${name}"></form>`).join('')}
        </div></body>`;
        server = http.createServer(async (request, response) => {
            if (request.method === 'POST') {
                const chunks = [];
                for await (const chunk of request) chunks.push(chunk);
                posts.push(Buffer.concat(chunks).toString());
                if (request.url.endsWith('/toggles')) enabled = false;
                if (posts.at(-1).includes('dashboard.follow_raid')) followRaid = false;
                await new Promise(resolve => setTimeout(resolve, 100));
                response.writeHead(303, {location: `/channel/settings?setting_result=${fail ? 'error' : 'success'}&setting_message=${fail ? 'Invalid+setting.' : 'Saved.'}`});
                response.end();
            } else {
                response.writeHead(200, {'Content-Type': 'text/html'});
                response.end(html());
            }
        });
        await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
        await page.goto(`http://127.0.0.1:${server.address().port}/channel/settings?section=events`);
        await page.addStyleTag({path: 'web/static/css/channel-settings.css'});
        await page.addStyleTag({content: '.settings-menu{position:fixed;left:0;top:0;width:180px}.settings-main{margin-left:200px}'});
        for (const file of ['channel-settings.js', 'settings-save.js']) await page.addScriptTag({path: `web/static/js/${file}`});
        await page.evaluate(() => { window.samePage = true; });
        assert.equal(await page.locator('.toggle-feedback').count(), 0);
        assert.equal(await page.locator('#save-follow [data-settings-save]').isVisible(), false);
        assert.equal(await page.locator('#master').isVisible(), true);
        await page.locator('#save-follow textarea').fill('Temporary edit');
        assert.equal(await page.locator('#save-follow [data-settings-save]').isVisible(), true);
        await page.locator('#save-follow textarea').fill('Follow message');
        assert.equal(await page.locator('#save-follow [data-settings-save]').isVisible(), false);
        assert.equal(await page.locator('.settings-floating-status').evaluate(node => getComputedStyle(node).color), 'rgb(134, 239, 172)');
        await page.locator('[data-settings-tab="chat"]').click();
        await page.locator('#save-lurk textarea').fill('Unsaved chat draft');
        await page.locator('[data-settings-tab="events"]').click();
        await page.locator('#save-follow textarea').fill('Submitted message');
        await page.locator('#save-follow [data-settings-save]').click();
        await page.locator('#save-follow textarea').fill('New edit while saving');
        await page.locator('[data-settings-tab="chat"]').click();
        await page.waitForFunction(() => !document.querySelector('#save-follow').hasAttribute('aria-busy'));
        assert.equal(await page.evaluate(() => window.samePage), true);
        assert.match(page.url(), /section=chat/);
        assert.equal(await page.locator('#save-lurk textarea').inputValue(), 'Unsaved chat draft');
        assert.equal(await page.locator('#save-follow textarea').inputValue(), 'New edit while saving');
        assert.equal(await page.locator('[data-settings-tab="events"]').locator('..').locator('.settings-dirty-dot').evaluate(node => node.hidden), false);
        assert.equal(await page.locator('#save-follow [data-settings-save]').evaluate(node => node.hidden), false);
        assert.match(posts[0], /name="action"\r\n\r\nsave/);
        assert.match(posts[0], /test-token/);
        await page.locator('[data-settings-tab="events"]').click();
        await page.locator('#save-follow [data-settings-save]').click();
        await page.waitForFunction(() => !document.querySelector('#save-follow').hasAttribute('aria-busy'));
        assert.equal(await page.locator('[data-settings-tab="events"]').locator('..').locator('.settings-dirty-dot').evaluate(node => node.hidden), true, await page.locator('.settings-floating-status').textContent());
        assert.equal(await page.locator('#save-follow [data-settings-save]').isVisible(), false);
        await page.locator('#master').click();
        await page.waitForFunction(() => document.querySelector('#master').getAttribute('aria-checked') === 'false');
        assert.equal(await page.locator('#child').isDisabled(), true);
        assert.equal(await page.locator('#lurk-card').evaluate(node => node.classList.contains('is-disabled')), true);
        assert.equal(await page.locator('#save-lurk textarea').inputValue(), 'Unsaved chat draft');
        await page.locator('#save-raid button').click();
        await page.waitForFunction(() => document.querySelector('#save-raid button').getAttribute('aria-checked') === 'false');
        assert.equal(await page.locator('#save-raid button').getAttribute('value'), '1');
        assert.match(posts.at(-1), /name="value"\r\n\r\n0/);
        const savesBeforeCancel = posts.length;
        await page.locator('#save-follow textarea').fill('An edit to cancel');
        assert.equal(await page.locator('#save-follow [data-settings-cancel]').isVisible(), true);
        await page.locator('#save-follow [data-settings-cancel]').click();
        assert.equal(await page.locator('#save-follow textarea').inputValue(), 'New edit while saving');
        assert.equal(posts.length, savesBeforeCancel);
        assert.equal(await page.locator('#save-follow [data-settings-save]').isVisible(), false);
        fail = true;
        await page.locator('#save-follow textarea').fill('Invalid draft');
        await page.locator('#save-follow [data-settings-save]').click();
        await page.waitForFunction(() => document.querySelector('.settings-floating-status').textContent === 'Invalid setting.');
        assert.equal(await page.locator('#save-follow textarea').inputValue(), 'Invalid draft');
        assert.equal(await page.locator('[data-settings-tab="events"]').locator('..').locator('.settings-dirty-dot').evaluate(node => node.hidden), false);
        const status = page.locator('.settings-floating-status');
        assert.equal(await status.evaluate(node => getComputedStyle(node).color), 'rgb(252, 165, 165)');
        assert.equal(await status.evaluate(node => getComputedStyle(node).position), 'fixed');
        const bounds = await status.boundingBox();
        assert.ok(Math.abs(bounds.x + bounds.width - 1280) < 1);
        assert.ok(Math.abs(bounds.y + bounds.height - 880) < 1);
        await page.clock.fastForward(4000);
        assert.equal(await status.evaluate(node => node.classList.contains('is-fading')), false);
        await page.clock.fastForward(1000);
        assert.equal(await status.evaluate(node => node.classList.contains('is-fading')), true);
        await page.clock.fastForward(250);
        assert.equal(await status.isVisible(), false);
    } finally {
        await browser.close();
        if (server) await new Promise(resolve => server.close(resolve));
    }
});

test('settings actions animate in both directions and Cancel restores entry lists', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true, args: ['--disable-frame-rate-limit']});
    try {
        const page = await browser.newPage();
        await page.route('http://settings.test/**', route => route.fulfill({body: '<html></html>', contentType: 'text/html'}));
        await page.goto('http://settings.test/channel/settings?section=general');
        await page.setContent(`<body class="channel-page-settings"><div data-settings-book data-selected="general"><nav><details class="settings-menu-section"><summary><a data-settings-tab="general">General</a><span class="settings-dirty-dot" hidden></span></summary></details></nav>
            <main class="settings-main settings-pages"><section class="settings-page" data-settings-page="general"><form method="post"><div class="settings-entry-editor" data-settings-list data-entry-label="Name" data-entry-limit="1000"><textarea name="value" data-settings-list-value>First\nSecond</textarea></div><div class="profile-setting-actions"><button name="action" value="save">Save</button></div></form></section></main></div></body>`);
        await page.addStyleTag({path: 'web/static/css/style.css'});
        await page.addStyleTag({path: 'web/static/css/channel-settings.css'});
        for (const file of ['settings-inputs.js', 'channel-settings.js']) await page.addScriptTag({path: `web/static/js/${file}`});
        const inputs = page.locator('.settings-entry-list input');
        const actions = page.locator('.settings-save-reveal');
        assert.equal(await page.locator('[data-settings-cancel]').isVisible(), false);
        await inputs.first().fill('Changed');
        assert.ok(await actions.evaluate(node => { void getComputedStyle(node).opacity; return node.getAnimations().length > 0; }));
        await page.locator('[data-settings-add-entry]').click();
        await inputs.nth(2).fill('Third');
        await page.locator('[data-settings-cancel]').click();
        assert.deepEqual(await inputs.evaluateAll(nodes => nodes.map(node => node.value)), ['First', 'Second']);
        assert.ok(await actions.evaluate(node => { void getComputedStyle(node).opacity; return node.getAnimations().length > 0; }));
        await page.waitForFunction(() => getComputedStyle(document.querySelector('.settings-save-reveal')).visibility === 'hidden');
        assert.equal(await page.locator('[data-settings-save]').isVisible(), false);
        await inputs.first().fill('Changed again');
        await inputs.first().fill('First');
        await page.waitForFunction(() => getComputedStyle(document.querySelector('.settings-save-reveal')).visibility === 'hidden');
        assert.equal(await page.locator('[data-settings-cancel]').isVisible(), false);
    } finally { await browser.close(); }
});
