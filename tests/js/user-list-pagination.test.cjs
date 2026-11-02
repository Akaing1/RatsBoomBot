const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();
const skip = !chromium || !fs.existsSync(executablePath || '');

test('shared user lists paginate independently after ten rows and adjust after changes', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage();
        await page.setContent([10, 11, 21, 0].map((count, index) => `<section><div data-user-list id="list${index}">${Array.from({length: count}, (_, row) => `<article class="user-list-row" data-name="user${row}">User ${row}</article>`).join('')}</div></section>`).join(''));
        await page.addStyleTag({path: 'web/static/css/style.css'});
        await page.addScriptTag({path: 'web/static/js/user-list-pagination.js'});
        const nav = index => page.locator(`#list${index} + .user-list-pagination`);
        const visible = index => page.locator(`#list${index} > .user-list-row:visible`);
        assert.equal(await nav(0).isHidden(), true);
        assert.equal(await nav(3).isHidden(), true);
        assert.equal(await visible(1).count(), 10);
        assert.equal(await visible(2).count(), 10);
        await nav(1).getByRole('button', {name: 'Next page'}).click();
        assert.equal(await visible(1).count(), 1);
        assert.equal(await visible(1).first().getAttribute('data-name'), 'user10');
        assert.equal(await nav(1).locator('span').textContent(), '2 / 2');
        assert.equal(await visible(2).first().getAttribute('data-name'), 'user0');
        await page.evaluate(() => document.querySelector('#list1').lastElementChild.remove());
        assert.equal(await nav(1).isHidden(), true);
        assert.equal(await visible(1).count(), 10);
        await nav(2).getByRole('button', {name: 'Next page'}).click();
        await nav(2).getByRole('button', {name: 'Next page'}).click();
        assert.equal(await visible(2).count(), 1);
        await page.evaluate(() => document.querySelector('#list2').lastElementChild.remove());
        assert.equal(await visible(2).count(), 10);
        assert.equal(await nav(2).locator('span').textContent(), '2 / 2');
        await page.evaluate(() => {
            const row = document.createElement('article'); row.className = 'user-list-row'; row.textContent = 'New user';
            document.querySelector('#list0').append(row);
        });
        assert.equal(await nav(0).isVisible(), true);
        assert.equal(await visible(0).count(), 10);
        await page.evaluate(() => {
            const list = document.createElement('div'); list.dataset.userList = ''; list.id = 'dynamic';
            list.innerHTML = Array.from({length: 12}, (_, n) => `<article class="user-list-row">Dynamic ${n}</article>`).join('');
            document.body.append(list);
        });
        assert.equal(await page.locator('#dynamic > .user-list-row:visible').count(), 10);
        assert.equal(await page.locator('#dynamic + .user-list-pagination').isVisible(), true);
    } finally { await browser.close(); }
});
