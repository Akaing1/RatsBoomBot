const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('dismissed category searches and blank titles restore the latest saved values', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({reducedMotion: 'reduce'});
        const saves = [];
        await page.route('http://metadata.test/**', route => {
            const request = route.request();
            if (request.method() === 'POST') {
                const game = request.postData().includes('name="field"\r\n\r\ngame');
                saves.push(game ? 'game' : 'title');
                return route.fulfill({json: {value: game ? 'New category' : 'New title', box_art_url: 'http://metadata.test/new.svg', announcement_sent: true}});
            }
            if (request.url().includes('/games')) return route.fulfill({json: {games: [{name: 'New category', box_art_url: 'http://metadata.test/new.svg'}]}});
            if (request.url().endsWith('.svg')) return route.fulfill({contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="30"/>'});
            return route.fulfill({body: '<html></html>', contentType: 'text/html'});
        });
        await page.goto('http://metadata.test/');
        await page.setContent(`<section data-channel-metadata data-update-url="/update" data-games-url="/games" data-csrf-token="test">
            <div contenteditable="true" data-channel-field="title">Original title</div>
            <div><img data-current-category-art src="http://metadata.test/original.svg"></div>
            <div contenteditable="true" data-channel-field="game">Original category</div>
            <div data-game-suggestions hidden><div data-game-selection-preview></div><div data-game-options></div></div>
            <p data-channel-metadata-status></p></section><button id="outside">Outside</button>`);
        await page.addScriptTag({path: 'web/static/js/dashboard-channel-metadata.js'});
        const game = page.locator('[data-channel-field="game"]');
        const title = page.locator('[data-channel-field="title"]');
        const outside = page.locator('#outside');
        const picker = page.locator('[data-game-suggestions]');
        await game.focus();
        await page.locator('.twitch-game-option').first().waitFor();
        assert.equal(await page.locator('.twitch-game-option').first().textContent(), 'Original category');
        await game.fill('search text');
        await page.waitForFunction(() => document.querySelectorAll('.twitch-game-option').length === 1);
        assert.equal(await page.locator('.twitch-game-option').first().textContent(), 'New category');
        await outside.click();
        assert.equal(await game.textContent(), 'Original category');
        assert.equal(await picker.isVisible(), false);
        assert.match(await page.locator('[data-current-category-art]').getAttribute('src'), /original\.svg$/);
        assert.equal(saves.length, 0);
        await game.focus();
        await page.locator('.twitch-game-option').filter({hasText: 'New category'}).click();
        await page.waitForFunction(() => document.querySelector('[data-channel-field="game"]').textContent === 'New category');
        await game.fill('discard this');
        await page.evaluate(() => document.dispatchEvent(new Event('dashboard-carousel-card-changed')));
        assert.equal(await game.textContent(), 'New category');
        await title.fill('   ');
        await outside.click();
        assert.equal(await title.textContent(), 'Original title');
        assert.equal(await title.getAttribute('data-has-draft'), null);
        await title.fill('New title');
        await title.press('Enter');
        await page.waitForFunction(() => !document.querySelector('[data-channel-field="title"]').dataset.hasDraft);
        await title.fill('');
        await outside.click();
        assert.equal(await title.textContent(), 'New title');
        assert.deepEqual(saves, ['game', 'title']);
        await title.fill('Keep this draft');
        await outside.click();
        assert.equal(await title.textContent(), 'Keep this draft', 'Nonempty title drafts are retained');
    } finally { await browser.close(); }
});
