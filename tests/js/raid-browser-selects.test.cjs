const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();
const skip = !chromium || !fs.existsSync(executablePath || '');

async function fixture(browser, width = 1100) {
    const page = await browser.newPage({viewport: {width, height: 800}});
    const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
    const markup = '<dialog id="dashboard-raid-browser"' + template.split('<dialog id="dashboard-raid-browser"')[1].split('</dialog>')[0] + '</dialog>';
    await page.route('**/*', route => route.abort());
    await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}</style>${markup}`);
    await page.evaluate(() => {
        const dialog = document.querySelector('dialog');
        dialog.showModal(); dialog.classList.add('is-filters-open');
        window.changes = [];
        dialog.querySelector('form').addEventListener('change', event => window.changes.push([event.target.name, event.target.value]));
    });
    await page.addScriptTag({content: fs.readFileSync('web/static/js/raid-browser-selects.js', 'utf8')});
    return page;
}

test('raid filter menus share category styling and preserve selection, keyboard, dismissal, and reset', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await fixture(browser);
        assert.equal(await page.locator('.raid-browser-select-trigger').count(), 5);
        const following = page.getByRole('combobox', {name: 'Following: Any', exact: true});
        await following.click();
        const menu = page.locator('#raid-browser-select-follow_status');
        assert.equal(await menu.isVisible(), true);
        assert.equal(await menu.evaluate(node => getComputedStyle(node).backgroundColor),
            await page.locator('#raid-browser-category-options').evaluate(node => getComputedStyle(node).backgroundColor));
        await page.keyboard.press('ArrowDown'); await page.keyboard.press('Enter');
        assert.equal(await page.locator('select[name="follow_status"]').inputValue(), 'not_following');
        assert.deepEqual(await page.evaluate(() => window.changes), [['follow_status', 'not_following']]);
        assert.equal(await menu.isVisible(), false);
        const selected = page.getByRole('combobox', {name: 'Following: Not following', exact: true});
        await selected.press('ArrowDown'); await page.keyboard.press('End'); await page.keyboard.press('Escape');
        assert.equal(await selected.evaluate(node => node === document.activeElement), true);
        assert.equal(await page.locator('dialog').evaluate(node => node.open), true);
        await selected.click();
        await page.getByRole('combobox', {name: 'Sort by: For You', exact: true}).click();
        assert.equal(await menu.isVisible(), false);
        assert.equal(await page.locator('#raid-browser-select-sort').isVisible(), true);
        await page.keyboard.press('Escape');
        await page.evaluate(() => document.querySelector('form').reset());
        await page.waitForFunction(() => document.querySelector('[name="follow_status"]').previousElementSibling.textContent === 'Any');
    } finally { await browser.close(); }
});

test('mobile team options update dynamically and the popup fits the filter width', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await fixture(browser, 390);
        await page.evaluate(() => {
            document.querySelector('[data-raid-team-filter]').hidden = false;
            const select = document.querySelector('[name="team"]');
            select.append(new Option('Team One', 'Team One'), new Option('Team Two', 'Team Two'));
        });
        const trigger = page.getByRole('combobox', {name: 'Stream team: All teams', exact: true});
        await trigger.scrollIntoViewIfNeeded(); await trigger.click();
        const menu = page.locator('#raid-browser-select-team');
        assert.equal(await menu.getByRole('option').count(), 3);
        const rect = await menu.boundingBox(), input = await trigger.boundingBox();
        assert.ok(Math.abs(rect.width - input.width) < 1);
        assert.ok(rect.y >= 0 && rect.y + rect.height <= 800);
        await menu.getByRole('option', {name: 'Team Two', exact: true}).click();
        assert.deepEqual(await page.evaluate(() => window.changes), [['team', 'Team Two']]);
        await page.evaluate(() => { document.querySelector('[name="team"]').disabled = true; });
        await page.waitForFunction(() => document.querySelector('[name="team"]').previousElementSibling.disabled);
    } finally { await browser.close(); }
});
