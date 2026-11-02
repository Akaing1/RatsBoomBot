const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();
const skip = !chromium || !fs.existsSync(executablePath || '');

async function setup(browser, immediate = false) {
    const page = await browser.newPage();
    const identity = '<span class="protected-user-avatar"></span><div class="user-list-identity"><strong></strong><small></small></div>';
    await page.setContent(`<body class="channel-page-settings"><div class="settings-page"><div class="profile-setting-card" data-settings-book data-channel="test">
        ${['users', 'blacklist'].map(name => `<div data-shoutout-user-list id="${name}">
            <form data-protected-user-search data-search-url="/channel/protected-users/search"><input name="query"><p data-protected-search-message></p></form>
            <form class="protected-user-result" data-protected-user-result data-user-search-local hidden><input type="hidden" data-protected-result-id><div class="protected-user-result-identity"><div><strong data-protected-result-label></strong><small data-protected-result-user-id></small></div></div><button class="button" data-protected-add>Add</button></form>
            <div data-shoutout-list-members><div class="protected-user-empty">No users added.</div></div>
            <template data-shoutout-row-template><article class="protected-user-row user-list-row">${identity}<button type="button" data-shoutout-list-remove data-user-row-remove>Remove</button></article></template>
            <form data-shoutout-list-form${immediate && name === 'users' ? ' data-shoutout-autosave' : ''}><input type="hidden" name="setting_name" value="automatic_shoutouts.${name}"><input type="hidden" name="value" data-shoutout-list-value value=""></form>
        </div>`).join('')}</div></div></body>`);
    await page.addStyleTag({path: 'web/static/css/style.css'});
    await page.addStyleTag({path: 'web/static/css/channel-settings.css'});
    await page.evaluate(() => {
        window.changes = 0; window.submissions = 0;
        document.addEventListener('input', event => { if (event.target.matches('[data-shoutout-list-value]')) changes++; });
        document.addEventListener('submit', event => { submissions++; event.preventDefault(); });
        window.fetch = async () => ({ok: true, json: async () => ({users: [
            {id: '123', login: 'alice', display_name: 'Alice Display', already_protected: true, related: true,
                profile_image_url: 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs='},
            {id: '456', login: 'alice_other', display_name: 'Alice Other', related: true},
        ]})});
    });
    for (const script of ['user-row-confirmation.js', 'protected-users.js', 'automatic-shoutout-settings.js']) await page.addScriptTag({path: `web/static/js/${script}`});
    return page;
}

test('shared picker adds protected users to a separate shoutout draft using keyboard selection and identity rows', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        const query = page.locator('#users input[name=query]');
        await query.fill('alice');
        await page.waitForSelector('#users [data-protected-user-result]:not([hidden])');
        assert.equal(await page.locator('#users [data-protected-add]').first().isEnabled(), true);
        for (const width of [1200, 600]) {
            await page.setViewportSize({width, height: 900});
            await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
            const identity = await page.locator('#users .protected-user-result-identity').first().boundingBox();
            const button = await page.locator('#users [data-protected-add]').first().boundingBox();
            assert.ok(button.x >= identity.x + identity.width, `Add button stays to the right of the user identity: ${JSON.stringify({width, identity, button, style: await page.locator('#users [data-protected-user-result]').first().evaluate(row => ({direction: getComputedStyle(row).flexDirection, width: getComputedStyle(row).width, gap: getComputedStyle(row).gap}))})}`);
            assert.ok(Math.abs((identity.y + identity.height / 2) - (button.y + button.height / 2)) < 2, 'Identity and action align vertically');
        }
        await query.press('ArrowDown'); await query.press('Enter');
        assert.equal(await page.locator('#users [data-shoutout-list-value]').inputValue(), 'alice');
        assert.equal(await page.locator('#blacklist [data-shoutout-list-value]').inputValue(), '');
        assert.equal(await page.locator('#users .user-list-identity strong').textContent(), 'Alice Display (alice)');
        assert.equal(await page.locator('#users .user-list-identity small').textContent(), '123');
        assert.equal(await page.locator('#users [data-shoutout-list-members] img').count(), 1);
        assert.equal(await page.evaluate(() => submissions), 0);
        await query.fill('alice');
        await page.waitForSelector('#users [data-protected-user-result]:not([hidden])');
        assert.equal(await page.locator('#users [data-protected-add]').first().isDisabled(), true);
        await query.press('Escape');
        await page.locator('#users [data-shoutout-list-remove]').click();
        await page.locator('#users [data-user-row-confirm]').click();
        assert.equal(await page.locator('#users [data-shoutout-list-value]').inputValue(), '');
        assert.equal(await page.locator('#users .protected-user-empty').textContent(), 'No users added.');
        assert.equal(await page.evaluate(() => changes), 2);
    } finally { await browser.close(); }
});

