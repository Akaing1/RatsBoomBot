const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('custom scrollbars stay disabled across panel closing and overflow changes', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({viewport: {width: 1000, height: 700}});
        await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}</style>
            <div id="commands" style="position:absolute;left:50px;top:50px;width:250px;height:180px;overflow:auto"><div style="height:1200px">Commands</div></div>
            <div id="ordinary" style="position:absolute;left:400px;top:50px;width:250px;height:180px;overflow:auto"><div style="height:1200px">Other content</div></div>`);
        await page.addScriptTag({path: 'web/static/js/overlay-scrollbars.js'});
        await page.waitForFunction(() => document.querySelectorAll('.overlay-scrollbar.axis-y:not([hidden])').length === 2);
        await page.locator('#commands').evaluate(node => node.setAttribute('data-overlay-scrollbars', 'off'));
        await page.waitForFunction(() => document.querySelectorAll('.overlay-scrollbar.axis-y').length === 2);
        for (const overflow of ['hidden', 'auto', 'scroll', 'auto']) {
            await page.locator('#commands').evaluate((node, value) => {
                node.style.overflowY = value;
                node.style.height = value === 'hidden' ? '500px' : '180px';
            }, overflow);
            await page.mouse.move(200, 100);
            await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
            assert.equal(await page.locator('.overlay-scrollbar.axis-y').count(), 2, 'Closing must not recreate the opted-out panel scrollbar');
            assert.equal(await page.locator('.overlay-scrollbar.axis-y:not([hidden])').count(), 1, 'Other scrollbars remain available');
        }
        await page.locator('#commands').evaluate(node => node.removeAttribute('data-overlay-scrollbars'));
        await page.waitForFunction(() => document.querySelectorAll('.overlay-scrollbar.axis-y:not([hidden])').length === 2);
    } finally { await browser.close(); }
});

test('overlay scrollbar remains reachable across its outset and during a drag', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({viewport: {width: 900, height: 700}, reducedMotion: 'reduce'});
        await page.route('**/*', route => route.abort());
        await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}</style>
            <div id="scroller" style="position:absolute;left:60px;top:60px;width:220px;height:220px;overflow:auto;--overlay-scrollbar-outset:12px">
                <div style="height:1800px">Scrollable content</div>
            </div>`);
        await page.addScriptTag({content: fs.readFileSync('web/static/js/overlay-scrollbars.js', 'utf8')});
        await page.mouse.move(270, 100);
        const track = page.locator('.overlay-scrollbar.axis-y:not([hidden])');
        await page.waitForFunction(() => document.querySelector('.overlay-scrollbar.axis-y:not([hidden])')?.classList.contains('is-visible'));
        // The invisible hit area bridges the old gap without thickening the thumb.
        const initialBounds = await track.boundingBox();
        const contentBounds = await page.locator('#scroller').boundingBox();
        assert.ok(initialBounds.x <= contentBounds.x + contentBounds.width);
        assert.equal((await track.locator('.overlay-scrollbar-thumb').boundingBox()).width, 7);
        await page.mouse.move(281, 100);
        await page.waitForTimeout(100);
        assert.equal(await track.evaluate(node => node.classList.contains('is-visible')), true);
        const bounds = await track.boundingBox();
        const x = bounds.x + bounds.width / 2;
        await page.mouse.move(x, bounds.y + 10);
        await page.waitForTimeout(450);
        assert.equal(await track.evaluate(node => node.classList.contains('is-visible')), true,
            'Hovering the scrollbar must keep it visible beyond the grace period');
        await page.mouse.down();
        await page.mouse.move(x + 80, bounds.y + 120, {steps: 5});
        await page.waitForTimeout(450);
        assert.equal(await track.evaluate(node => node.classList.contains('is-visible')), true);
        assert.ok(await page.locator('#scroller').evaluate(node => node.scrollTop) > 0);
        await page.mouse.up();
        await page.mouse.move(800, 600);
        await page.waitForFunction(() => !document.querySelector('.overlay-scrollbar.axis-y:not([hidden])')?.classList.contains('is-visible'));
    } finally {
        await browser.close();
    }
});
