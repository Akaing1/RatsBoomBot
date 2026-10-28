const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();
const skip = !chromium || !fs.existsSync(executablePath || '');
const script = fs.readFileSync('web/static/js/dashboard-engagement.js', 'utf8');
const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
const markup = '<dialog id="dashboard-engagement"' + template.split('<dialog id="dashboard-engagement"')[1].split('</dialog>')[0] + '</dialog>';
async function setup(browser, width = 1100, storage, route = '/', archivedStorage) {
    const page = await browser.newPage({viewport: {width, height: 850}});
    await page.route('https://test.local/**', route => route.fulfill({contentType: 'text/html', body: '<html></html>'}));
    await page.goto(`https://test.local${route}`);
    await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}\n${fs.readFileSync('web/static/css/dashboard-engagement.css', 'utf8')}</style><button data-engagement-open="predictions">Predictions</button><button data-engagement-open="polls">Polls</button>${markup}`);
    if (archivedStorage) await page.evaluate(value => localStorage.setItem('dashboard-engagement-archived:1:v1', value), archivedStorage);
    await page.evaluate(storage => {
        if (storage) localStorage.setItem('dashboard-engagement:1:v1', storage);
        document.querySelector('[data-engagement]').dataset.channelId = '1';
        window.calls = [];
        window.fetch = async (url, options = {}) => {
            window.calls.push({url, method: options.method || 'GET', body: options.body?.toString()});
            if (options.method === 'POST') return {ok: true, json: async () => ({item: {id: 'created'}})};
            return {ok: true, json: async () => ({items: [{id: 'old', title: 'Will we win?', choices: ['Yes', 'No'], duration: 120}]})};
        };
    }, storage);
    await page.addScriptTag({content: script});
    return page;
}

test('poll and prediction hash links open the matching view and follow navigation', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser, 1100, undefined, '/?test=1#polls');
        const dialog = page.locator('[data-engagement]');
        await assert.doesNotReject(() => dialog.waitFor({state: 'visible'}));
        assert.equal(await page.locator('[data-engagement-tab="polls"]').getAttribute('aria-selected'), 'true');
        await page.locator('[name="title"]').fill('Keep this draft');
        await page.locator('[data-engagement-tab="predictions"]').click();
        assert.equal(new URL(page.url()).hash, '#predictions');
        assert.equal(await page.locator('[name="title"]').inputValue(), 'Keep this draft');
        await page.locator('[data-engagement-close]').click();
        await page.waitForFunction(() => !location.hash);
        assert.equal(new URL(page.url()).search, '?test=1');
        await page.locator('[data-engagement-open="polls"]').click();
        assert.equal(new URL(page.url()).hash, '#polls');
        await page.goBack();
        await dialog.waitFor({state: 'hidden'});
        await page.goForward();
        await dialog.waitFor({state: 'visible'});
        await page.evaluate(() => { location.hash = '#predictions'; });
        await page.waitForFunction(() => document.querySelector('[data-engagement-tab="predictions"]').getAttribute('aria-selected') === 'true');
        await page.evaluate(() => { location.hash = '#raidbrowser'; });
        await dialog.waitFor({state: 'hidden'});
        assert.equal(new URL(page.url()).hash, '#raidbrowser');
    } finally { await browser.close(); }
});

test('prediction deep link opens on initial load', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser, 1100, undefined, '/#predictions');
        assert.equal(await page.locator('[data-engagement]').evaluate(dialog => dialog.open), true);
        assert.equal(await page.locator('[data-engagement-tab="predictions"]').getAttribute('aria-selected'), 'true');
        assert.equal((await page.evaluate(() => calls)).length, 1);
    } finally { await browser.close(); }
});

test('poll additional votes default off and omit the cost when posted', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-engagement-open="polls"]');
        assert.equal(await page.locator('[data-engagement-additional-votes]').isChecked(), false);
        assert.equal(await page.locator('[data-engagement-vote-cost]').isVisible(), false);
        assert.equal(await page.locator('[name="channel_points_per_vote"]').isDisabled(), true);
        await page.fill('[name="title"]', 'Question');
        await page.locator('[data-engagement-choices] input').nth(0).fill('A');
        await page.locator('[data-engagement-choices] input').nth(1).fill('B');
        await page.click('[data-engagement-start]');
        await page.waitForFunction(() => window.calls.some(call => call.method === 'POST'));
        const body = new URLSearchParams(await page.evaluate(() => window.calls.find(call => call.method === 'POST').body));
        assert.equal(body.get('channel_points_voting_enabled'), 'false');
        assert.equal(body.has('channel_points_per_vote'), false);
    } finally { await browser.close(); }
});

test('additional vote settings validate, save and restore, but never leak into predictions', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-engagement-open="polls"]');
        await page.fill('[name="title"]', 'Question');
        await page.locator('[data-engagement-choices] input').nth(0).fill('A');
        await page.locator('[data-engagement-choices] input').nth(1).fill('B');
        const toggle = page.locator('[data-engagement-additional-votes]'), cost = page.locator('[name="channel_points_per_vote"]');
        await toggle.check();
        assert.equal(await cost.isVisible(), true);
        await cost.fill('0'); await page.click('[data-engagement-save]');
        assert.match(await page.textContent('[data-engagement-status]'), /1–1,000,000 Channel Points/);
        assert.equal(await page.locator('[data-engagement-saved] .engagement-library-row').count(), 0);
        await cost.fill('250'); await page.click('[data-engagement-save]');
        await toggle.uncheck();
        await page.locator('[data-engagement-saved] .engagement-load').click();
        assert.equal(await toggle.isChecked(), true);
        assert.equal(await cost.inputValue(), '250');
        await page.click('[data-engagement-tab="predictions"]');
        assert.equal(await page.locator('[data-engagement-poll-options]').isVisible(), false);
        assert.equal(await cost.isDisabled(), true);
        await page.click('[data-engagement-start]');
        await page.waitForFunction(() => document.querySelector('[data-engagement-status]').textContent === 'Prediction started.');
        const prediction = new URLSearchParams(await page.evaluate(() => window.calls.find(call => call.method === 'POST').body));
        assert.equal(prediction.has('channel_points_voting_enabled'), false);
        assert.equal(prediction.has('channel_points_per_vote'), false);
        await page.click('[data-engagement-tab="polls"]');
        assert.equal(await toggle.isChecked(), true);
        await page.click('[data-engagement-start]');
        await page.waitForFunction(() => document.querySelector('[data-engagement-status]').textContent === 'Poll started.');
        const poll = new URLSearchParams(await page.evaluate(() => window.calls.find(call => call.method === 'POST' && call.url.endsWith('/polls')).body));
        assert.equal(poll.get('channel_points_voting_enabled'), 'true');
        assert.equal(poll.get('channel_points_per_vote'), '250');
    } finally { await browser.close(); }
});

test('saved and recent entries highlight exact draft matches and fade when edited', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const item = {kind: 'polls', title: 'Will we win?', choices: ['Yes', 'No'], duration: 120,
            channel_points_voting_enabled: true, channel_points_per_vote: 100};
        const page = await setup(browser, 1100, JSON.stringify([item]));
        await page.click('[data-engagement-open="polls"]');
        const saved = page.locator('[data-engagement-saved] .engagement-library-row');
        const recent = page.locator('[data-engagement-recent] .engagement-library-row');
        await recent.waitFor();
        await saved.locator('.engagement-load').click();
        assert.equal(await saved.locator('.engagement-load').getAttribute('aria-pressed'), 'true');
        assert.equal(await recent.locator('.engagement-load').getAttribute('aria-pressed'), 'false', 'Additional-vote settings are part of the match');
        await page.uncheck('[data-engagement-additional-votes]');
        assert.equal(await saved.locator('.engagement-load').getAttribute('aria-pressed'), 'false');
        assert.equal(await recent.locator('.engagement-load').getAttribute('aria-pressed'), 'true', 'Matching by editing also highlights');
        await page.locator('[data-engagement-choices] input').first().fill('Maybe');
        assert.equal(await recent.locator('.engagement-load').getAttribute('aria-pressed'), 'false');
        await page.locator('[data-engagement-choices] input').first().fill('Yes');
        assert.equal(await recent.locator('.engagement-load').getAttribute('aria-pressed'), 'true');
        await page.fill('[name="duration"]', '90s');
        assert.equal(await recent.locator('.engagement-load').getAttribute('aria-pressed'), 'false');
        await page.fill('[name="duration"]', '2m');
        assert.equal(await recent.locator('.engagement-load').getAttribute('aria-pressed'), 'true');
        await page.fill('[name="title"]', 'Different');
        assert.equal(await recent.locator('.engagement-load').getAttribute('aria-pressed'), 'false');
        const transition = await recent.evaluate(node => getComputedStyle(node).transitionDuration);
        assert.ok(transition.includes('0.3s'), 'Unhighlighting has a fade transition');
    } finally { await browser.close(); }
});

test('duration slider and inline field sync, pointer dragging snaps, and exact input stays precise', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-engagement-open="predictions"]');
        const slider = page.locator('[data-engagement-duration-slider]'), field = page.locator('[name="duration"]');
        assert.equal(await slider.getAttribute('aria-valuenow'), '120');
        assert.equal(await field.inputValue(), '2m0s');
        const marks = await page.locator('#engagement-duration-marks option').evaluateAll(options => options.map(option => ({position: Number(option.value), seconds: Number(option.dataset.seconds)})));
        assert.deepEqual(marks.map(mark => mark.position), marks.map((_, index) => index), 'Notches are evenly spaced visually');
        assert.deepEqual(marks.map(mark => mark.seconds), [30, 60, 120, 300, 600, 1200, 1800]);
        const moveSlider = seconds => slider.evaluate((node, seconds) => {
            const points = [...document.querySelectorAll('#engagement-duration-marks option')].map(option => Number(option.dataset.seconds));
            const upper = points.findIndex(point => point >= seconds);
            node.value = String(upper === 0 ? 0 : upper - 1 + (seconds - points[upper - 1]) / (points[upper] - points[upper - 1]));
            node.dispatchEvent(new Event('input', {bubbles: true}));
        }, seconds);
        await field.fill('137');
        assert.equal(await slider.getAttribute('aria-valuenow'), '137');
        await slider.dispatchEvent('pointerdown', {pointerType: 'mouse'});
        await moveSlider(307);
        assert.equal(await field.inputValue(), '5m0s');
        assert.equal(await slider.getAttribute('aria-valuenow'), '300');
        assert.equal(await slider.getAttribute('aria-valuetext'), '5 minutes');
        await moveSlider(400);
        assert.equal(await field.inputValue(), '6m30s');
        for (const [raw, expected, display] of [[47, 45, '0m45s'], [62, 60, '1m0s'], [77, 80, '1m20s'], [137, 150, '2m30s'], [293, 300, '5m0s'], [337, 330, '5m30s'], [907, 900, '15m0s'], [947, 960, '16m0s'], [1247, 1260, '21m0s'], [1798, 1800, '30m0s']]) {
            await moveSlider(raw);
            assert.equal(await slider.getAttribute('aria-valuenow'), String(expected));
            assert.equal(await field.inputValue(), display);
        }
        await page.dispatchEvent('body', 'pointerup');
        await field.fill('301');
        assert.equal(await slider.getAttribute('aria-valuenow'), '301', 'Typed values must not snap');
        await slider.focus(); await page.keyboard.press('ArrowRight');
        assert.equal(await field.inputValue(), '5m30s', 'Keyboard steps match the duration range');
        await page.keyboard.press('ArrowLeft');
        assert.equal(await field.inputValue(), '5m0s');
        await page.keyboard.press('ArrowLeft');
        assert.equal(await field.inputValue(), '4m30s');
        await field.fill('1m'); await slider.focus(); await page.keyboard.press('ArrowLeft');
        assert.equal(await field.inputValue(), '0m55s', 'Moving below one minute returns to five-second steps');
        await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowRight');
        assert.equal(await field.inputValue(), '1m10s');
        await field.fill('2m'); await slider.focus(); await page.keyboard.press('ArrowLeft');
        assert.equal(await field.inputValue(), '1m50s');
        await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowRight');
        assert.equal(await field.inputValue(), '2m30s');
        await field.fill('10m'); await slider.focus(); await page.keyboard.press('ArrowLeft');
        assert.equal(await field.inputValue(), '9m30s');
        await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowRight');
        assert.equal(await field.inputValue(), '11m0s');
        await field.fill('20m'); await slider.focus(); await page.keyboard.press('ArrowLeft');
        assert.equal(await field.inputValue(), '19m0s');
        await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowRight');
        assert.equal(await field.inputValue(), '21m0s');
        const aligned = await page.evaluate(() => {
            const slider = document.querySelector('[data-engagement-duration-slider]').getBoundingClientRect();
            const field = document.querySelector('[name="duration"]').getBoundingClientRect();
            return {centers: Math.abs(slider.y + slider.height / 2 - field.y - field.height / 2), gap: field.left - slider.right};
        });
        assert.ok(aligned.centers < 1 && aligned.gap > 0, JSON.stringify(aligned));
        await page.click('[data-engagement-tab="polls"]');
        assert.equal(await slider.getAttribute('aria-valuemin'), '15');
        await field.fill('15');
        assert.equal(await slider.getAttribute('aria-valuenow'), '15');
        await page.click('[data-engagement-tab="predictions"]');
        assert.equal(await slider.getAttribute('aria-valuemin'), '30');
        assert.equal(await field.evaluate(node => node.validity.customError), true);
        await field.fill('137');
        await page.fill('[name="title"]', 'Question');
        await page.locator('[data-engagement-choices] input').nth(0).fill('A');
        await page.locator('[data-engagement-choices] input').nth(1).fill('B');
        await page.click('[data-engagement-save]');
        await field.fill('600');
        await page.locator('[data-engagement-saved] .engagement-load').click();
        assert.equal(await field.inputValue(), '2m17s');
        assert.equal(await slider.getAttribute('aria-valuenow'), '137');
        await page.click('[data-engagement-start]');
        await page.waitForFunction(() => window.calls.some(call => call.method === 'POST'));
        const body = await page.evaluate(() => window.calls.find(call => call.method === 'POST').body);
        assert.equal(new URLSearchParams(body).get('duration'), '137');
    } finally { await browser.close(); }
});

test('duration notches have readable labels on desktop and mobile', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-engagement-open="polls"]');
        for (const width of [1100, 375]) {
            await page.setViewportSize({width, height: 850});
            await page.waitForTimeout(100);
            const labels = await page.locator('[data-engagement-duration-labels] span').evaluateAll(nodes => nodes.map(node => {
                const rect = node.getBoundingClientRect();
                return {text: node.textContent, x: rect.x, right: rect.right, y: rect.y, bottom: rect.bottom};
            }));
            assert.deepEqual(labels.map(label => label.text), ['15s', '30s', '1m', '2m', '5m', '10m', '20m', '30m']);
            const track = await page.locator('[data-engagement-duration-labels]').boundingBox();
            for (const [index, label] of labels.entries()) {
                const expected = track.x + index / (labels.length - 1) * track.width;
                assert.ok(Math.abs((label.x + label.right) / 2 - expected) < 1, `Label centered on notch: ${label.text}`);
            }
            for (let index = 0; index < labels.length; index++) {
                const label = labels[index];
                assert.ok(label.x >= 0 && label.right <= width, `Label fits at ${width}: ${label.text}`);
                for (const other of labels.slice(index + 1)) {
                    assert.ok(label.right <= other.x || other.right <= label.x || label.bottom <= other.y || other.bottom <= label.y, `Labels do not overlap at ${width}: ${label.text}, ${other.text}`);
                }
            }
        }
    } finally { await browser.close(); }
});

test('duration accepts minutes, seconds and combined units and normalizes on blur', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-engagement-open="predictions"]');
        const field = page.locator('[name="duration"]'), slider = page.locator('[data-engagement-duration-slider]');
        for (const [text, seconds, display] of [['2m15s', 135, '2m15s'], ['3m', 180, '3m0s'], ['90s', 90, '1m30s'],
            ['2 minutes 15 seconds', 135, '2m15s'], ['1.5m', 90, '1m30s'], ['137', 137, '2m17s'], ['30m', 1800, '30m0s']]) {
            await field.fill(text);
            assert.equal(await slider.getAttribute('aria-valuenow'), String(seconds));
            assert.equal(await field.evaluate(node => node.validity.valid), true);
            await page.click('[name="title"]');
            assert.equal(await field.inputValue(), display);
        }
        for (const text of ['31m', '14s', '2mfoo', '1.2s', '-30', '']) {
            await field.fill(text);
            assert.equal(await field.evaluate(node => node.validity.valid), false, `Reject ${text}`);
        }
    } finally { await browser.close(); }
});

test('disabled Add choice explains the five-poll and ten-prediction choice limits', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-engagement-open="polls"]');
        const add = page.locator('[data-engagement-add]'), wrapper = page.locator('[data-engagement-add-control]');
        assert.equal(await wrapper.getAttribute('title'), '');
        for (let i = 0; i < 3; i++) await add.click();
        assert.equal(await add.isDisabled(), true);
        await wrapper.hover();
        assert.equal(await wrapper.getAttribute('title'), 'The maximum number of choices you can add to a poll is 5.');
        await page.click('[data-engagement-tab="predictions"]');
        assert.equal(await add.isDisabled(), false);
        assert.equal(await wrapper.getAttribute('title'), '');
        for (let i = 0; i < 5; i++) await add.click();
        assert.equal(await add.isDisabled(), true);
        await wrapper.hover();
        assert.equal(await wrapper.getAttribute('title'), 'The maximum number of choices you can add to a prediction is 10.');
        assert.equal(await page.locator('[data-engagement-choices] input').count(), 10);
        await page.locator('.engagement-remove').last().click();
        assert.equal(await add.isDisabled(), false);
        assert.equal(await wrapper.getAttribute('title'), '');
    } finally { await browser.close(); }
});

test('round trips through Polls do not lock Add choice below the prediction limit', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-engagement-open="predictions"]');
        const add = page.locator('[data-engagement-add]');
        const inputs = page.locator('[data-engagement-choices] input');
        for (let i = 0; i < 3; i++) await add.click();
        assert.equal(await inputs.count(), 5);
        for (let i = 0; i < 3; i++) {
            await page.click('[data-engagement-tab="polls"]');
            assert.equal(await add.isDisabled(), true);
            await page.click('[data-engagement-tab="predictions"]');
            assert.equal(await add.isDisabled(), false);
        }
        await add.click();
        assert.equal(await inputs.count(), 6);
        await page.click('[data-engagement-tab="polls"]');
        await page.click('[data-engagement-tab="predictions"]');
        assert.equal(await add.isDisabled(), false, 'Six choices must still allow adding up to ten');
        assert.equal(await add.getAttribute('title'), '');
        assert.equal(await inputs.nth(5).isDisabled(), false);
        await page.locator('.engagement-remove').last().click();
        assert.equal(await add.isDisabled(), false);
        await add.click();
        assert.equal(await inputs.count(), 6);
        await page.click('[data-engagement-tab="polls"]');
        await page.locator('.engagement-remove').last().click();
        await page.click('[data-engagement-tab="predictions"]');
        assert.equal(await add.isDisabled(), false);
        await add.click();
        assert.equal(await inputs.count(), 6);
    } finally { await browser.close(); }
});

test('hovering either the saved/recent text or star highlights the entire row', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.emulateMedia({reducedMotion: 'reduce'});
        await page.click('[data-engagement-open="predictions"]');
        const row = page.locator('[data-engagement-recent] .engagement-library-row').first();
        const color = () => row.evaluate(node => getComputedStyle(node).backgroundColor);
        const normal = await color();
        const star = row.locator('.engagement-star');
        assert.equal(await star.locator('svg').evaluate(node => getComputedStyle(node).fill), 'none');
        await row.locator('.engagement-load').hover();
        const highlighted = await color();
        assert.notEqual(highlighted, normal);
        for (const selector of ['.engagement-load', '.engagement-star']) {
            assert.equal(await row.locator(selector).evaluate(node => getComputedStyle(node).backgroundColor), 'rgba(0, 0, 0, 0)');
        }
        await star.hover();
        assert.equal(await color(), highlighted);
        assert.notEqual(await star.locator('svg').evaluate(node => getComputedStyle(node).fill), 'none');
        await page.mouse.move(0, 0);
        assert.equal(await color(), normal);
        assert.equal(await star.locator('svg').evaluate(node => getComputedStyle(node).fill), 'none');
        await row.locator('.engagement-star').focus();
        assert.equal(await color(), highlighted);
    } finally { await browser.close(); }
});

test('saving slides a row in and deleting requires the revealed X before sliding it out', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.evaluate(() => {
            const animate = Element.prototype.animate;
            window.savedAnimations = [];
            Element.prototype.animate = function(frames, options) {
                if (this.matches('.engagement-library-row')) window.savedAnimations.push(frames);
                return animate.call(this, frames, options);
            };
        });
        await page.click('[data-engagement-open="predictions"]');
        await page.locator('[data-engagement-recent] .engagement-star').click();
        const row = page.locator('[data-engagement-saved] .engagement-library-row');
        assert.equal(await row.count(), 1);
        assert.equal(await page.evaluate(() => window.savedAnimations[0][0].transform), 'translateY(-14px)');
        await row.locator('.engagement-star').click();
        assert.equal(await row.locator('.engagement-delete').isVisible(), true);
        assert.equal(await row.locator('.engagement-delete').getAttribute('title'), 'Are you sure you want to delete it?');
        assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('dashboard-engagement:1:v1')).length), 1);
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('[data-engagement]').evaluate(node => node.open), true);
        assert.equal(await row.locator('.engagement-delete').isVisible(), false);
        await row.locator('.engagement-star').click();
        await row.locator('.engagement-delete').click();
        await page.waitForFunction(() => JSON.parse(localStorage.getItem('dashboard-engagement:1:v1')).length === 0);
        assert.equal(await row.count(), 0);
        const frames = await page.evaluate(() => window.savedAnimations.at(-1));
        assert.equal(frames[1].transform, 'translateY(-14px)');
        assert.equal(frames[1].height, '0px');
        assert.equal(await page.locator('[data-engagement-recent] .engagement-star').getAttribute('aria-pressed'), 'false');
    } finally { await browser.close(); }
});

test('recent stars also require confirmation and clicking away cancels deletion', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.emulateMedia({reducedMotion: 'reduce'});
        await page.click('[data-engagement-open="predictions"]');
        const recent = page.locator('[data-engagement-recent] .engagement-library-row');
        await recent.locator('.engagement-star').click();
        await recent.locator('.engagement-star').click();
        assert.equal(await recent.locator('.engagement-delete').isVisible(), true);
        await page.click('[name="title"]');
        assert.equal(await recent.locator('.engagement-delete').isVisible(), false);
        assert.equal(await page.locator('[data-engagement-saved] .engagement-library-row').count(), 1);
        await recent.locator('.engagement-star').click();
        await recent.locator('.engagement-delete').click();
        assert.equal(await page.locator('[data-engagement-saved] .engagement-library-row').count(), 0);
        assert.equal(await recent.locator('.engagement-star').getAttribute('aria-pressed'), 'false');
    } finally { await browser.close(); }
});

test('clicking anywhere except the confirmation X only cancels the prompt', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.emulateMedia({reducedMotion: 'reduce'});
        await page.click('[data-engagement-open="predictions"]');
        await page.locator('[data-engagement-recent] .engagement-star').click();
        await page.fill('[name="title"]', 'Keep this draft');
        const row = page.locator('[data-engagement-saved] .engagement-library-row');
        for (const target of ['[data-engagement-saved] .engagement-load', '[data-engagement-saved] .engagement-star', '[data-engagement-tab="polls"]', '[data-engagement-close]']) {
            await row.locator('.engagement-star').click();
            assert.equal(await row.locator('.engagement-delete').isVisible(), true);
            await page.click(target);
            assert.equal(await row.locator('.engagement-delete').isVisible(), false);
            assert.equal(await page.inputValue('[name="title"]'), 'Keep this draft');
            assert.equal(await page.locator('[data-engagement-tab="predictions"]').getAttribute('aria-selected'), 'true');
            assert.equal(await page.locator('[data-engagement]').evaluate(node => node.open), true);
            assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('dashboard-engagement:1:v1')).length), 1);
        }
        await row.locator('.engagement-star').click();
        await row.locator('.engagement-delete').click();
        assert.equal(await row.count(), 0);
    } finally { await browser.close(); }
});

test('X buttons highlight on hover while disabled choice buttons stay muted', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-engagement-open="predictions"]');
        const colors = locator => locator.evaluate(node => {
            const style = getComputedStyle(node);
            return [style.backgroundColor, style.borderColor, style.color];
        });
        const remove = page.locator('.engagement-remove').first();
        const disabled = await colors(remove);
        await remove.hover();
        assert.deepEqual(await colors(remove), disabled);
        await page.click('[data-engagement-add]');
        const enabled = await colors(remove);
        await remove.hover();
        assert.notDeepEqual(await colors(remove), enabled);
        const close = page.locator('[data-engagement-close]');
        const normal = await colors(close);
        await close.hover();
        assert.notDeepEqual(await colors(close), normal);
    } finally { await browser.close(); }
});

test('shared draft, sliding tabs, choices, saving and starring recent templates', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        assert.equal(await page.evaluate(() => window.calls.length), 0, 'History is lazy-loaded');
        await page.click('[data-engagement-open="predictions"]');
        await page.fill('[name="title"]', 'Will we win?');
        const inputs = page.locator('[data-engagement-choices] input');
        assert.equal(await inputs.count(), 2);
        await inputs.nth(0).fill('Yes'); await inputs.nth(1).fill('No');
        const firstPosition = await page.locator('.engagement-tabs').evaluate(node => node.style.getPropertyValue('--engagement-tab-x'));
        await page.click('[data-engagement-tab="polls"]');
        assert.equal(await page.inputValue('[name="title"]'), 'Will we win?');
        assert.equal(await inputs.nth(0).inputValue(), 'Yes');
        assert.notEqual(await page.locator('.engagement-tabs').evaluate(node => node.style.getPropertyValue('--engagement-tab-x')), firstPosition);
        await page.click('[data-engagement-save]');
        assert.equal(await page.locator('[data-engagement-saved] .engagement-load').count(), 1);
        assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('dashboard-engagement:1:v1'))[0].kind), 'polls');
        await page.click('[data-engagement-tab="predictions"]');
        await page.locator('[data-engagement-recent] .engagement-star').click();
        assert.equal(await page.locator('[data-engagement-recent] .engagement-star').getAttribute('aria-pressed'), 'true');
        await page.click('[data-engagement-add]');
        assert.equal(await inputs.count(), 3);
        await page.locator('.engagement-remove').last().click();
        assert.equal(await inputs.count(), 2);
        await page.click('[data-engagement-start]');
        await page.waitForFunction(() => document.querySelector('[data-engagement-status]').textContent === 'Prediction started.');
        const post = await page.evaluate(() => window.calls.find(call => call.method === 'POST'));
        assert.equal(post.url, '/channel/api/engagement/predictions');
        assert.deepEqual(JSON.parse(new URLSearchParams(post.body).get('choices')), ['Yes', 'No']);
    } finally { await browser.close(); }
});

test('poll toggle crosses out extras and posts only the first five before deleting extras on success', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-engagement-open="predictions"]');
        await page.fill('[name="title"]', 'Question');
        for (let i = 0; i < 4; i++) await page.click('[data-engagement-add]');
        const inputs = page.locator('[data-engagement-choices] input');
        for (let i = 0; i < 5; i++) await inputs.nth(i).fill(`Choice ${i}`);
        await page.click('[data-engagement-tab="polls"]');
        assert.equal(await inputs.count(), 6);
        assert.equal(await page.locator('.engagement-choice.is-excluded').count(), 1);
        assert.equal(await inputs.nth(5).isDisabled(), true);
        assert.equal(await page.locator('[data-engagement-excluded-mark]').isVisible(), true);
        assert.match(await page.textContent('[data-engagement-choice-warning]'), /Twitch only allows 5 choices.*deleted/);
        await page.focus('[data-engagement-tab="polls"]'); await page.keyboard.press('ArrowRight');
        assert.equal(await page.locator('[data-engagement-tab="predictions"]').getAttribute('aria-selected'), 'true');
        assert.equal(await inputs.count(), 6);
        assert.equal(await inputs.nth(5).isDisabled(), false);
        assert.equal(await page.locator('.engagement-choice.is-excluded').count(), 0);
        await page.click('[data-engagement-tab="polls"]');
        await page.click('[data-engagement-start]');
        await page.waitForFunction(() => document.querySelector('[data-engagement-status]').textContent === 'Poll started.');
        const post = await page.evaluate(() => window.calls.find(call => call.method === 'POST'));
        assert.equal(post.url, '/channel/api/engagement/polls');
        assert.deepEqual(JSON.parse(new URLSearchParams(post.body).get('choices')), ['Choice 0', 'Choice 1', 'Choice 2', 'Choice 3', 'Choice 4']);
        assert.equal(await inputs.count(), 5);
        assert.equal(await page.locator('[data-engagement-choice-warning]').isVisible(), false);
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('[data-engagement]').evaluate(node => node.open), false);
    } finally { await browser.close(); }
});

test('one large X spans all extra poll fields and follows removals and window resizing', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-engagement-open="predictions"]');
        for (let i = 0; i < 8; i++) await page.click('[data-engagement-add]');
        await page.click('[data-engagement-tab="polls"]');
        assert.equal(await page.locator('.engagement-excluded-mark').count(), 1);
        const matchesFields = () => page.waitForFunction(() => {
            const mark = document.querySelector('[data-engagement-excluded-mark]').getBoundingClientRect();
            const fields = [...document.querySelectorAll('.engagement-choice.is-excluded input')];
            const first = fields[0].getBoundingClientRect(), last = fields.at(-1).getBoundingClientRect();
            return Math.abs(mark.top - first.top) < 1 && Math.abs(mark.bottom - last.bottom) < 1 &&
                Math.abs(mark.left - first.left) < 1 && Math.abs(mark.right - first.right) < 1;
        });
        await matchesFields();
        for (const width of [800, 514, 375]) {
            await page.setViewportSize({width, height: 850});
            await matchesFields();
        }
        await page.locator('.engagement-remove').last().click();
        assert.equal(await page.locator('.engagement-choice.is-excluded').count(), 4);
        await matchesFields();
        await page.click('[data-engagement-tab="predictions"]');
        assert.equal(await page.locator('[data-engagement-excluded-mark]').isVisible(), false);
    } finally { await browser.close(); }
});

test('failed poll creation keeps excluded choices and restores them when switching back', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-engagement-open="predictions"]');
        await page.fill('[name="title"]', 'Question');
        for (let i = 0; i < 4; i++) await page.click('[data-engagement-add]');
        const inputs = page.locator('[data-engagement-choices] input');
        for (let i = 0; i < 6; i++) await inputs.nth(i).fill(`Choice ${i}`);
        await page.evaluate(() => {
            const original = window.fetch;
            window.fetch = (url, options) => options?.method === 'POST'
                ? Promise.resolve({ok: false, json: async () => ({detail: 'Twitch unavailable'})}) : original(url, options);
        });
        await page.click('[data-engagement-tab="polls"]');
        await page.click('[data-engagement-start]');
        await page.waitForFunction(() => document.querySelector('[data-engagement-status]').textContent === 'Twitch unavailable');
        assert.equal(await inputs.count(), 6);
        assert.equal(await inputs.nth(5).isDisabled(), true);
        await page.click('[data-engagement-tab="predictions"]');
        assert.equal(await inputs.nth(5).inputValue(), 'Choice 5');
        assert.equal(await inputs.nth(5).isDisabled(), false);
    } finally { await browser.close(); }
});

test('choices panel has equal outer spacing with dashboard overlay scrollbars', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-engagement-open="predictions"]');
        const layout = await page.evaluate(() => {
            document.documentElement.classList.add('has-overlay-scrollbars');
            const main = document.querySelector('.engagement-main').getBoundingClientRect();
            const editor = document.querySelector('.engagement-editor');
            const form = editor.querySelector('form').getBoundingClientRect();
            const sidebar = document.querySelector('.engagement-sidebar');
            const dialog = document.querySelector('[data-engagement]').getBoundingClientRect();
            const saved = sidebar.querySelector('section').getBoundingClientRect();
            return {left: form.left - main.left, right: main.right - form.right,
                outerLeft: form.left - dialog.left, outerRight: dialog.right - saved.right,
                outset: parseFloat(getComputedStyle(editor).getPropertyValue('--overlay-scrollbar-outset')),
                sidebarLeft: getComputedStyle(sidebar).paddingLeft, sidebarRight: getComputedStyle(sidebar).paddingRight,
                sidebarOutset: getComputedStyle(sidebar).getPropertyValue('--overlay-scrollbar-outset')};
        });
        assert.ok(Math.abs(layout.left - layout.right) < 1, JSON.stringify(layout));
        assert.equal(layout.outset, 12);
        assert.equal(layout.sidebarLeft, '20px');
        assert.equal(layout.sidebarRight, '0px');
        assert.ok(Math.abs(layout.outerLeft - layout.outerRight) < 1, 'Outer saved/recent gap should match the choices panel left edge');
        assert.equal(layout.sidebarOutset.trim(), '12px');
    } finally { await browser.close(); }
});

test('both column scrollbars sit outside their content and scroll independently', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.setViewportSize({width: 1100, height: 550});
        await page.click('[data-engagement-open="predictions"]');
        for (let i = 0; i < 4; i++) await page.click('[data-engagement-add]');
        const layout = await page.evaluate(() => {
            const editor = document.querySelector('.engagement-editor');
            const form = editor.querySelector('form');
            const sidebar = document.querySelector('.engagement-sidebar');
            const list = sidebar.querySelector('[data-engagement-recent]');
            const row = list.querySelector('.engagement-library-row');
            for (let i = 0; i < 30; i++) list.append(row.cloneNode(true));
            editor.scrollTop = 100; sidebar.scrollTop = 100;
            return {editorGap: editor.getBoundingClientRect().left + editor.clientLeft + editor.clientWidth - form.getBoundingClientRect().right,
                sidebarGap: sidebar.getBoundingClientRect().left + sidebar.clientLeft + sidebar.clientWidth - row.getBoundingClientRect().right,
                editorBackground: getComputedStyle(editor).backgroundColor,
                formBackground: getComputedStyle(form).backgroundColor,
                editorScroll: editor.scrollTop, sidebarScroll: sidebar.scrollTop};
        });
        assert.ok(layout.editorGap >= 11, JSON.stringify(layout));
        assert.ok(layout.sidebarGap >= 11, JSON.stringify(layout));
        assert.equal(layout.editorBackground, 'rgba(0, 0, 0, 0)');
        assert.notEqual(layout.formBackground, layout.editorBackground);
        assert.ok(layout.editorScroll > 0 && layout.sidebarScroll > 0);
        const footer = await page.evaluate(() => {
            const editor = document.querySelector('.engagement-editor');
            editor.scrollTop = editor.scrollHeight;
            return editor.getBoundingClientRect().bottom - document.querySelector('[data-engagement-start]').getBoundingClientRect().bottom;
        });
        assert.ok(footer >= 19, `Start button must stay inside the panel with bottom padding (${footer})`);
    } finally { await browser.close(); }
});

test('overlay fits desktop and mobile without horizontal overflow', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        for (const width of [1200, 800, 750, 514, 375]) {
            const page = await setup(browser, width);
            await page.click('[data-engagement-open="predictions"]');
            await page.locator('[data-engagement]').evaluate(node => Promise.all(node.getAnimations().map(animation => animation.finished)));
            const layout = await page.evaluate(() => {
                const dialog = document.querySelector('[data-engagement]'), body = dialog.querySelector('.engagement-body');
                const toggle = dialog.querySelector('.engagement-tabs');
                const modeHeader = dialog.querySelector('.engagement-header-mode');
                const buttons = [...toggle.querySelectorAll('button')];
                const rect = dialog.getBoundingClientRect();
                const toggleRect = toggle.getBoundingClientRect();
                const actions = dialog.querySelector('.engagement-header-actions'), close = dialog.querySelector('[data-engagement-close]');
                return {left: rect.left, right: rect.right, bottom: rect.bottom, height: innerHeight,
                    actionsRight: actions.getBoundingClientRect().right, closeRight: close.getBoundingClientRect().right,
                    toggleWidth: toggleRect.width, mainWidth: modeHeader.getBoundingClientRect().width,
                    toggleTop: toggleRect.top - rect.top,
                    buttonWidths: buttons.map(button => button.getBoundingClientRect().width),
                    headingHidden: dialog.querySelector('#engagement-title').classList.contains('sr-only'),
                    width: innerWidth, overflow: body.scrollWidth - body.clientWidth};
            });
            assert.ok(layout.left >= 0 && layout.right <= layout.width && layout.bottom <= layout.height, JSON.stringify(layout));
            assert.ok(layout.overflow <= 1, JSON.stringify(layout));
            assert.ok(layout.closeRight <= layout.actionsRight, JSON.stringify(layout));
            assert.ok(Math.abs(layout.toggleWidth - layout.mainWidth) < 1);
            assert.ok(layout.toggleTop <= 18, 'Slider should start at the top inset without an empty heading row');
            assert.ok(Math.abs(layout.buttonWidths[0] - layout.buttonWidths[1]) < 1);
            assert.equal(layout.headingHidden, true);
            await page.close();
        }
    } finally { await browser.close(); }
});

test('corrupt storage is ignored and stale history cannot overwrite another tab', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser, 1100, '{bad');
        await page.evaluate(() => { window.fetch = (url, options) => new Promise(resolve => {
            window.pending ||= {}; window.pending[url] = resolve;
        }); });
        await page.click('[data-engagement-open="predictions"]');
        await page.click('[data-engagement-tab="polls"]');
        await page.evaluate(() => {
            window.pending['/channel/api/engagement/polls']({ok: true, json: async () => ({items: [{title: 'New poll', choices: ['A', 'B'], duration: 60}]})});
            window.pending['/channel/api/engagement/predictions']({ok: true, json: async () => ({items: [{title: 'Old prediction', choices: ['A', 'B'], duration: 60}]})});
        });
        await page.waitForFunction(() => document.querySelector('[data-engagement-recent]').textContent.includes('New poll'));
        assert.doesNotMatch(await page.textContent('[data-engagement-recent]'), /Old prediction/);
    } finally { await browser.close(); }
});

test('pending creation prevents duplicate starts and shows permission errors without losing the draft', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-engagement-open="predictions"]');
        await page.fill('[name="title"]', 'Question');
        await page.locator('[data-engagement-choices] input').nth(0).fill('A');
        await page.locator('[data-engagement-choices] input').nth(1).fill('B');
        await page.evaluate(() => {
            const original = window.fetch;
            window.fetch = (url, options) => options?.method === 'POST' ? new Promise(resolve => {
                window.postCount = (window.postCount || 0) + 1;
                window.finishPost = resolve;
            }) : original(url, options);
        });
        await page.click('[data-engagement-start]');
        assert.equal(await page.locator('[data-engagement-start]').isDisabled(), true);
        assert.equal(await page.locator('[data-engagement-tab="polls"]').isDisabled(), true);
        await page.evaluate(() => document.querySelector('[data-engagement-form]').dispatchEvent(new Event('submit', {cancelable: true})));
        assert.equal(await page.evaluate(() => window.postCount), 1);
        await page.evaluate(() => window.finishPost({ok: false, json: async () => ({detail: 'Reconnect Twitch to grant permission.'})}));
        await page.waitForFunction(() => document.querySelector('[data-engagement-status]').textContent.includes('Reconnect Twitch'));
        assert.equal(await page.inputValue('[name="title"]'), 'Question');
        assert.equal(await page.locator('[data-engagement-start]').isDisabled(), false);
        await page.click('[data-engagement-close]');
        await page.click('[data-engagement-open="polls"]');
        assert.equal(await page.inputValue('[name="title"]'), 'Question');
        assert.equal(await page.locator('[data-engagement-choices] input').nth(0).inputValue(), 'A');
    } finally { await browser.close(); }
});


test('recent results keep separate IDs for identical templates and refresh stays circular', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.evaluate(() => {
            const original = window.fetch;
            window.fetch = (url, options) => (!options?.method || options.method === 'GET')
                ? Promise.resolve({ok: true, json: async () => ({items: ['first', 'second'].map(id => ({id, title: 'Same question', choices: ['Yes', 'No'], duration: 120}))})})
                : original(url, options);
        });
        for (const kind of ['predictions', 'polls']) {
            await page.click(`[data-engagement-open="${kind}"]`);
            const links = page.locator('[data-engagement-recent] .engagement-library-results');
            await links.nth(1).waitFor();
            assert.deepEqual(await links.evaluateAll(nodes => nodes.map(node => node.getAttribute('href'))), [`#${kind}-summary=first`, `#${kind}-summary=second`]);
            const circle = await page.locator('[data-engagement-refresh]').evaluate(node => ({width: node.offsetWidth, height: node.offsetHeight, radius: getComputedStyle(node).borderRadius}));
            assert.equal(circle.width, 32); assert.equal(circle.height, 32);
            assert.ok(circle.radius === '50%' || parseFloat(circle.radius) >= circle.width / 2);
            await page.click('[data-engagement-refresh]');
            assert.equal(await links.count(), 2);
            await links.last().click();
            await page.waitForFunction(kind => location.hash === `#${kind}-summary=second` && !document.querySelector('[data-engagement]').open, kind);
            assert.equal(await page.locator('[name="title"]').inputValue(), '', 'Results does not load the template into the draft');
        }
    } finally { await browser.close(); }
});


