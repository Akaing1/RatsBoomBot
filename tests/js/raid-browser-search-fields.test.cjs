const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('all raid-browser search fields use matching clear icons and keep input events and focus', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({viewport: {width: 900, height: 800}});
        await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}</style>
            <form class="raid-browser-filters" data-raid-browser-search style="width:300px">
                <label>Search<input type="search" aria-label="Search" placeholder="Search channels..."></label>
                <label>Category<input type="search" placeholder="Search categories..."></label>
                <label>Tags<input type="search" placeholder="Search tags..."></label>
            </form>`);
        await page.addScriptTag({content: fs.readFileSync('web/static/js/raid-browser-search-fields.js', 'utf8')});
        assert.equal(await page.locator('.raid-browser-search-clear').count(), 3);
        for (const label of ['Search', 'Category', 'Tags']) {
            const clear = page.getByRole('button', {name: `Clear ${label}`, exact: true});
            assert.equal(await clear.isVisible(), false);
            const input = page.getByPlaceholder({Search: 'Search channels...', Category: 'Search categories...', Tags: 'Search tags...'}[label]);
            await input.fill('test');
            assert.equal(await clear.isVisible(), true);
            const before = await input.boundingBox(), button = await clear.boundingBox();
            assert.ok(Math.abs(before.y + before.height / 2 - button.y - button.height / 2) < 1);
            await input.evaluate(node => { node.addEventListener('input', () => { window.cleared = node.value === ''; }); });
            await clear.click();
            assert.equal(await input.inputValue(), '');
            assert.equal(await input.evaluate(node => node === document.activeElement), true);
            assert.equal(await page.evaluate(() => window.cleared), true);
            assert.equal(await clear.isVisible(), false);
            assert.deepEqual(await input.boundingBox(), before);
        }
        assert.equal(await page.locator('.raid-browser-search-clear svg path').first().getAttribute('d'), 'm6 6 12 12M18 6 6 18');
    } finally { await browser.close(); }
});