test('cancel restores list rows independently without replacing picker state', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        const query = page.locator('#blacklist input[name=query]');
        await query.fill('alice');
        await page.waitForSelector('#blacklist [data-protected-user-result]:not([hidden])');
        await query.press('ArrowDown'); await query.press('Enter');
        await page.evaluate(() => {
            const form = document.querySelector('#blacklist [data-shoutout-list-form]');
            form.querySelector('[name=value]').value = '';
            form.dispatchEvent(new Event('input', {bubbles: true}));
        });
        assert.equal(await page.locator('#blacklist [data-user-login]').count(), 0);
        assert.equal(await page.locator('#blacklist .protected-user-empty').count(), 1);
        await query.fill('alice');
        await page.waitForSelector('#blacklist [data-protected-user-result]:not([hidden])');
        assert.equal(await page.locator('#blacklist [data-protected-add]').first().isEnabled(), true);
    } finally { await browser.close(); }
});


test('whitelist changes save immediately, queue newer edits, and restore saved rows on failure', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser, true);
        await page.evaluate(() => document.querySelector('#users').dispatchEvent(new CustomEvent('user-search-selected', {
            detail: {id: '123', login: 'alice', display_name: 'Alice'}
        })));
        assert.equal(await page.evaluate(() => submissions), 1);
        await page.locator('#users [data-shoutout-list-remove]').click();
        await page.locator('#users [data-user-row-confirm]').click();
        assert.equal(await page.evaluate(() => submissions), 1);
        await page.evaluate(() => document.querySelector('[data-settings-book]').dispatchEvent(new CustomEvent('settings-saved', {
            detail: {form: document.querySelector('#users [data-shoutout-list-form]'), snapshot: JSON.stringify([['value', 'alice']])}
        })));
        await page.waitForFunction(() => submissions === 2);
        await page.evaluate(() => document.querySelector('[data-settings-book]').dispatchEvent(new CustomEvent('settings-save-failed', {
            detail: {form: document.querySelector('#users [data-shoutout-list-form]')}
        })));
        assert.equal(await page.locator('#users [data-shoutout-list-value]').inputValue(), 'alice');
        assert.equal(await page.locator('#users [data-user-login=alice]').count(), 1);
        await page.locator('#users [data-shoutout-list-remove]').click();
        await page.locator('#users [data-user-row-confirm]').click();
        assert.equal(await page.evaluate(() => submissions), 3);
        assert.equal(await page.locator('#users [data-shoutout-list-value]').inputValue(), '');
    } finally { await browser.close(); }
});


test('added user rows remain alphabetically sorted after additions and cancellation', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        for (const [id, login] of [['3', 'zoe'], ['1', 'alice'], ['2', 'bob']]) {
            await page.evaluate(user => document.querySelector('#blacklist').dispatchEvent(new CustomEvent('user-search-selected', {detail: user})), {id, login, display_name: login});
        }
        assert.deepEqual(await page.locator('#blacklist [data-user-login]').evaluateAll(rows => rows.map(row => row.dataset.userLogin)), ['alice', 'bob', 'zoe']);
        assert.equal(await page.locator('#blacklist [data-shoutout-list-value]').inputValue(), 'alice\nbob\nzoe');
        await page.evaluate(() => {
            const form = document.querySelector('#blacklist [data-shoutout-list-form]');
            form.querySelector('[name=value]').value = 'zoe\nalice';
            form.dispatchEvent(new Event('input', {bubbles: true}));
        });
        assert.deepEqual(await page.locator('#blacklist [data-user-login]').evaluateAll(rows => rows.map(row => row.dataset.userLogin)), ['alice', 'zoe']);
    } finally { await browser.close(); }
});


test('sorted insertion and removal update only the affected user row', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.evaluate(() => {
            const panel = document.querySelector('#blacklist');
            panel.dispatchEvent(new CustomEvent('user-search-selected', {detail: {id: '3', login: 'zoe', display_name: 'Zoe'}}));
            window.removedRows = [];
            new MutationObserver(records => records.forEach(record => record.removedNodes.forEach(node => {
                if (node.dataset?.userLogin) removedRows.push(node.dataset.userLogin);
            }))).observe(panel.querySelector('[data-shoutout-list-members]'), {childList: true});
            for (const [id, login] of [['1', 'alice'], ['2', 'bob']]) panel.dispatchEvent(new CustomEvent('user-search-selected', {detail: {id, login, display_name: login}}));
        });
        assert.deepEqual(await page.evaluate(() => removedRows), [], 'Existing rows are not detached during sorted insertion');
        assert.deepEqual(await page.locator('#blacklist [data-user-login]').evaluateAll(rows => rows.map(row => row.dataset.userLogin)), ['alice', 'bob', 'zoe']);
        await page.locator('#blacklist [data-user-login=bob] [data-shoutout-list-remove]').click();
        await page.locator('#blacklist [data-user-row-confirm]').click();
        assert.deepEqual(await page.evaluate(() => removedRows), ['bob']);
        assert.equal(await page.locator('#blacklist [data-shoutout-list-value]').inputValue(), 'alice\nzoe');
    } finally { await browser.close(); }
});
