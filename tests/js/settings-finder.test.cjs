const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('settings finder opens groups across tabs without losing drafts or searching saved values', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage();
        await page.route('http://settings.test/**', route => route.fulfill({body: '<html></html>', contentType: 'text/html'}));
        await page.goto('http://settings.test/channel/settings');
        await page.setContent(`<div data-settings-book data-selected="events" data-channel="1">
            <div class="settings-tabs">${['events', 'chat'].map(key => `<button data-settings-tab="${key}">${key}<span class="settings-dirty-dot" hidden></span></button>`).join('')}</div>
            <div class="settings-pages">${[['events', 'Follow message', 'follow'], ['chat', 'Lurk message', 'lurk']].map(([key, title, setting]) => `
                <section data-settings-page="${key}"><div class="settings-page-heading"><h3>${key}</h3></div>
                <details class="settings-group"><summary><span class="settings-group-title">${title} group</span></summary>
                    <article class="profile-setting-card" data-setting-key="${setting}"><form method="post">
                    <div class="toggle-card-heading"><h4>${title}</h4></div><textarea name="value">private_saved_message</textarea></form></article>
                </details></section>`).join('')}</div>
            <button data-settings-finder-toggle hidden aria-expanded="false">Find settings</button><aside data-settings-finder hidden><button data-settings-finder-close>Close</button><input><p data-settings-result-count></p><div data-settings-results></div><nav data-settings-shortcuts></nav></aside>
        </div>`);
        for (const file of ['channel-settings.js', 'settings-finder.js']) {
            await page.addScriptTag({content: fs.readFileSync(`web/static/js/${file}`, 'utf8')});
        }
        const toggle = page.locator('[data-settings-finder-toggle]');
        const drawer = page.locator('[data-settings-finder]');
        assert.equal(await drawer.isVisible(), false);
        await toggle.click();
        assert.equal(await toggle.getAttribute('aria-expanded'), 'true');
        const search = page.locator('[data-settings-finder] input');
        assert.equal(await search.evaluate(node => node === document.activeElement), true);
        await page.keyboard.press('Escape');
        assert.equal(await drawer.isVisible(), false);
        assert.equal(await toggle.evaluate(node => node === document.activeElement), true);
        await toggle.click();
        await search.fill('follow');
        await page.locator('[data-settings-results] button').filter({hasText: 'Follow message'}).last().click();
        const draft = page.locator('[data-settings-page="events"] textarea');
        await draft.fill('Unsaved draft');
        await search.fill('lurk');
        await page.locator('[data-settings-results] button').filter({hasText: 'Lurk message'}).last().click();
        assert.equal(await page.locator('[data-settings-page="chat"] details').getAttribute('open'), '');
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
        assert.match(await page.locator('[data-settings-shortcuts]').textContent(), /Follow message group/);
        await page.setViewportSize({width: 390, height: 844});
        await search.fill('lurk');
        await page.locator('[data-settings-results] button').filter({hasText: 'Lurk message'}).last().click();
        assert.equal(await drawer.isVisible(), false);
        assert.equal(await toggle.getAttribute('aria-expanded'), 'false');
        assert.equal(await page.locator('[data-settings-page="chat"] textarea').evaluate(node => node === document.activeElement), true);
        await toggle.click();
        await page.locator('[data-settings-finder-close]').click();
        assert.equal(await drawer.isVisible(), false);
    } finally { await browser.close(); }
});
