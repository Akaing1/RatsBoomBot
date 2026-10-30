const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();
const skip = !chromium || !fs.existsSync(executablePath || '');

async function setup(browser) {
    const page = await browser.newPage();
    await page.setContent(`<form data-shoutout-user-list data-search-url="/channel/api/automatic-shoutouts/users">
        <textarea name="value"></textarea><input data-shoutout-user-query list="users"><datalist id="users"></datalist>
        <button type="button" data-shoutout-user-add>Add user</button><p data-shoutout-user-status></p></form>`);
    await page.evaluate(() => {
        window.calls = []; window.dirty = 0;
        document.querySelector('textarea').addEventListener('input', () => dirty++);
        window.fetch = async (url, options) => {
            window.calls.push({url, signal: options.signal});
            return {ok: true, json: async () => ({users: [{login: 'alice', display_name: 'Alice'}]})};
        };
    });
    await page.addScriptTag({content: fs.readFileSync('web/static/js/automatic-shoutout-settings.js', 'utf8')});
    return page;
}

test('user autocomplete debounces, caches suggestions and marks list changes for saving', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        const input = page.locator('[data-shoutout-user-query]');
        await input.fill('ali');
        await page.waitForFunction(() => document.querySelector('datalist option')?.value === 'alice');
        assert.equal(await page.locator('datalist option').getAttribute('label'), 'Alice');
        await input.fill(''); await input.fill('ali');
        await page.waitForFunction(() => document.querySelector('datalist option')?.value === 'alice');
        assert.equal(await page.evaluate(() => calls.length), 1);
        await page.locator('textarea').fill('@ALICE');
        await input.fill('alice'); await page.click('[data-shoutout-user-add]');
        assert.equal(await page.locator('textarea').inputValue(), 'alice');
        assert.equal(await input.inputValue(), '');
        assert.match(await page.locator('[data-shoutout-user-status]').textContent(), /Save Changes/);
        assert.ok(await page.evaluate(() => dirty >= 2));
    } finally { await browser.close(); }
});

test('stale suggestions and page-exit requests are cancelled', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.evaluate(() => {
            window.pending = [];
            window.fetch = (url, options) => new Promise(resolve => pending.push({url, signal: options.signal, resolve}));
        });
        const input = page.locator('[data-shoutout-user-query]');
        await input.fill('ali'); await page.waitForFunction(() => pending.length === 1);
        await input.fill('bob'); await page.waitForFunction(() => pending.length === 2);
        assert.equal(await page.evaluate(() => pending[0].signal.aborted), true);
        await page.evaluate(() => {
            pending[1].resolve({ok: true, json: async () => ({users: [{login: 'bob', display_name: 'Bob'}]})});
            pending[0].resolve({ok: true, json: async () => ({users: [{login: 'alice', display_name: 'Alice'}]})});
        });
        await page.waitForFunction(() => document.querySelector('datalist option')?.value === 'bob');
        assert.equal(await page.locator('datalist option').count(), 1);
        await input.fill('carol'); await page.waitForFunction(() => pending.length === 3);
        await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pagehide')));
        assert.equal(await page.evaluate(() => pending[2].signal.aborted), true);
    } finally { await browser.close(); }
});
