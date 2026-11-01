const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();
const skip = !chromium || !fs.existsSync(executablePath || '');

async function setup(browser, names = '') {
    const page = await browser.newPage({viewport: {width: 1000, height: 800}});
    await page.setContent(`<body class="channel-page-settings"><div class="settings-book" data-settings-book><section class="settings-page"><form method="post">
        <textarea name="message" rows="1" data-settings-grow class="profile-setting-input"></textarea>
        <div data-settings-list data-entry-label="Boss names" data-entry-placeholder="Enter a name" data-entry-limit="1000">
            <textarea name="value" data-settings-list-value>${names}</textarea>
        </div></form></section></div></body>`);
    for (const file of ['style.css', 'channel-settings.css']) await page.addStyleTag({path: `web/static/css/${file}`});
    await page.addScriptTag({path: 'web/static/js/settings-inputs.js'});
    return page;
}

test('single-message fields grow with text and shrink when cleared', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        const input = page.locator('[data-settings-grow]');
        const initial = await input.evaluate(el => el.offsetHeight);
        assert.ok(initial < 60);
        await input.fill('A long message with spaces. '.repeat(60));
        assert.ok(await input.evaluate(el => el.offsetHeight) > initial * 2);
        await input.fill('');
        assert.equal(await input.evaluate(el => el.offsetHeight), initial);
    } finally { await browser.close(); }
});

test('entry fields preserve saved order, add and remove names and enforce the combined limit', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser, 'First\nSecond');
        const inputs = page.locator('.settings-entry-row input');
        assert.equal(await inputs.count(), 2);
        assert.equal(await inputs.nth(0).inputValue(), 'First');
        assert.equal(await inputs.nth(1).inputValue(), 'Second');
        await page.locator('[data-settings-add-entry]').click();
        await inputs.nth(2).fill('Third');
        const saved = () => page.locator('form').evaluate(form => new FormData(form).get('value'));
        assert.equal(await saved(), 'First\nSecond\nThird');
        await page.locator('.settings-entry-remove').nth(1).click();
        assert.equal(await saved(), 'First\nThird');
        await page.locator('.settings-entry-remove').nth(1).click();
        assert.equal(await page.locator('.settings-entry-remove').isDisabled(), true);
        await inputs.first().fill('');
        assert.equal(await saved(), '');
        for (let index = 0; index < 11; index++) {
            if (index) await page.locator('[data-settings-add-entry]').click();
            await inputs.nth(index).fill('x'.repeat(100));
        }
        assert.equal(await inputs.first().evaluate(el => el.validity.valid), false);
        await page.locator('.settings-entry-remove').last().click();
        await page.locator('.settings-entry-remove').last().click();
        assert.equal(await inputs.first().evaluate(el => el.validity.valid), true);
    } finally { await browser.close(); }
});
