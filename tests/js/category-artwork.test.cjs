const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('category artwork selects responsive sources as the preview expands', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({viewport: {width: 1200, height: 1000}, deviceScaleFactor: 2});
        await page.route('https://static-cdn.jtvnw.net/**', route => route.fulfill({contentType: 'image/svg+xml',
            body: '<svg xmlns="http://www.w3.org/2000/svg" width="768" height="1024"/>'}));
        await page.setContent('<img style="width:24px;height:32px">');
        await page.addScriptTag({path: 'web/static/js/category-artwork.js'});
        await page.evaluate(() => categoryArtwork.set(document.querySelector('img'), 'https://static-cdn.jtvnw.net/ttv-boxart/1081998272_IGDB-96x128.jpg'));
        const image = page.locator('img');
        await page.waitForFunction(() => document.querySelector('img').sizes === '24px');
        assert.match(await image.getAttribute('srcset'), /1081998272_IGDB-384x512.jpg 384w/);
        const rewrites = await image.evaluate(async node => {
            let mutations = 0;
            const observer = new MutationObserver(records => { mutations += records.length; });
            observer.observe(node, {attributes: true});
            categoryArtwork.set(node, 'https://static-cdn.jtvnw.net/ttv-boxart/1081998272_IGDB-96x128.jpg');
            await new Promise(resolve => setTimeout(resolve, 50));
            observer.disconnect();
            return mutations;
        });
        assert.equal(rewrites, 0, 'Unchanged artwork does not rewrite sources or restart observation');
        await image.evaluate(node => { node.style.width = '240px'; node.style.height = '320px'; });
        await page.waitForFunction(() => document.querySelector('img').sizes === '240px');
        await page.waitForFunction(() => document.querySelector('img').currentSrc.endsWith('-768x1024.jpg'));
        await image.evaluate(node => { node.style.width = '900px'; });
        await page.waitForFunction(() => !document.querySelector('img').hasAttribute('srcset'));
        assert.match(await image.getAttribute('src'), /1081998272_IGDB\.jpg$/);
        await image.evaluate(node => { node.style.width = '24px'; });
        await page.waitForFunction(() => document.querySelector('img').sizes === '24px');
        await image.evaluate(node => categoryArtwork.set(node, 'https://example.com/art.png', 24));
        assert.equal(await image.getAttribute('srcset'), null);
        assert.equal(await image.getAttribute('src'), 'https://example.com/art.png');
        await image.evaluate(node => categoryArtwork.set(node, ''));
        assert.equal(await image.getAttribute('src'), null);
    } finally { await browser.close(); }
});
