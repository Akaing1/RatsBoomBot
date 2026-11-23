const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('shared toggles retain the clicked hover label until leaving and rehovering',
    {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
        const browser = await chromium.launch({executablePath, headless: true});
        try {
            const page = await browser.newPage();
            const errors = []; page.on('pageerror', error => errors.push(error.message));
            await page.setContent('<button class="state-toggle" role="switch" aria-label="Feature" aria-checked="false"><span class="state-toggle-current">Disabled</span><span class="state-toggle-alternate" aria-hidden="true">Enable</span></button><button id="away">Other control</button>');
            await page.addStyleTag({path: 'web/static/css/style.css'});
            await page.addScriptTag({path: 'web/static/js/state-toggle.js'});
            await page.evaluate(() => {
                document.querySelector('.state-toggle').addEventListener('click', event => {
                    const button = event.currentTarget;
                    const enabled = button.getAttribute('aria-checked') !== 'true';
                    button.setAttribute('aria-checked', String(enabled));
                    // Settings saves can replace all label nodes asynchronously.
                    setTimeout(() => {
                        button.className = enabled ? 'state-toggle live' : 'state-toggle';
                        button.innerHTML = `<span class="state-toggle-current">${enabled ? 'Enabled' : 'Disabled'}</span><span class="state-toggle-alternate" aria-hidden="true">${enabled ? 'Disable' : 'Enable'}</span>`;
                    }, 10);
                });
            });
            const toggle = page.getByRole('switch', {name: 'Feature'});
            await toggle.hover();
            await toggle.click();
            await page.waitForFunction(() => document.querySelector('.state-toggle-current').textContent === 'Enabled');
            assert.equal(await toggle.getAttribute('aria-checked'), 'true');
            assert.equal(await toggle.getAttribute('data-toggle-hover-label'), 'Enable');
            assert.equal(await toggle.evaluate(button => getComputedStyle(button, '::before').content), '"Enable"');
            await page.locator('#away').hover();
            assert.equal(await toggle.getAttribute('data-toggle-hover-label'), null);
            await toggle.hover();
            assert.equal(await toggle.locator('.state-toggle-alternate').innerText(), 'Disable');
            await toggle.click();
            await page.waitForFunction(() => document.querySelector('.state-toggle-current').textContent === 'Disabled');
            assert.equal(await toggle.getAttribute('data-toggle-hover-label'), 'Disable');
            await page.locator('#away').hover();
            await toggle.focus();
            await page.keyboard.press('Space');
            await page.waitForFunction(() => document.querySelector('.state-toggle-current').textContent === 'Enabled');
            assert.equal(await toggle.getAttribute('data-toggle-hover-label'), 'Enable');
            await page.locator('#away').focus();
            assert.equal(await toggle.getAttribute('data-toggle-hover-label'), null);
            assert.deepEqual(errors, []);
        } finally { await browser.close(); }
    });
