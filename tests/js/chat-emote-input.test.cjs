const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('rich emote input in an isolated browser', {skip: !chromium || !fs.existsSync(executablePath || '')}, async t => {
    const browser = await chromium.launch({executablePath, headless: true});
    async function fixture(preview = false) {
        const page = await browser.newPage();
        await page.route('**/*', route => route.abort());
        await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}</style>
            <div class="${preview ? 'raid-preview-chat' : ''}"><form class="dashboard-chat-composer">
            <div class="${preview ? '' : 'dashboard-chat-compose-row'}"><div class="chat-message-entry">
            <textarea name="message" maxlength="500" placeholder="Send a message…" required></textarea><div id="suggestions" hidden></div>
            </div><button type="submit">Send</button></div><p id="status"></p></form></div>`);
        for (const script of ['chat-emote-input', 'chat-autocomplete', 'chat-composer']) {
            await page.addScriptTag({content: fs.readFileSync(`web/static/js/${script}.js`, 'utf8')});
        }
        await page.evaluate(() => {
            window.catalog = [{name: 'Kappa', provider: 'twitch', url: 'https://static-cdn.jtvnw.net/emoticons/v2/25/static/dark/2.0'}];
            window.limits = 0; window.sent = []; window.emotesEnabled = true;
            const source = document.querySelector('textarea'), form = document.querySelector('form');
            window.rich = window.createChatEmoteInput({input: source, getEmotes: () => window.catalog,
                enabled: () => window.emotesEnabled, onLimit: () => { window.limits++; }});
            window.composer = window.createChatComposer({form, input: window.rich,
                sendButton: form.querySelector('button'), status: document.querySelector('#status'),
                autocomplete: {box: document.querySelector('#suggestions'), getEmotes: () => window.catalog},
                send: async message => { window.sent.push(message); return {}; }});
            window.rich.focus();
        });
        return page;
    }
    try {
        await t.test('typed emotes display inline and Backspace/Delete remove whole codes', async () => {
            const page = await fixture();
            await page.keyboard.type('hello Kappa ');
            assert.equal(await page.locator('.chat-input-emote').count(), 1);
            assert.equal(await page.evaluate(() => window.rich.value), 'hello Kappa ');
            assert.equal(await page.locator('textarea').isVisible(), false);
            await page.keyboard.press('Backspace'); await page.keyboard.press('Backspace');
            assert.equal(await page.evaluate(() => window.rich.value), 'hello ');
            await page.keyboard.press('Control+z');
            assert.equal(await page.evaluate(() => window.rich.value), 'hello Kappa');
            assert.equal(await page.locator('.chat-input-emote').count(), 1);
            await page.evaluate(() => window.rich.setSelectionRange(6, 6));
            await page.keyboard.press('Delete');
            assert.equal(await page.evaluate(() => window.rich.value), 'hello ');
            await page.close();
        });
        await t.test('typing after an emote reuses its image and narrow inputs wrap within their bounds', async () => {
            const page = await fixture();
            await page.setViewportSize({width: 400, height: 800});
            await page.keyboard.type('Kappa');
            await page.evaluate(() => { window.originalImage = document.querySelector('.chat-input-emote'); });
            await page.keyboard.type(' hello');
            assert.equal(await page.evaluate(() => document.querySelector('.chat-input-emote') === window.originalImage), true);
            await page.keyboard.type(' word'.repeat(40));
            const bounds = await page.locator('.chat-rich-input').evaluate(node => ({
                width: node.clientWidth, scrollWidth: node.scrollWidth, height: node.clientHeight,
                maxHeight: parseFloat(getComputedStyle(node).maxHeight)
            }));
            assert.ok(bounds.scrollWidth <= bounds.width);
            assert.ok(bounds.height <= bounds.maxHeight);
            await page.close();
        });
        await t.test('picker-style replacement and sending retain plain-text codes in both layouts', async () => {
            for (const preview of [false, true]) {
                const page = await fixture(preview);
                await page.evaluate(() => {
                    window.rich.setRangeText('Kappa hi', 0, 0, 'end');
                    window.rich.dispatchEvent(new Event('input', {bubbles: true}));
                });
                assert.equal(await page.locator('.chat-input-emote').count(), 1);
                await page.keyboard.press('Enter');
                assert.deepEqual(await page.evaluate(() => window.sent), ['Kappa hi']);
                assert.equal(await page.evaluate(() => window.rich.value), '');
                assert.equal(await page.locator('.chat-input-emote').count(), 0);
                await page.close();
            }
        });
        await t.test('pasting and copying use text codes, never pasted HTML', async () => {
            const page = await fixture();
            const result = await page.evaluate(() => {
                const data = new DataTransfer(); data.setData('text/plain', 'Kappa <b>hello</b>'); data.setData('text/html', '<b>unsafe</b>');
                window.rich.element.dispatchEvent(new ClipboardEvent('paste', {clipboardData: data, bubbles: true, cancelable: true}));
                window.rich.setSelectionRange(0, 5);
                const copied = new DataTransfer();
                window.rich.element.dispatchEvent(new ClipboardEvent('copy', {clipboardData: copied, bubbles: true, cancelable: true}));
                return {value: window.rich.value, copied: copied.getData('text/plain'), html: window.rich.element.querySelectorAll('b').length};
            });
            assert.deepEqual(result, {value: 'Kappa <b>hello</b>', copied: 'Kappa', html: 0});
            await page.close();
        });
        await t.test('line breaks, selection cuts, redo and IME composition keep the draft intact', async () => {
            const page = await fixture(true);
            await page.keyboard.type('Kappa');
            await page.keyboard.press('Shift+Enter');
            await page.keyboard.type('hello');
            assert.equal(await page.evaluate(() => window.rich.value), 'Kappa\nhello');
            await page.evaluate(() => {
                window.rich.setSelectionRange(0, 5);
                window.rich.element.dispatchEvent(new ClipboardEvent('cut', {clipboardData: new DataTransfer(), bubbles: true, cancelable: true}));
            });
            assert.equal(await page.evaluate(() => window.rich.value), '\nhello');
            await page.keyboard.press('Control+z');
            assert.equal(await page.locator('.chat-input-emote').count(), 1);
            await page.keyboard.press('Control+Shift+z');
            assert.equal(await page.locator('.chat-input-emote').count(), 0);
            await page.evaluate(() => {
                window.rich.value = '';
                const editor = window.rich.element;
                editor.dispatchEvent(new CompositionEvent('compositionstart', {bubbles: true}));
                editor.textContent = 'こんにちは';
                editor.dispatchEvent(new InputEvent('input', {inputType: 'insertCompositionText', data: 'こんにちは', isComposing: true, bubbles: true}));
                editor.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', isComposing: true, bubbles: true}));
                editor.dispatchEvent(new CompositionEvent('compositionend', {data: 'こんにちは', bubbles: true}));
            });
            assert.equal(await page.evaluate(() => window.rich.value), 'こんにちは');
            assert.deepEqual(await page.evaluate(() => window.sent), []);
            await page.close();
        });
        await t.test('limits, catalog refresh, target switching, and teardown remain intact', async () => {
            const page = await fixture();
            await page.keyboard.insertText('x'.repeat(501));
            assert.equal(await page.evaluate(() => window.rich.value), '');
            assert.equal(await page.evaluate(() => window.limits), 1);
            await page.evaluate(() => { window.rich.value = 'Kappa'; window.emotesEnabled = false; window.rich.refreshEmotes(); });
            assert.equal(await page.locator('.chat-input-emote').count(), 0);
            await page.evaluate(() => { window.emotesEnabled = true; window.rich.refreshEmotes(); });
            assert.equal(await page.locator('.chat-input-emote').count(), 1);
            await page.evaluate(() => { window.catalog = []; window.rich.refreshEmotes(); });
            assert.equal(await page.locator('.chat-input-emote').count(), 0);
            await page.evaluate(() => window.composer.destroy());
            assert.equal(await page.locator('.chat-rich-input').count(), 0);
            assert.equal(await page.locator('textarea').inputValue(), 'Kappa');
            assert.equal(await page.locator('textarea').isVisible(), true);
            await page.close();
        });
        await t.test('dashboard integration preserves autocomplete, platform switching, history and All sends', async () => {
            const page = await browser.newPage();
            await page.route('**/*', route => route.abort());
            const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
            const form = template.match(/<form class="dashboard-chat-composer" data-chat-composer[\s\S]*?<\/form>/)[0];
            await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}</style>${form}`);
            await page.evaluate(() => {
                document.querySelector('form').dataset.youtubeConnected = 'true';
                window.sent = [];
                window.fetch = async (url, options) => ({ok: true, json: async () => {
                    if (String(url).endsWith('/send')) {
                        window.sent.push({message: options.body.get('message'), target: options.body.get('target')});
                        return {sent: ['twitch', 'youtube'], errors: {}};
                    }
                    return {emotes: [{name: 'Kappa', provider: 'twitch', url: 'https://static-cdn.jtvnw.net/emoticons/v2/25/static/dark/2.0'}], users: []};
                }});
            });
            for (const script of ['chat-emote-input', 'chat-autocomplete', 'chat-composer', 'chat-target-selector', 'chat-emote-picker', 'dashboard-chat-send']) {
                await page.addScriptTag({content: fs.readFileSync(`web/static/js/${script}.js`, 'utf8')});
            }
            await page.locator('.chat-rich-input').click();
            await page.keyboard.type(':kap'); await page.keyboard.press('Tab');
            assert.equal(await page.locator('.chat-input-emote').count(), 1);
            assert.equal(await page.locator('textarea').inputValue(), 'Kappa ');
            await page.locator('[data-chat-target-cycle]').click();
            assert.equal(await page.locator('.chat-input-emote').count(), 0, 'YouTube keeps text emote codes');
            await page.locator('[data-chat-target-cycle]').click();
            assert.equal(await page.locator('.chat-input-emote').count(), 1);
            await page.locator('.chat-rich-input').click();
            await page.keyboard.press('Shift+Enter');
            await page.waitForFunction(() => window.sent.length === 1);
            assert.deepEqual(await page.evaluate(() => window.sent), [{message: 'Kappa', target: 'both'}]);
            await page.keyboard.press('ArrowUp');
            assert.equal(await page.locator('textarea').inputValue(), 'Kappa');
            assert.equal(await page.locator('.chat-input-emote').count(), 1);
            const indent = await page.locator('.chat-rich-input').evaluate(node => parseFloat(getComputedStyle(node).textIndent));
            assert.ok(indent > 20, 'The first line still reserves space for the platform selector');
            await page.close();
        });
        await t.test('preview integration inserts picker emotes and sends text codes', async () => {
            const page = await browser.newPage();
            await page.route('**/*', route => route.abort());
            await page.route('https://chat-input.test.invalid/', route => route.fulfill({contentType: 'text/html', body: '<!doctype html>'}));
            await page.goto('https://chat-input.test.invalid/');
            await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}</style><div class="raid-preview-chat" style="height:500px"></div>`);
            await page.evaluate(() => {
                window.sent = [];
                window.EventSource = class {close() {}};
                window.fetch = async (url, options) => ({ok: true, json: async () => {
                    if (String(url).endsWith('/send')) { window.sent.push(options.body.get('message')); return {sent: true}; }
                    return {emotes: [{name: 'Kappa', provider: 'twitch', url: 'https://static-cdn.jtvnw.net/emoticons/v2/25/static/dark/2.0'}]};
                }});
            });
            for (const script of ['chat-emote-input', 'chat-autocomplete', 'chat-composer', 'chat-emote-picker', 'live-chat-feed', 'raid-preview-chat']) {
                await page.addScriptTag({content: fs.readFileSync(`web/static/js/${script}.js`, 'utf8')});
            }
            await page.evaluate(() => { window.preview = window.createRaidPreviewChat(document.querySelector('.raid-preview-chat'), {id: '2', login: 'target'}, 'test'); });
            await page.locator('.chat-emote-toggle').click();
            await page.locator('.chat-emote-option').click();
            assert.equal(await page.locator('.chat-rich-input img').count(), 1);
            await page.keyboard.press('Enter');
            await page.waitForFunction(() => window.sent.length === 1);
            assert.deepEqual(await page.evaluate(() => window.sent), ['Kappa']);
            await page.evaluate(() => window.preview.destroy());
            assert.equal(await page.locator('.chat-rich-input').count(), 0);
            await page.close();
        });
    } finally { await browser.close(); }
});
