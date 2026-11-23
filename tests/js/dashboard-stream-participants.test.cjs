const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('participant icons stay right of the video, pin your channel first and switch one existing player',
    {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
        const browser = await chromium.launch({executablePath, headless: true});
        try {
            for (const width of [1200, 390]) {
                const page = await browser.newPage({viewport: {width, height: 844}, reducedMotion: 'reduce'});
                const errors = []; page.on('pageerror', error => errors.push(error.message));
                const entries = ['friend', 'other', 'owner'].map((login, index) => ({id: String(index + 1), login, display_name: login,
                    profile_image_url: `https://images.test/${login}.svg`, is_streaming: login !== 'friend'}));
                let roster = entries, fail = false, reads = 0;
                await page.route('http://dashboard.test/**', async route => {
                    if (route.request().url().includes('/api/stream-together/participants')) {
                        reads++;
                        return route.fulfill(fail ? {status: 502, json: {detail: 'Unavailable'}} : {json: {participants: roster}});
                    }
                    return route.fulfill({contentType: 'text/html; charset=utf-8', body: `<body class="dashboard-page channel-page channel-page-overview" data-channel-root="/channel">
                        <section class="panel dashboard-video-card" style="width:min(640px,100%);height:420px;margin:16px auto">
                            <div class="dashboard-video-header" style="margin-bottom:12px">
                                <h3>Stream preview</h3><button type="button" class="twitch-current-category-art" aria-label="Select category"><img data-current-category-art alt="" src="https://images.test/category.svg"></button>
                            </div>
                                <nav class="dashboard-stream-participants" data-stream-participants data-channel-id="3" aria-label="Stream Together previews" hidden><button class="dashboard-stream-session" aria-label="Stream Together"><svg viewBox="0 0 24 24"><circle cx="9" cy="7" r="3"/></svg></button><div class="dashboard-stream-participant-icons" data-stream-participant-icons></div><button class="dashboard-stream-hangup" aria-label="Hang up">Hang up</button></nav>
                            <div class="dashboard-video-frame"><div id="player" class="dashboard-video-player" data-stream-player data-channel="owner" data-is-live="true"></div>
                            </div><p data-stream-playback-status hidden></p>
                        </section></body>`});
                });
                await page.route('https://images.test/**', route => route.fulfill({contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36"><rect width="36" height="36" rx="18" fill="#8360c4"/></svg>'}));
                await page.goto('http://dashboard.test/');
                await page.evaluate(() => {
                    window.commands = []; window.creations = 0;
                    class Player {
                        constructor() { creations++; this.events = {}; window.player = this; }
                        addEventListener(type, listener) { this.events[type] = listener; }
                        setChannel(login) { commands.push(login); }
                        pause() {}
                    }
                    for (const type of ['READY', 'ONLINE', 'OFFLINE', 'PLAY', 'PLAYING', 'PAUSE', 'PLAYBACK_BLOCKED']) Player[type] = type;
                    window.Twitch = {Player};
                    window.EventSource = class { constructor() { throw Error('No extra chat connection'); } };
                });
                for (const css of ['style', 'dashboard-stream-together']) await page.addStyleTag({path: `web/static/css/${css}.css`});
                const art = page.locator('.twitch-current-category-art');
                const originalArtPosition = await art.boundingBox();
                for (const js of ['dashboard-stream-player', 'dashboard-participant-order', 'dashboard-stream-participants']) await page.addScriptTag({path: `web/static/js/${js}.js`});
                await page.getByRole('button', {name: 'owner', exact: true}).waitFor();
                assert.equal(await page.locator('[data-stream-participant-icons] > button').first().getAttribute('data-channel'), 'owner');
                assert.deepEqual(await page.locator('[data-stream-participant-icons] > button').evaluateAll(buttons => buttons.map(button => button.dataset.channel)), ['owner', 'other', 'friend']);
                await page.evaluate(() => player.events.READY());
                const offline = page.locator('[data-stream-participant-icons] [data-channel="friend"]');
                assert.equal(await offline.isDisabled(), true);
                assert.equal(await offline.getAttribute('title'), 'friend');
                await offline.hover();
                assert.equal(await offline.locator('img').evaluate(img => getComputedStyle(img).transform), 'none');
                await offline.evaluate(button => button.click());
                assert.deepEqual(await page.evaluate(() => commands), []);
                const live = page.getByRole('button', {name: 'other', exact: true});
                assert.equal(await live.evaluate(button => getComputedStyle(button).borderTopColor), 'rgb(239, 68, 68)');
                await live.click();
                assert.deepEqual(await page.evaluate(() => commands), ['other']);
                assert.equal(await live.getAttribute('aria-pressed'), 'true');
                assert.equal(await live.evaluate(button => getComputedStyle(button).borderTopColor), 'rgb(255, 255, 255)');
                await offline.dragTo(live);
                assert.deepEqual(await page.locator('[data-stream-participant-icons] > button').evaluateAll(buttons => buttons.map(button => button.dataset.channel)), ['owner', 'friend', 'other']);
                await page.mouse.move(0, 0);
                const icon = page.getByRole('button', {name: 'owner', exact: true}).locator('img');
                const originalWidth = (await icon.boundingBox()).width;
                await icon.hover();
                assert.ok((await icon.boundingBox()).width > (await icon.locator('..').boundingBox()).width, 'Hovered icons overlap the ring');
                assert.equal(await icon.locator('..').getAttribute('title'), 'owner');
                assert.equal(await icon.locator('..').getAttribute('aria-label'), 'owner');
                await page.evaluate(() => window.dispatchEvent(new CustomEvent('dashboard-stream-live-changed', {detail: {isLive: false}})));
                const layout = await page.locator('[data-stream-participants]').evaluate(rail => {
                    const r = rail.getBoundingClientRect(), frame = rail.parentElement.getBoundingClientRect();
                    const video = document.querySelector('[data-stream-player]').getBoundingClientRect();
                    const buttons = [...rail.querySelector('[data-stream-participant-icons]').children].map(button => button.getBoundingClientRect());
                    return {right: r.right <= frame.right + 1 && r.left >= video.right,
                        vertical: buttons[0].bottom < buttons[1].top && buttons[1].bottom < buttons[2].top,
                        ratio: video.width / video.height, background: getComputedStyle(rail).backgroundColor,
                        top: buttons[0].top - r.top};
                });
                assert.equal(layout.right, true); assert.equal(layout.vertical, true);
                assert.ok(Math.abs(layout.ratio - 16 / 9) < .02, 'Video stays 16:9');
                assert.notEqual(layout.background, 'rgba(0, 0, 0, 0)');
                assert.ok(layout.top >= 44 && layout.top <= 52, 'Bubbles begin just below the Stream Together icon');
                const hangup = await page.getByRole('button', {name: 'Hang up', exact: true}).boundingBox();
                const strip = await page.locator('[data-stream-participants]').boundingBox();
                assert.equal((await art.boundingBox()).x, originalArtPosition.x,
                    'Showing the participant strip leaves the category art in its original position');
                assert.ok(Math.abs(hangup.y + hangup.height - strip.y - strip.height + 6) < 1, 'Hang up is inset from the bottom of the strip');
                assert.equal(hangup.width, hangup.height, 'Hang up stays square');
                assert.equal(hangup.width, 44);
                assert.ok(Math.abs(hangup.x + hangup.width - strip.x - strip.width + 6) < 1, 'Hang up is inset from the right of the strip');
                const panel = await page.locator('.dashboard-video-card').boundingBox();
                assert.ok(Math.abs(strip.x + strip.width - panel.x - panel.width) <= 1, 'The strip begins at the panel edge without its padding gap');
                const header = await page.locator('.dashboard-video-header').boundingBox();
                assert.ok(Math.abs(strip.y - header.y - header.height - 8) <= 1, 'The strip starts eight pixels below the title and category row');
                await page.locator('.dashboard-video-header').evaluate(header => { header.style.paddingBottom = '28px'; });
                await page.waitForFunction(() => Math.abs(document.querySelector('[data-stream-participants]').getBoundingClientRect().top - document.querySelector('.dashboard-video-header').getBoundingClientRect().bottom - 8) <= 1);
                await page.locator('.dashboard-video-card').evaluate(panel => { panel.style.height = '245px'; });
                await page.waitForFunction(() => {
                    const strip = document.querySelector('[data-stream-participant-icons]');
                    const bubbles = [...strip.children].map(button => button.getBoundingClientRect());
                    return bubbles.length === 3 && bubbles.every(bubble => bubble.width > 0 && bubble.width < 42 && Math.abs(bubble.width - bubble.height) < 1)
                        && bubbles.at(-1).bottom <= strip.getBoundingClientRect().bottom + 1;
                }, null, {timeout: 5000});
                await page.locator('.dashboard-video-card').evaluate(panel => { panel.style.height = '420px'; });
                await page.waitForFunction(() => document.querySelector('[data-stream-participant-icons] button').getBoundingClientRect().width === 42);
                entries[0].display_name = 'Different name';
                const updated = page.waitForResponse(response => response.url().includes('/api/stream-together/participants'));
                await page.evaluate(() => window.dispatchEvent(new CustomEvent('dashboard-stream-participants-changed')));
                await updated;
                await page.waitForFunction(() => document.querySelector('[data-channel="friend"]').getAttribute('aria-label') === 'Different name\n(friend)');
                assert.equal(await page.locator('[data-channel="friend"]').getAttribute('aria-label'), 'Different name\n(friend)');
                await page.addScriptTag({path: 'web/static/js/hover-labels.js'});
                await offline.hover();
                const tooltip = page.locator('.dashboard-hover-tooltip');
                await tooltip.waitFor({state: 'visible', timeout: 3000});
                assert.match(await tooltip.innerText(), /Different name/);
                await page.mouse.move(0, 0);
                await page.screenshot({path: `.data/stream-participant-rail-${width}.png`});
                fail = true; const previousReads = reads;
                const failure = page.waitForResponse(response => response.url().includes('/api/stream-together/participants') && response.status() === 502);
                await page.evaluate(() => window.dispatchEvent(new CustomEvent('dashboard-stream-participants-changed')));
                await failure;
                await page.evaluate(() => new Promise(requestAnimationFrame));
                assert.ok(reads > previousReads); assert.equal(await page.locator('[data-stream-participants] [data-channel]').count(), 3);
                fail = false; roster = [entries[2]];
                await page.evaluate(() => window.dispatchEvent(new CustomEvent('dashboard-stream-participants-changed')));
                await page.waitForFunction(() => document.querySelectorAll('[data-stream-participants] [data-channel]').length === 1);
                assert.equal(await page.locator('[data-stream-participants]').isVisible(), true, 'Your bubble stays visible in a solo shared session');
                assert.deepEqual(await page.evaluate(() => commands), ['other', 'owner']);
                roster = [];
                await page.evaluate(() => window.dispatchEvent(new CustomEvent('dashboard-stream-participants-changed')));
                await page.waitForFunction(() => document.querySelector('[data-stream-participants]').hidden);
                assert.deepEqual(await page.evaluate(() => commands), ['other', 'owner']);
                assert.equal(await page.evaluate(() => creations), 1);
                assert.deepEqual(errors, []); await page.close();
            }
        } finally { await browser.close(); }
    });