test('recent items archive locally by ID and type, and can be shown and restored', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        for (const kind of ['predictions', 'polls']) {
            const isOpen = await page.locator('[data-engagement]').evaluate(node => node.open);
            await page.click(isOpen ? `[data-engagement-tab="${kind}"]` : `[data-engagement-open="${kind}"]`);
            const archive = page.locator('[data-engagement-recent] .engagement-archive');
            await archive.waitFor();
            const bounds = await archive.boundingBox(), row = await page.locator('[data-engagement-recent] .engagement-library-row').boundingBox();
            assert.ok(bounds.x + bounds.width <= row.x + row.width && bounds.y >= row.y && bounds.y < row.y + 10);
            await archive.click();
            await page.locator('[data-engagement-recent] .engagement-library-row').waitFor({state: 'detached'});
            assert.equal(await page.locator('[data-engagement-recent] .engagement-library-row').count(), 0);
        }
        assert.equal(await page.evaluate(() => calls.filter(call => call.method === 'POST').length), 0);
        assert.deepEqual(await page.evaluate(() => JSON.parse(localStorage.getItem('dashboard-engagement-archived:1:v1'))), ['predictions:old', 'polls:old']);
        await page.click('[data-engagement-show-archived]');
        assert.equal(await page.locator('[data-engagement-recent] .is-archived').count(), 1);
        await page.click('[data-engagement-tab="predictions"]');
        const restore = page.locator('[data-engagement-recent] .engagement-archive');
        assert.match(await restore.getAttribute('aria-label'), /^Restore prediction:/);
        await restore.click();
        await page.locator('[data-engagement-recent] .is-archived').waitFor({state: 'detached'});
        assert.equal(await page.locator('[data-engagement-recent] .is-archived').count(), 0);
        await page.click('[data-engagement-show-archived]');
        assert.equal(await page.locator('[data-engagement-recent] .engagement-library-row').count(), 1);
        const archived = await page.evaluate(() => localStorage.getItem('dashboard-engagement-archived:1:v1'));
        const restored = await setup(browser, 1100, undefined, '/#polls', archived);
        await restored.waitForFunction(() => document.querySelector('[data-engagement-recent] p')?.textContent === 'No recent polls.');
        await restored.click('[data-engagement-show-archived]');
        await restored.locator('[data-engagement-recent] .is-archived').waitFor();
        assert.equal(await restored.locator('[data-engagement-recent] .engagement-library-results').getAttribute('href'), '#polls-summary=old');
    } finally { await browser.close(); }
});


