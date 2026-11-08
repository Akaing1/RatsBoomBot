const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();
const skip = !chromium || !fs.existsSync(executablePath || '');

test('navigation pin preference survives layout changes, refreshes, and mobile navigation', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({viewport: {width: 1400, height: 900}});
        await page.route('http://navigation.test/**', route => route.fulfill({contentType: 'text/html', body: `
            <div data-dashboard-shell data-sidebar-storage-key="test-navigation">
                <aside class="sidebar"><button data-sidebar-toggle><span></span></button>
                    <button data-sidebar-mobile-toggle></button><button data-sidebar-mobile-back></button>
                </aside>
            </div>`}));
        const load = async () => {
            await page.goto('http://navigation.test/');
            await page.addScriptTag({path: 'web/static/js/channel-sidebar.js'});
        };
        const expanded = () => page.locator('[data-sidebar-toggle]').getAttribute('aria-expanded');
        const resize = async width => {
            await page.setViewportSize({width, height: 900});
            await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        };
        await load();
        assert.equal(await expanded(), 'true');
        await page.locator('[data-sidebar-toggle]').click();
        for (const width of [1000, 850, 1400]) {
            await resize(width);
            assert.equal(await expanded(), 'false', `Collapsed preference at ${width}px`);
        }
        await resize(1000);
        await page.locator('[data-sidebar-toggle]').click();
        assert.equal(await page.evaluate(() => localStorage.getItem('test-navigation')), 'false');
        for (const width of [1400, 850, 1000]) {
            await resize(width);
            assert.equal(await expanded(), 'true', `Pinned preference at ${width}px`);
        }
        await load();
        assert.equal(await expanded(), 'true', 'Compact refresh restores the saved pin');
        await resize(600);
        assert.equal(await expanded(), 'false', 'Mobile navigation starts closed');
        await page.locator('[data-sidebar-mobile-toggle]').click();
        assert.equal(await expanded(), 'true');
        await page.locator('[data-sidebar-mobile-back]').click();
        await resize(1400);
        assert.equal(await expanded(), 'true', 'Closing mobile navigation does not unpin desktop');
        await page.evaluate(() => localStorage.clear());
        await resize(1000);
        await load();
        assert.equal(await expanded(), 'false', 'First compact visit keeps the compact default');
        await page.locator('[data-sidebar-toggle]').click();
        await page.locator('[data-sidebar-toggle]').click();
        await resize(1400);
        await load();
        assert.equal(await expanded(), 'false', 'Compact collapse is also saved for wide refreshes');
    } finally { await browser.close(); }
});
