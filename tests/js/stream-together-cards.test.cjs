const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('call cards use balanced rows, expand with bottom mini previews, and preserve playback during updates',
    {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
        const browser = await chromium.launch({executablePath, headless: true});
        try {
            const page = await browser.newPage({viewport: {width: 1540, height: 1000}});
            const errors = []; page.on('pageerror', error => errors.push(error.message));
            await page.route('https://images.test/**', route => route.fulfill({contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"><rect width="640" height="360" fill="#332c50"/><path d="M0 250L180 70 420 320 640 100" stroke="#8b5cf6" stroke-width="20" fill="none"/></svg>'}));
            await page.setContent(`<dialog open class="raid-browser-dialog stream-together-dialog"><header class="stream-together-header"><h3>Stream Together</h3></header>
                <section class="stream-together-controls"><p>Starting a session opens Twitch’s call page in a new tab or window. Keep it open; we recommend minimizing it.</p>
                <div class="stream-call-stage">
                    <div class="stream-call-grid" data-stream-cards></div></div>
                <footer class="stream-call-footer">Call controls</footer></section></dialog>`);
            for (const css of ['style', 'dashboard-stream-together']) await page.addStyleTag({path: `web/static/css/${css}.css`});
            await page.addScriptTag({path: 'web/static/js/dashboard-participant-order.js'});
            await page.addScriptTag({path: 'web/static/js/dashboard-stream-together-cards.js'});
            await page.evaluate(() => {
                window.created = []; window.destroyed = []; window.selection = null;
                window.createRaidPreviewPlayer = (host, login, report) => {
                    created.push(login); const mount = document.createElement('div'); mount.className = 'raid-preview-player'; mount.textContent = `Playing ${login}`; host.append(mount);
                    setTimeout(() => report(''), 0);
                    return {destroy() { destroyed.push(login); mount.remove(); }};
                };
                window.model = Array.from({length: 6}, (_, i) => ({user_id: String(i + 1), user_login: `person${i + 1}`,
                    user_display_name: `Person ${i + 1}`, slot_id: String(i), is_streaming: i !== 5,
                    thumbnail_url: 'https://images.test/stream.svg', profile_image_url: 'https://images.test/avatar.svg'}));
                window.kicked = [];
                window.cards = createStreamTogetherCards(document.querySelector('.stream-together-controls'), guest => { selection = guest?.user_id; }, guest => kicked.push(guest.user_id));
            });
            const expected = {2: [2], 3: [2, 1], 4: [2, 2], 5: [3, 2], 6: [3, 3]};
            async function assertVideoRatios() {
                await page.waitForFunction(() => {
                    const grid = document.querySelector('[data-stream-cards]');
                    return !grid.getAnimations({subtree: true}).length
                        && parseFloat(grid.style.getPropertyValue('--stream-call-grid-height')) === grid.parentElement.clientHeight - 4;
                });
                await page.waitForFunction(() => [...document.querySelectorAll('.stream-call-card:not([hidden]) .stream-call-media')].every(media => {
                    const rect = media.getBoundingClientRect();
                    return rect.width > 0 && Math.abs(rect.width - rect.height * 16 / 9) < 1;
                }));
                assert.equal(await page.locator('.stream-call-card:visible').evaluateAll(cards => cards.every(card => {
                    const media = card.querySelector('.stream-call-media').getBoundingClientRect();
                    return Math.abs(card.clientHeight - media.height) < 1 && Math.abs(card.clientWidth - media.width) < 1;
                })), true, 'Cards fit their video and caption without black bars');
                assert.equal(await page.locator('.stream-call-grid.is-focused').evaluateAll(grids => grids.every(grid => {
                    const selected = grid.querySelector('.is-selected').getBoundingClientRect();
                    return [...grid.querySelectorAll('.stream-call-card:not(.is-selected):not([hidden])')].every(card =>
                        Math.abs(card.getBoundingClientRect().top - selected.bottom - 8) < 1);
                })), true, 'Mini previews stay eight pixels below the main video at every window size');
                assert.equal(await page.locator('.stream-call-grid.is-focused').evaluateAll(grids => grids.every(grid => {
                    const minis = [...grid.querySelectorAll('.stream-call-card:not(.is-selected):not([hidden])')];
                    if (!minis.length) return true;
                    const rowWidth = minis.reduce((sum, card) => sum + card.getBoundingClientRect().width, 0) + (minis.length - 1) * 8;
                    return Math.abs(rowWidth - grid.clientWidth) < 2 || Math.abs(grid.clientHeight - grid.parentElement.clientHeight + 4) < 2;
                })), true, 'Mini previews fill the available width or height without a fixed size cap');
            }
            for (let count = 2; count <= 6; count++) {
                await page.evaluate(count => cards.update(model.slice(0, count)), count);
                const rows = await page.locator('.stream-call-card').evaluateAll(cards => {
                    const rows = [];
                    for (const card of cards) { const top = Math.round(card.getBoundingClientRect().top); let row = rows.find(row => Math.abs(row.top - top) < 2); if (!row) rows.push(row = {top, count: 0}); row.count++; }
                    return rows.map(row => row.count);
                });
                assert.deepEqual(rows, expected[count], `${count} participants use the requested rows`);
                await assertVideoRatios();
            }
            await page.screenshot({path: '.data/stream-call-grid-six.png'});
            const second = page.locator('.stream-call-card[data-user-id="2"]');
            assert.equal(await second.locator('.stream-call-portrait').isVisible(), true);
            await page.getByRole('button', {name: 'Person 1 options', exact: true}).click();
            assert.equal(await page.getByRole('menuitem', {name: 'Kick', exact: true}).isVisible(), false, 'The host cannot be kicked');
            await page.keyboard.press('Escape');
            await page.getByRole('button', {name: 'Person 2 options', exact: true}).click();
            await page.getByRole('menuitem', {name: 'Hide video', exact: true}).click();
            assert.equal(await second.locator('.stream-call-avatar').isVisible(), true);
            assert.equal(await second.locator('.stream-call-poster').isVisible(), false);
            assert.equal(await page.locator('.stream-call-grid').evaluate(grid => grid.classList.contains('is-focused')), false, 'Opening the menu does not expand a card');
            await page.evaluate(() => cards.update(model.map(guest => ({...guest}))));
            assert.equal(await second.locator('.stream-call-poster').isVisible(), false, 'Local hiding survives participant refreshes');
            await page.evaluate(() => cards.hideOffline(true));
            assert.equal(await second.isVisible(), false, 'The non-streaming filter also hides locally hidden videos');
            assert.equal(await page.locator('.stream-call-card:visible').count(), 4);
            await page.evaluate(() => cards.hideOffline(false));
            assert.equal(await second.isVisible(), true);
            await page.getByRole('button', {name: 'Person 2 options', exact: true}).click();
            await page.getByRole('menuitem', {name: 'Show video', exact: true}).click();
            assert.equal(await second.locator('.stream-call-poster').isVisible(), true);
            await page.getByRole('button', {name: 'Person 2 options', exact: true}).click();
            await page.getByRole('menuitem', {name: 'Kick', exact: true}).click();
            assert.deepEqual(await page.evaluate(() => kicked), [], 'Kick requires confirmation');
            await page.keyboard.press('Escape');
            await page.getByRole('button', {name: 'Person 2 options', exact: true}).click();
            await page.getByRole('menuitem', {name: 'Kick', exact: true}).click();
            await page.getByRole('menuitem', {name: 'Confirm kick', exact: true}).click();
            assert.deepEqual(await page.evaluate(() => kicked), ['2']);
            const refreshDuringExpansion = await page.getByRole('button', {name: 'Expand Person 2', exact: true}).evaluate(button => {
                button.click();
                const card = button.closest('.stream-call-card');
                const animation = card.getAnimations()[0];
                model[1].thumbnail_url += '?refresh=1';
                cards.update(model);
                return {
                    animating: Boolean(animation && card.getAnimations().includes(animation)),
                    thumbnail: card.querySelector('.stream-call-poster').src,
                    label: button.getAttribute('aria-label')
                };
            });
            assert.deepEqual(refreshDuringExpansion, {
                animating: true, thumbnail: 'https://images.test/stream.svg?refresh=1', label: 'Return to split view'
            }, 'Refreshing a thumbnail keeps the current expansion and updates the image');
            await page.waitForFunction(() => created.length === 1);
            await page.getByRole('button', {name: 'Person 2 options', exact: true}).click();
            await page.getByRole('menuitem', {name: 'Hide video', exact: true}).click();
            assert.deepEqual(await page.evaluate(() => destroyed), ['person2'], 'Hiding an expanded video stops its player');
            await page.getByRole('button', {name: 'Person 2 options', exact: true}).click();
            await page.getByRole('menuitem', {name: 'Show video', exact: true}).click();
            await page.waitForFunction(() => created.length === 2);
            const stacked = await page.locator('.stream-call-grid').evaluate(grid => {
                const selected = grid.querySelector('.is-selected').getBoundingClientRect();
                const rest = [...grid.querySelectorAll('.stream-call-card:not(.is-selected)')].map(card => card.getBoundingClientRect());
                return rest.every((rect, i) => rect.top > selected.bottom && (!i || (rect.left > rest[i - 1].left && Math.abs(rect.top - rest[i - 1].top) < 1)));
            });
            assert.equal(stacked, true, 'Other participants sit in one row below the expanded preview');
            await assertVideoRatios();
            assert.equal(await page.evaluate(() => selection), '2');
            await page.getByRole('button', {name: 'Expand Person 3', exact: true}).click();
            await page.waitForFunction(() => created.at(-1) === 'person3');
            const starts = await page.evaluate(() => created.length);
            await page.evaluate(() => cards.update(model.map(guest => ({...guest}))));
            assert.equal(await page.evaluate(() => created.length), starts, 'Refreshing participants does not reload the selected player');
            await page.evaluate(() => cards.hideOffline(true));
            assert.equal(await page.locator('.stream-call-card:visible').count(), 5);
            await page.screenshot({path: '.data/stream-call-focused.png'});
            await page.getByRole('button', {name: 'Return to split view', exact: true}).click();
            assert.equal(await page.locator('.stream-call-grid').evaluate(grid => grid.classList.contains('is-focused')), false);
            assert.equal(await page.locator('.stream-call-card:visible').count(), 5, 'Returning to the grid preserves the filter');
            await page.getByRole('button', {name: 'Expand Person 3', exact: true}).click();
            await page.getByRole('button', {name: 'Return to split view', exact: true}).click();
            assert.equal(await page.locator('.stream-call-grid').evaluate(grid => grid.classList.contains('is-focused')), false);
            await page.evaluate(() => cards.hideOffline(false));
            assert.equal(await page.locator('.stream-call-card:visible').count(), 6);
            await page.evaluate(() => cards.update([...model].reverse()));
            assert.equal(await page.locator('.stream-call-card').last().getAttribute('data-user-id'), '6', 'The offline card follows live previews regardless of input order');
            const source = await page.locator('.stream-call-card[data-user-id="6"]').boundingBox();
            const target = await page.locator('.stream-call-card').first().boundingBox();
            await page.mouse.move(source.x + source.width / 2, source.y + source.height / 2);
            await page.mouse.down();
            await page.mouse.move(target.x + target.width / 2, target.y + target.height / 2, {steps: 5});
            const ghost = page.locator('.participant-drag-ghost');
            const placeholder = page.locator('.participant-drop-placeholder');
            assert.equal(await ghost.count(), 1);
            assert.ok(Math.abs(await ghost.evaluate(card => parseFloat(card.style.left)) - target.x) < 1);
            assert.ok(Math.abs(await placeholder.evaluate(slot => parseFloat(slot.style.top)) - target.y) < 1);
            assert.match(await page.locator('.stream-call-card').first().evaluate(card =>
                card.style.getPropertyValue('--participant-drag-shift')), /[1-9]/);
            await page.mouse.up();
            assert.equal(await placeholder.count(), 0);
            await ghost.waitFor({state: 'detached'});
            await page.evaluate(() => cards.update(model));
            assert.equal(await page.locator('.stream-call-card').first().getAttribute('data-user-id'), '6', 'Manual order survives a participant refresh');
            await page.setViewportSize({width: 390, height: 844});
            assert.equal(await page.getByRole('button', {name: 'Expand Person 4', exact: true}).evaluate(button => {
                button.click();
                return document.querySelector('[data-stream-cards]').getAnimations({subtree: true}).length > 0;
            }), true, 'Expanding animates the cards into their new positions');
            await assertVideoRatios();
            await page.setViewportSize({width: 900, height: 500});
            await assertVideoRatios();
            await page.setViewportSize({width: 390, height: 844});
            await assertVideoRatios();
            await page.screenshot({path: '.data/stream-call-focused-mobile.png'});
            assert.ok((await page.locator('.stream-together-dialog').boundingBox()).width <= 390);
            assert.equal(await page.getByRole('button', {name: 'Return to split view', exact: true}).evaluate(button => {
                button.click();
                return document.querySelector('[data-stream-cards]').getAnimations({subtree: true}).length > 0;
            }), true, 'Returning to multiview animates in the opposite direction');
            await page.emulateMedia({reducedMotion: 'reduce'});
            assert.equal(await page.getByRole('button', {name: 'Expand Person 4', exact: true}).evaluate(button => {
                button.click();
                return document.querySelector('[data-stream-cards]').getAnimations({subtree: true}).length;
            }), 0, 'Reduced motion skips transitions and cancels an unfinished switch');
            await page.evaluate(() => cards.destroy());
            assert.equal(await page.locator('.stream-call-card').count(), 0);
            assert.deepEqual(errors, []);
        } finally { await browser.close(); }
    });