test('archiving and restoring slide straight left at full size before removing the row', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-engagement-open="predictions"]');
        await page.locator('[data-engagement-recent] .engagement-archive').waitFor();
        await page.evaluate(() => {
            const original = Element.prototype.animate;
            Element.prototype.animate = function(...args) {
                const animation = original.apply(this, args);
                if (this.matches('.engagement-library-row')) { animation.pause(); window.archiveAnimation = animation; }
                return animation;
            };
        });
        for (const restoring of [false, true]) {
            if (restoring) await page.click('[data-engagement-show-archived]');
            const row = page.locator('[data-engagement-recent] .engagement-library-row');
            const initial = await row.boundingBox();
            await row.locator('.engagement-archive').click();
            assert.equal(await row.count(), 1, 'Row remains during its exit animation');
            const middle = await row.evaluate(node => {
                window.archiveAnimation.currentTime = 120;
                const transform = new DOMMatrix(getComputedStyle(node).transform);
                return {height: node.getBoundingClientRect().height, opacity: Number(getComputedStyle(node).opacity), x: transform.m41, y: transform.m42};
            });
            assert.ok(Math.abs(middle.height - initial.height) < 1);
            assert.equal(middle.opacity, 1);
            assert.ok(middle.x < 0);
            assert.equal(middle.y, 0);
            await page.evaluate(() => window.archiveAnimation.finish());
            await row.waitFor({state: 'detached'});
        }
        await page.emulateMedia({reducedMotion: 'reduce'});
        await page.click('[data-engagement-show-archived]');
        await page.locator('[data-engagement-recent] .engagement-archive').click();
        await page.locator('[data-engagement-recent] .engagement-library-row').waitFor({state: 'detached'});
    } finally { await browser.close(); }
});


