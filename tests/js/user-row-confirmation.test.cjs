const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();
const skip = !chromium || !fs.existsSync(executablePath || '');

test('user-row removals require the sliding X and cancel on outside click or Escape', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({viewport: {width: 600, height: 800}});
        await page.setContent(`<div id="rows"><article class="user-list-row" id="one"><div class="user-list-identity"><strong>Alice</strong><small>123</small></div><form><button class="button" type="submit" name="action" value="remove" data-user-row-remove>Remove</button></form></article></div><button id="outside">Outside</button>`);
        await page.addStyleTag({path: 'web/static/css/style.css'});
        await page.addStyleTag({content: '.user-list-row{width:260px}'});
        await page.evaluate(() => {
            window.submits = []; window.removals = 0;
            document.addEventListener('submit', event => { event.preventDefault(); submits.push(event.submitter.value); });
            window.confirm = () => { throw new Error('Popup confirmation must not be used'); };
        });
        await page.addScriptTag({path: 'web/static/js/user-row-confirmation.js'});
        const remove = page.locator('#one [data-user-row-remove]');
        await page.evaluate(() => document.querySelector('#one [data-user-row-remove]').click());
        assert.ok(await page.locator('#one [data-user-row-confirm]').evaluate(button => button.getAnimations().length > 0), 'First opening has a slide animation');
        assert.equal(await remove.textContent(), 'Remove');
        assert.deepEqual(await page.evaluate(() => submits), []);
        await page.locator('#outside').click();
        assert.equal(await remove.textContent(), 'Remove');
        await remove.click(); await page.locator('#outside').click();
        assert.equal(await remove.getAttribute('aria-expanded'), 'false');
        await remove.click(); await page.keyboard.press('Escape');
        assert.equal(await remove.getAttribute('aria-expanded'), 'false');
        await page.evaluate(() => {
            const row = document.createElement('article'); row.id = 'two'; row.className = 'user-list-row';
            row.innerHTML = '<div class="user-list-identity"><strong>Bob</strong></div><button type="button" data-user-row-remove>Remove</button>';
            row.querySelector('button').addEventListener('click', () => removals++);
            document.querySelector('#rows').append(row);
        });
        await remove.click(); await page.locator('#two [data-user-row-remove]').click();
        assert.equal(await remove.getAttribute('aria-expanded'), 'false');
        assert.equal(await page.evaluate(() => removals), 0);
        await page.locator('#two [data-user-row-confirm]').click();
        assert.equal(await page.evaluate(() => removals), 1);
        await remove.click();
        await page.waitForTimeout(250);
        const row = await page.locator('#one').boundingBox();
        const confirm = await page.locator('#one [data-user-row-confirm]').boundingBox();
        assert.ok(confirm.x + confirm.width <= row.x + row.width, 'Confirmation remains inside the row');
        const icon = await page.locator('#one [data-user-row-confirm] svg').boundingBox();
        assert.ok(Math.abs(icon.x + icon.width / 2 - confirm.x - confirm.width / 2) < 1, 'X is horizontally centered');
        assert.ok(Math.abs(icon.y + icon.height / 2 - confirm.y - confirm.height / 2) < 1, 'X is vertically centered');
        await page.locator('#one [data-user-row-confirm]').click();
        assert.deepEqual(await page.evaluate(() => submits), ['remove']);
        assert.equal(await remove.textContent(), 'Remove');
    } finally { await browser.close(); }
});