test('history refresh shares pending reads but mutations invalidate outdated responses', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.evaluate(() => {
            const original = window.fetch;
            window.historyJobs = [];
            window.fetch = (url, options = {}) => /\/(polls|predictions)$/.test(url) && options.method !== 'POST'
                ? new Promise(resolve => historyJobs.push({resolve, signal: options.signal})) : original(url, options);
            window.historyResponse = title => ({ok: true, json: async () => ({items: [{id: title.replaceAll(' ', '-'), title, choices: ['Yes', 'No'], duration: 120}]})});
        });
        await page.click('[data-engagement-open="predictions"]');
        await page.click('[data-engagement-refresh]');
        await page.click('[data-engagement-refresh]');
        await page.click('[data-engagement-tab="predictions"]');
        assert.equal(await page.evaluate(() => historyJobs.length), 1);
        assert.equal(await page.evaluate(() => historyJobs[0].signal.aborted), false);
        await page.evaluate(() => historyJobs[0].resolve(historyResponse('First result')));
        await page.waitForFunction(() => document.querySelector('[data-engagement-recent] strong')?.textContent === 'First result');
        await page.click('[data-engagement-refresh]');
        await page.evaluate(() => document.dispatchEvent(new CustomEvent('dashboard-engagement-updated', {detail: {kind: 'predictions'}})));
        assert.equal(await page.evaluate(() => historyJobs.length), 3);
        assert.equal(await page.evaluate(() => historyJobs[1].signal.aborted), true);
        await page.evaluate(() => { historyJobs[2].resolve(historyResponse('Newest result')); historyJobs[1].resolve(historyResponse('Outdated result')); });
        await page.waitForFunction(() => document.querySelector('[data-engagement-recent] strong')?.textContent === 'Newest result');
        assert.equal(await page.locator('[data-engagement-recent] .engagement-library-row').count(), 1);
    } finally { await browser.close(); }
});


test('unchanged draft events leave template highlighting untouched', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-engagement-open="predictions"]');
        await page.locator('[data-engagement-recent] .engagement-library-row').waitFor();
        await page.evaluate(() => {
            window.matchChanges = 0;
            new MutationObserver(changes => { window.matchChanges += changes.length; }).observe(document.querySelector('[data-engagement-recent]'), {attributes: true, subtree: true});
            const form = document.querySelector('[data-engagement-form]');
            form.dispatchEvent(new Event('input', {bubbles: true}));
            form.dispatchEvent(new Event('change', {bubbles: true}));
        });
        assert.equal(await page.evaluate(() => matchChanges), 0);
    } finally { await browser.close(); }
});


test('reused history rows load and save the latest refreshed template data', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-engagement-open="polls"]');
        const row = page.locator('[data-engagement-recent] .engagement-library-row');
        await row.waitFor();
        await row.evaluate(node => { node.dataset.retained = 'true'; });
        await page.evaluate(() => {
            const original = window.fetch;
            window.fetch = (url, options = {}) => url.endsWith('/polls') && options.method !== 'POST'
                ? Promise.resolve({ok: true, json: async () => ({items: [{id: 'old', title: 'Updated question', choices: ['Up', 'Down'], duration: 300, channel_points_voting_enabled: true, channel_points_per_vote: 250}]})})
                : original(url, options);
        });
        await page.click('[data-engagement-refresh]');
        await page.waitForFunction(() => document.querySelector('[data-engagement-recent] strong').textContent === 'Updated question');
        assert.equal(await row.getAttribute('data-retained'), 'true');
        await row.locator('.engagement-load').click();
        assert.equal(await page.locator('[name="title"]').inputValue(), 'Updated question');
        assert.deepEqual(await page.locator('[data-engagement-choices] input').evaluateAll(nodes => nodes.map(node => node.value)), ['Up', 'Down']);
        assert.equal(await page.locator('[name="duration"]').inputValue(), '5m0s');
        assert.equal(await page.locator('[data-engagement-additional-votes]').isChecked(), true);
        assert.equal(await page.locator('[name="channel_points_per_vote"]').inputValue(), '250');
        await row.locator('.engagement-star').click();
        assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('dashboard-engagement:1:v1'))[0].title), 'Updated question');
        await row.locator('.engagement-star').click();
        await row.locator('.engagement-delete').click();
        await page.waitForFunction(() => JSON.parse(localStorage.getItem('dashboard-engagement:1:v1')).length === 0);
    } finally { await browser.close(); }
});
