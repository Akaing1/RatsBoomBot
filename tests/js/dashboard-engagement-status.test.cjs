const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();
const skip = !chromium || !fs.existsSync(executablePath || '');
const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
function fragment(start) { return start + template.split(start)[1].split('</dialog>')[0] + '</dialog>'; }
async function setup(browser, reduced = true, width = 1100, restored = null, hash = '') {
    const page = await browser.newPage({viewport: {width, height: 850}});
    if (reduced) await page.emulateMedia({reducedMotion: 'reduce'});
    await page.route('https://test.local/**', route => route.fulfill({contentType: 'text/html', body: '<html></html>'}));
    await page.goto(`https://test.local/${hash}`);
    await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}\n${fs.readFileSync('web/static/css/dashboard-engagement.css', 'utf8')}
        [data-engagement-cards]{position:absolute;right:20px;bottom:20px;width:280px}</style>
        <button data-engagement-open="polls">Polls</button><button data-engagement-open="predictions">Predictions</button>
        <div data-engagement-cards data-channel-id="1" data-csrf-token="csrf"></div>
        ${fragment('<dialog id="dashboard-engagement"')}${fragment('<dialog class="engagement-summary-dialog"')}`);
    await page.evaluate(restored => {
        window.calls = []; window.items = restored?.items || {};
        if (restored) localStorage.setItem('dashboard-engagement-active:1:v1', restored.references);
        document.querySelector('[data-engagement]').dataset.csrfToken = 'csrf';
        window.fetch = async (url, options = {}) => {
            const body = new URLSearchParams(options.body);
            window.calls.push({url, method: options.method || 'GET', body: body.toString()});
            const kind = url.includes('/predictions') ? 'predictions' : 'polls';
            const id = kind === 'polls' ? 'poll-1' : 'prediction-1';
            if (options.method === 'POST' && !url.endsWith('/action')) {
                const item = {id, kind, title: body.get('title'), status: 'ACTIVE', duration: Number(body.get('duration')),
                    created_at: new Date().toISOString(), options: JSON.parse(body.get('choices')).map((title, i) => ({id: `option-${i}`, title, votes: i ? 1 : 3, points: i ? 100 : 300}))};
                window.items[id] = item;
                return {ok: true, json: async () => ({item: structuredClone(item)})};
            }
            if (url.endsWith('/action')) {
                const item = window.items[id];
                const action = body.get('action');
                if (action !== 'delete' || ['ACTIVE', 'LOCKED'].includes(item.status)) item.status = action === 'resolve' ? 'RESOLVED' : action === 'delete' ? (kind === 'polls' ? 'ARCHIVED' : 'CANCELED') : kind === 'polls' ? 'TERMINATED' : 'LOCKED';
                if (action === 'resolve') item.winning_outcome_id = body.get('winning_outcome_id');
                return {ok: true, json: async () => ({item: structuredClone(item), dismissed: action === 'delete'})};
            }
            if (/\/(polls|predictions)$/.test(url)) return {ok: true, json: async () => ({items: Object.values(window.items)
                .filter(item => item.kind === kind).map(item => ({...item, choices: item.options.map(option => option.title)}))})};
            if (url.endsWith('/latest')) {
                const items = Object.values(window.items).filter(item => item.kind === kind);
                items.sort((a, b) => Number(b.status === 'ACTIVE') - Number(a.status === 'ACTIVE') ||
                    Number(b.status === 'LOCKED') - Number(a.status === 'LOCKED') ||
                    (b.created_at || '').localeCompare(a.created_at || ''));
                return {ok: true, json: async () => ({item: structuredClone(items[0])})};
            }
            return {ok: true, json: async () => ({item: structuredClone(window.items[id])})};
        };
    }, restored);
    await page.addScriptTag({content: fs.readFileSync('web/static/js/dashboard-engagement-status.js', 'utf8')});
    await page.addScriptTag({content: fs.readFileSync('web/static/js/dashboard-engagement.js', 'utf8')});
    return page;
}
async function create(page, kind) {
    await page.click(`[data-engagement-open="${kind}"]`);
    await page.fill('[name="title"]', kind === 'polls' ? 'What next?' : 'Will we win?');
    await page.locator('[data-engagement-choices] input').nth(0).fill('Yes');
    await page.locator('[data-engagement-choices] input').nth(1).fill('No');
    await page.click('[data-engagement-start]');
    await page.waitForFunction(() => !document.querySelector('[data-engagement]').open);
}

async function openSummary(card) {
    if (await card.getAttribute('aria-expanded') !== 'true') await card.locator('strong').click();
    await card.locator('[data-engagement-card-action="summary"]').click();
}

test('created poll animates into a clickable chat card and shows vote totals and close controls', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser, false);
        await create(page, 'polls');
        await page.waitForSelector('.engagement-flight');
        assert.equal(await page.locator('.engagement-flight').getAttribute('aria-hidden'), 'true');
        await page.waitForSelector('.engagement-flight', {state: 'detached'});
        const card = page.locator('.dashboard-engagement-card');
        assert.match(await card.textContent(), /What next\?/);
        await openSummary(card);
        await page.waitForSelector('[data-engagement-summary][open]');
        assert.match(await page.textContent('[data-engagement-summary-options]'), /3 votes/);
        assert.equal(await page.locator('[data-engagement-summary-resolve]').isVisible(), false);
        await page.click('[data-engagement-summary-lock]');
        await page.waitForFunction(() => window.items['poll-1'].status === 'TERMINATED');
        assert.match(await card.textContent(), /Closed/);
        const action = await page.evaluate(() => window.calls.find(call => call.url.endsWith('/action')));
        assert.equal(new URLSearchParams(action.body).get('action'), 'close');
        assert.equal(await page.locator('[data-engagement-summary-delete]').isVisible(), false);
        await page.click('[data-engagement-summary-close]');
        await page.waitForFunction(() => !document.querySelector('[data-engagement-summary]').open);
        assert.equal(await page.evaluate(() => window.items['poll-1'].status), 'TERMINATED');
        await card.locator('[data-engagement-card-action="close"]').click();
        assert.equal(await card.count(), 0);
    } finally { await browser.close(); }
});

test('chat summaries restore from channel-scoped references without creating new polls', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await create(page, 'polls');
        const restored = await page.evaluate(() => ({items: window.items, references: localStorage.getItem('dashboard-engagement-active:1:v1')}));
        await page.close();
        const next = await setup(browser, true, 1100, restored);
        await next.waitForFunction(() => document.querySelector('.dashboard-engagement-card strong')?.textContent === 'What next?');
        assert.equal(await next.evaluate(() => window.calls.filter(call => call.method === 'POST').length), 0);
        assert.equal(await next.evaluate(() => window.calls.filter(call => call.url.endsWith('/poll-1')).length), 1);
    } finally { await browser.close(); }
});

test('zero-percent results have no bar and show their number above the baseline', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await create(page, 'polls');
        await page.evaluate(() => {
            const item = structuredClone(window.items['poll-1']);
            item.status = 'ARCHIVED'; item.options.forEach(option => { option.votes = 0; });
            document.dispatchEvent(new CustomEvent('dashboard-engagement-started', {detail: {item}}));
        });
        const chart = page.locator('.engagement-mini-chart');
        assert.equal(await chart.getAttribute('aria-label'), 'Results: Yes: 0%, No: 0%');
        const bars = await chart.locator(':scope > div > div').evaluateAll(nodes => nodes.map(node => ({height: node.getBoundingClientRect().height, value: node.style.height, color: getComputedStyle(node).backgroundColor})));
        assert.ok(bars.every(bar => bar.height === 0 && bar.value === '0%'), JSON.stringify(bars));
        assert.deepEqual(await chart.locator('small').allTextContents(), ['0', '0']);
        const above = await chart.locator('small').evaluateAll(nodes => nodes.every(node => node.getBoundingClientRect().bottom <= node.parentElement.firstChild.getBoundingClientRect().top));
        assert.equal(above, true);
    } finally { await browser.close(); }
});

test('card body toggles an inline quick preview while Summary opens detailed results', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await create(page, 'polls');
        const card = page.locator('.dashboard-engagement-card'), preview = card.locator('.engagement-quick-preview');
        assert.equal(await preview.isVisible(), false);
        const mini = card.locator('.engagement-mini-chart');
        assert.equal(await mini.isVisible(), true);
        const chartBounds = await mini.boundingBox(), headingBounds = await card.locator('strong').boundingBox();
        const buttonsBounds = await card.locator('.dashboard-engagement-card-actions').boundingBox();
        assert.equal(Math.round(chartBounds.width), 52);
        assert.equal(Math.round(chartBounds.height), 46);
        assert.ok(chartBounds.x >= headingBounds.x + headingBounds.width && chartBounds.x + chartBounds.width <= buttonsBounds.x, 'Mini chart stays between the title and buttons');
        assert.equal(await mini.getAttribute('aria-label'), 'Results: Yes: 75%, No: 25%');
        assert.deepEqual(await mini.locator(':scope > div > span').allTextContents(), ['Yes', 'No']);
        assert.deepEqual(await mini.locator('small').allTextContents(), ['75', '25']);
        assert.equal(await mini.locator(':scope > div > div').first().evaluate(node => node.style.height), '75%');
        const barHeights = await mini.locator(':scope > div > div').evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().height));
        assert.ok(barHeights[0] > 15 && Math.abs(barHeights[0] / barHeights[1] - 3) < .1, `Bar heights reflect the 75/25 split: ${barHeights}`);
        const labelsInside = await mini.locator(':scope > div > span').evaluateAll(nodes => nodes.every(node => {
            const label = node.getBoundingClientRect(), chart = node.closest('.engagement-mini-chart').getBoundingClientRect();
            return label.top >= chart.top && label.bottom <= chart.bottom + .5;
        }));
        assert.equal(labelsInside, true, 'Choice labels remain inside the chart');
        const numbersFit = await mini.locator('small').evaluateAll(nodes => nodes.every(node => {
            const text = document.createRange(); text.selectNodeContents(node);
            const bounds = text.getBoundingClientRect(), bar = node.parentElement.getBoundingClientRect();
            const fitsHorizontally = bounds.left >= bar.left - .5 && bounds.right <= bar.right + .5;
            return fitsHorizontally && bounds.top >= bar.top && bounds.bottom <= bar.bottom;
        }));
        assert.equal(numbersFit, true, 'Numbers fit within their chart columns');
        const numberRows = await mini.locator('small').evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().y));
        assert.ok(Math.max(...numberRows) - Math.min(...numberRows) < 1, 'All numbers line up horizontally');
        await card.locator('strong').click();
        assert.equal(await mini.isVisible(), false);
        assert.equal(await preview.isVisible(), true);
        assert.equal(await card.getAttribute('aria-expanded'), 'true');
        assert.match(await preview.textContent(), /Yes75% · 3 votes/);
        assert.equal(await preview.locator('[role="progressbar"]').first().getAttribute('aria-valuenow'), '75');
        assert.equal(await page.locator('[data-engagement-summary]').evaluate(node => node.open), false);
        await card.focus(); await page.keyboard.press('Enter');
        assert.equal(await preview.isVisible(), false);
        assert.equal(await mini.isVisible(), true);
        await openSummary(card);
        assert.equal(await preview.isVisible(), true, 'Summary keeps the card expanded');
        assert.match(await page.textContent('[data-engagement-summary-state]'), /4 total votes/);
        assert.match(await page.textContent('[data-engagement-summary-duration]'), /Voting duration: 2m0s/);
        assert.ok(await page.textContent('[data-engagement-summary-times]'));
        assert.doesNotMatch(await page.textContent('[data-engagement-summary-times]'), /Started:/);
        assert.match(await page.textContent('[data-engagement-summary-options]'), /75% · 3 votes/);
        const summaryBars = page.locator('[data-engagement-summary-options] [role="progressbar"]');
        assert.deepEqual(await summaryBars.evaluateAll(nodes => nodes.map(node => node.getAttribute('aria-valuenow'))), ['75', '25']);
        const summaryWidths = await summaryBars.locator(':scope > div').evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().width));
        assert.ok(summaryWidths[0] > 0 && Math.abs(summaryWidths[0] / summaryWidths[1] - 3) < .1);
        await page.click('[data-engagement-summary-close]');
        await preview.locator('[role="progressbar"]').first().evaluate(node => { node.dataset.retained = 'true'; });
        await page.evaluate(() => { window.items['poll-1'].options[0].votes = 7; });
        await page.waitForFunction(() => document.querySelector('.engagement-quick-preview').textContent.includes('88% · 7 votes'), {timeout: 8000});
        assert.equal(await preview.locator('[role="progressbar"]').first().getAttribute('aria-valuenow'), '88');
        assert.equal(await mini.getAttribute('aria-label'), 'Results: Yes: 88%, No: 13%');
        assert.deepEqual(await mini.locator('small').allTextContents(), ['88', '13']);
        assert.equal(await preview.locator('[role="progressbar"]').first().getAttribute('data-retained'), 'true', 'Live updates retain the graph bars for smooth transitions');
    } finally { await browser.close(); }
});

test('prediction summary can lock voting and confirm an outcome without accidental resolution', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await create(page, 'predictions'); await openSummary(page.locator('.dashboard-engagement-card'));
        assert.deepEqual(await page.locator('[data-engagement-summary-options] [role="progressbar"]').evaluateAll(nodes => nodes.map(node => node.getAttribute('aria-valuenow'))), ['75', '25']);
        assert.equal(await page.locator('[data-engagement-summary-resolve]').isDisabled(), true);
        await page.click('[data-engagement-summary-lock]');
        await page.waitForFunction(() => window.items['prediction-1'].status === 'LOCKED');
        await page.check('[name="engagement-winning-outcome"][value="option-0"]');
        await page.click('[data-engagement-summary-resolve]');
        assert.match(await page.textContent('[data-engagement-summary-confirm-text]'), /awards Channel Points/);
        assert.equal(await page.evaluate(() => window.items['prediction-1'].status), 'LOCKED');
        await page.click('[data-engagement-summary-confirm-no]');
        assert.equal(await page.evaluate(() => window.items['prediction-1'].status), 'LOCKED');
        await page.click('[data-engagement-summary-resolve]');
        await page.click('[data-engagement-summary-confirm-yes]');
        await page.waitForFunction(() => window.items['prediction-1'].status === 'RESOLVED');
        assert.match(await page.textContent('[data-engagement-summary-options]'), /Winner/);
        assert.equal(await page.locator('[data-engagement-summary-resolve]').isVisible(), false);
    } finally { await browser.close(); }
});

test('deleting a prediction requires confirmation, refunds via cancel, and removes its chat card', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser, true, 514);
        await create(page, 'predictions'); await openSummary(page.locator('.dashboard-engagement-card'));
        await page.click('[data-engagement-summary-delete]');
        assert.match(await page.textContent('[data-engagement-summary-confirm-text]'), /all Channel Points refunded/);
        assert.equal(await page.locator('.dashboard-engagement-card').count(), 1);
        await page.click('[data-engagement-summary-confirm-yes]');
        await page.waitForFunction(() => !document.querySelector('[data-engagement-summary]').open);
        assert.equal(await page.locator('.dashboard-engagement-card').count(), 0);
        assert.equal(await page.evaluate(() => window.items['prediction-1'].status), 'CANCELED');
        assert.deepEqual(await page.evaluate(() => JSON.parse(localStorage.getItem('dashboard-engagement-active:1:v1'))), []);
    } finally { await browser.close(); }
});

test('poll and prediction summaries coexist, and live reads share one in-flight request', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await create(page, 'polls'); await create(page, 'predictions');
        assert.equal(await page.locator('.dashboard-engagement-card').count(), 2);
        await page.evaluate(() => {
            const original = window.fetch;
            window.fetch = (url, options) => url.endsWith('/poll-1') ? new Promise(resolve => {
                window.readCount = (window.readCount || 0) + 1;
                window.finishRead = () => original(url, options).then(resolve);
            }) : original(url, options);
        });
        await openSummary(page.locator('.dashboard-engagement-card').first());
        await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
        assert.equal(await page.evaluate(() => window.readCount), 1);
        await page.evaluate(() => window.finishRead());
        await page.waitForFunction(() => document.querySelector('[data-engagement-summary-options]').textContent.includes('3 votes'));
    } finally { await browser.close(); }
});

test('chat cards only show Summary and Close, and closing never changes Twitch state', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser, true, 375);
        await create(page, 'polls');
        const poll = page.locator('.dashboard-engagement-card').first();
        const titleBounds = await poll.locator('strong').boundingBox();
        const actionBounds = await poll.locator('.dashboard-engagement-card-actions').boundingBox();
        assert.ok(actionBounds.x >= titleBounds.x + titleBounds.width, 'Actions sit to the right of the title');
        assert.deepEqual(await poll.locator('button:visible').allTextContents(), ['Close']);
        await poll.locator('strong').click();
        assert.deepEqual(await poll.locator('button:visible').allTextContents(), ['Summary', 'Close']);
        const summaryBounds = await poll.locator('[data-engagement-card-action="summary"]').boundingBox();
        const closeBounds = await poll.locator('[data-engagement-card-action="close"]').boundingBox();
        assert.ok(Math.abs(summaryBounds.y - closeBounds.y) < 1 && closeBounds.x >= summaryBounds.x + summaryBounds.width, 'Buttons are side by side');
        assert.ok(await poll.evaluate(node => node.scrollWidth <= node.clientWidth), 'Compact card does not overflow');
        const postsBefore = await page.evaluate(() => calls.filter(call => call.method === 'POST').length);
        await poll.locator('[data-engagement-card-action="close"]').click();
        assert.equal(await poll.count(), 0);
        assert.equal(await page.evaluate(() => window.items['poll-1'].status), 'ACTIVE');
        assert.equal(await page.evaluate(() => calls.filter(call => call.method === 'POST').length), postsBefore);
        assert.deepEqual(await page.evaluate(() => JSON.parse(localStorage.getItem('dashboard-engagement-active:1:v1'))), []);
        await create(page, 'predictions');
        const prediction = page.locator('.dashboard-engagement-card').last();
        assert.deepEqual(await prediction.locator('button:visible').allTextContents(), ['Close']);
        await openSummary(prediction);
        assert.equal(await page.locator('[data-engagement-summary-lock]').textContent(), 'Lock voting');
        assert.equal(await page.locator('[data-engagement-summary-delete]').textContent(), 'Delete');
        await page.click('[data-engagement-summary-close]');
        await prediction.locator('[data-engagement-card-action="close"]').click();
        assert.equal(await page.evaluate(() => window.items['prediction-1'].status), 'ACTIVE');
        assert.equal(await page.locator('.dashboard-engagement-card').count(), 0);
        assert.equal(await page.evaluate(() => calls.some(call => call.url.endsWith('/action'))), false);
    } finally { await browser.close(); }
});


test('summary links restore directly and New opens the matching editor with history navigation', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        for (const kind of ['polls', 'predictions']) {
            const page = await setup(browser);
            await create(page, kind);
            await openSummary(page.locator('.dashboard-engagement-card'));
            const hash = `#${kind}-summary=${kind === 'polls' ? 'poll-1' : 'prediction-1'}`;
            assert.equal(await page.evaluate(() => location.hash), hash);
            const link = page.locator('[data-engagement-summary-new]');
            assert.equal(await link.textContent(), kind === 'polls' ? 'New poll' : 'New prediction');
            assert.equal(await link.getAttribute('href'), `#${kind}`);
            await link.click();
            await page.waitForFunction(kind => location.hash === `#${kind}` && document.querySelector('[data-engagement]').open && !document.querySelector('[data-engagement-summary]').open, kind);
            assert.equal(await page.locator(`[data-engagement-tab="${kind}"]`).getAttribute('aria-selected'), 'true');
            const results = page.locator('[data-engagement-recent] .engagement-library-results');
            assert.equal(await results.getAttribute('href'), hash);
            await page.goBack();
            await page.waitForFunction(() => document.querySelector('[data-engagement-summary]').open && !document.querySelector('[data-engagement]').open);
            assert.equal(await page.evaluate(() => location.hash), hash);
            await page.goForward();
            await page.waitForFunction(() => document.querySelector('[data-engagement]').open && !document.querySelector('[data-engagement-summary]').open);
            const restored = await page.evaluate(() => ({items: window.items, references: '[]'}));
            await page.close();
            const direct = await setup(browser, true, 1100, restored, hash);
            await direct.waitForFunction(() => document.querySelector('[data-engagement-summary-options]').textContent.includes('75%'));
            assert.equal(await direct.locator('[data-engagement-summary]').evaluate(node => node.open), true);
            assert.equal(await direct.evaluate(() => calls.some(call => call.method === 'POST')), false);
            await direct.evaluate(kind => { location.hash = `#${kind}-summary`; }, kind);
            await direct.evaluate(kind => {
                const previous = Object.values(window.items).find(item => item.kind === kind);
                previous.status = kind === 'polls' ? 'COMPLETED' : 'RESOLVED';
                window.items.next = {...structuredClone(previous), id: 'next', title: 'New current item', status: 'ACTIVE', created_at: new Date(Date.now() + 1000).toISOString()};
            }, kind);
            assert.equal(await direct.locator('[data-engagement-summary-refresh]').count(), 0);
            await direct.waitForFunction(() => document.querySelector('[data-engagement-summary-title]').textContent === 'New current item');
            assert.equal(await direct.evaluate(() => location.hash), `#${kind}-summary`, 'A newer item keeps the same base summary link');
            assert.equal(await direct.locator('.dashboard-engagement-card strong').textContent(), 'New current item');
            await direct.evaluate(hash => { location.hash = hash; }, hash);
            await direct.waitForFunction(() => ['What next?', 'Will we win?'].includes(document.querySelector('[data-engagement-summary-title]').textContent));
            assert.equal(await direct.evaluate(() => location.hash), hash, 'An ID link still opens the older result');
            assert.equal(await direct.locator('.dashboard-engagement-card strong').textContent(), 'New current item', 'Viewing history does not replace the current chat card');
            await direct.click('[data-engagement-summary-close]');
            await direct.waitForFunction(() => !location.hash);
            await direct.close();
        }
    } finally { await browser.close(); }
});


test('Run again starts a fresh copy with the original settings after the item finishes', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        for (const kind of ['polls', 'predictions']) {
            const page = await setup(browser);
            await create(page, kind);
            const card = page.locator('.dashboard-engagement-card');
            await openSummary(card);
            assert.equal(await page.locator('[data-engagement-summary-repeat]').isDisabled(), true);
            await page.click('[data-engagement-summary-close]');
            await page.evaluate(kind => {
                const item = Object.values(window.items).find(item => item.kind === kind);
                item.status = kind === 'polls' ? 'COMPLETED' : 'RESOLVED';
                item.duration = 300;
                if (kind === 'polls') { item.channel_points_voting_enabled = true; item.channel_points_per_vote = 250; }
            }, kind);
            await card.locator('[data-engagement-card-action="summary"]').click();
            await page.waitForFunction(() => !document.querySelector('[data-engagement-summary-repeat]').disabled);
            await page.click('[data-engagement-summary-repeat]');
            await page.waitForFunction(() => calls.filter(call => call.method === 'POST' && !call.url.endsWith('/action')).length === 2 && !document.querySelector('[data-engagement]').open);
            const posts = await page.evaluate(() => calls.filter(call => call.method === 'POST'));
            assert.equal(posts.length, 2);
            const first = new URLSearchParams(posts[0].body), repeated = new URLSearchParams(posts[1].body);
            assert.equal(repeated.get('title'), first.get('title'));
            assert.equal(repeated.get('choices'), first.get('choices'));
            assert.equal(repeated.get('duration'), '300');
            if (kind === 'polls') {
                assert.equal(repeated.get('channel_points_voting_enabled'), 'true');
                assert.equal(repeated.get('channel_points_per_vote'), '250');
            } else assert.equal(repeated.has('channel_points_voting_enabled'), false);
            await page.close();
        }
    } finally { await browser.close(); }
});


test('summary X returns to chat or the original creator and preserves its draft', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        for (const kind of ['polls', 'predictions']) {
            const page = await setup(browser);
            await create(page, kind);
            const card = page.locator('.dashboard-engagement-card');
            await openSummary(card);
            await page.click('[data-engagement-summary-close]');
            await page.waitForFunction(() => !location.hash && !document.querySelector('[data-engagement-summary]').open && !document.querySelector('[data-engagement]').open);
            assert.equal(await card.evaluate(node => document.activeElement === node), true);
            await page.click(`[data-engagement-open="${kind}"]`);
            await page.fill('[name="title"]', 'Unsaved draft');
            await page.locator('[data-engagement-choices] input').first().fill('Draft option');
            const results = page.locator('[data-engagement-recent] .engagement-library-results');
            await results.click();
            await page.waitForFunction(() => document.querySelector('[data-engagement-summary]').open && !document.querySelector('[data-engagement]').open);
            await page.click('[data-engagement-summary-close]');
            await page.waitForFunction(kind => location.hash === `#${kind}` && document.querySelector('[data-engagement]').open && !document.querySelector('[data-engagement-summary]').open, kind);
            assert.equal(await page.locator('[name="title"]').inputValue(), 'Unsaved draft');
            assert.equal(await page.locator('[data-engagement-choices] input').first().inputValue(), 'Draft option');
            assert.equal(await page.locator(`[data-engagement-tab="${kind}"]`).getAttribute('aria-selected'), 'true');
            await results.click();
            await page.waitForFunction(() => document.querySelector('[data-engagement-summary]').open);
            await page.keyboard.press('Escape');
            await page.waitForFunction(() => document.querySelector('[data-engagement]').open && !document.querySelector('[data-engagement-summary]').open);
            await page.close();
        }
    } finally { await browser.close(); }
});


test('live summary updates retain bars, selected outcomes and keyboard focus', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await create(page, 'predictions');
        await openSummary(page.locator('.dashboard-engagement-card'));
        const radio = page.locator('[name="engagement-winning-outcome"]').first();
        await radio.check(); await radio.focus();
        await page.evaluate(() => {
            const options = document.querySelector('[data-engagement-summary-options]');
            window.originalSummaryRow = options.firstElementChild;
            window.summaryRowChanges = 0;
            new MutationObserver(changes => { window.summaryRowChanges += changes.length; }).observe(options, {childList: true});
            window.items['prediction-1'].options[0].channel_points = 0;
            window.items['prediction-1'].options[0].points = 700;
            document.dispatchEvent(new Event('visibilitychange'));
        });
        await page.waitForFunction(() => document.querySelector('[data-engagement-summary-options] [role="progressbar"]').getAttribute('aria-valuenow') === '88');
        assert.equal(await radio.isChecked(), true);
        assert.equal(await radio.evaluate(node => document.activeElement === node), true);
        assert.equal(await page.evaluate(() => document.querySelector('[data-engagement-summary-options]').firstElementChild === originalSummaryRow), true);
        assert.equal(await page.evaluate(() => summaryRowChanges), 0);
    } finally { await browser.close(); }
});

test('duplicate history events share a single pending latest-summary request', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await create(page, 'polls');
        await page.locator('[data-engagement-card-action="close"]').click();
        await page.evaluate(() => {
            const original = window.fetch;
            window.latestReads = 0;
            window.fetch = (url, options) => url.endsWith('/latest') ? new Promise(resolve => {
                window.latestReads++;
                window.finishLatest = () => original(url, options).then(resolve);
            }) : original(url, options);
            location.hash = '#polls-summary';
        });
        await page.waitForFunction(() => latestReads === 1);
        await page.evaluate(() => window.dispatchEvent(new PopStateEvent('popstate')));
        assert.equal(await page.evaluate(() => latestReads), 1);
        await page.evaluate(() => finishLatest());
        await page.waitForFunction(() => document.querySelector('[data-engagement-summary-title]').textContent === 'What next?');
        assert.equal(await page.locator('.dashboard-engagement-card').count(), 1);
    } finally { await browser.close(); }
});


test('confirmed actions do not wait for or get overwritten by an older background read', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await create(page, 'polls');
        await openSummary(page.locator('.dashboard-engagement-card'));
        await page.evaluate(() => {
            const original = window.fetch, outdated = structuredClone(window.items['poll-1']);
            window.fetch = (url, options = {}) => url.endsWith('/poll-1') && options.method !== 'POST'
                ? new Promise(resolve => { window.finishOutdated = () => resolve({ok: true, json: async () => ({item: outdated})}); })
                : original(url, options);
            document.dispatchEvent(new Event('visibilitychange'));
        });
        await page.waitForFunction(() => typeof finishOutdated === 'function');
        await page.click('[data-engagement-summary-lock]');
        await page.waitForFunction(() => document.querySelector('[data-engagement-summary-state]').textContent.includes('Closed'));
        assert.equal(await page.locator('[data-engagement-summary-lock]').isVisible(), false);
        await page.evaluate(() => finishOutdated());
        assert.match(await page.textContent('[data-engagement-summary-state]'), /Closed/);
        assert.equal(await page.locator('[data-engagement-summary-lock]').isVisible(), false);
        assert.equal(await page.evaluate(() => calls.filter(call => call.url.endsWith('/action')).length), 1);
    } finally { await browser.close(); }
});


test('reduced-motion creation skips cloning the editor for the flight animation', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.evaluate(() => {
            const original = Element.prototype.cloneNode;
            window.editorClones = 0;
            Element.prototype.cloneNode = function(...args) {
                if (this.matches('.engagement-editor')) window.editorClones++;
                return original.apply(this, args);
            };
        });
        await create(page, 'polls');
        assert.equal(await page.evaluate(() => editorClones), 0);
        assert.equal(await page.locator('.engagement-flight').count(), 0);
        await page.waitForFunction(() => document.activeElement === document.querySelector('.dashboard-engagement-card'));
    } finally { await browser.close(); }
});

test('history restoration resumes live updates and ignores reads from before leaving', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await create(page, 'polls');
        await openSummary(page.locator('.dashboard-engagement-card'));
        await page.evaluate(() => {
            const original = window.fetch, outdated = structuredClone(window.items['poll-1']);
            window.restoreReads = 0;
            window.fetch = (url, options = {}) => {
                if (url.endsWith('/poll-1') && ++window.restoreReads === 1)
                    return new Promise(resolve => { window.oldReadSignal = options.signal; window.finishBeforeLeaving = () => resolve({ok: true, json: async () => ({item: outdated})}); });
                return original(url, options);
            };
            document.dispatchEvent(new Event('visibilitychange'));
        });
        await page.waitForFunction(() => typeof finishBeforeLeaving === 'function');
        await page.evaluate(() => {
            window.dispatchEvent(new PageTransitionEvent('pagehide', {persisted: true}));
            window.items['poll-1'].options[0].votes = 7;
            window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted: true}));
        });
        assert.equal(await page.evaluate(() => oldReadSignal.aborted), true);
        await page.waitForFunction(() => document.querySelector('[data-engagement-summary-options] [role="progressbar"]').getAttribute('aria-valuenow') === '88');
        await page.evaluate(() => finishBeforeLeaving());
        assert.match(await page.textContent('[data-engagement-summary-options]'), /88%/);
        await page.evaluate(() => { window.items['poll-1'].options[0].votes = 1; });
        await page.waitForFunction(() => document.querySelector('[data-engagement-summary-options] [role="progressbar"]').getAttribute('aria-valuenow') === '50', {timeout: 8000});
    } finally { await browser.close(); }
});


test('a successful automatic update clears a temporary summary error', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await create(page, 'polls');
        await openSummary(page.locator('.dashboard-engagement-card'));
        await page.evaluate(() => {
            const original = window.fetch;
            let failed = false;
            window.fetch = (url, options) => {
                if (url.endsWith('/poll-1') && !failed) { failed = true; return Promise.resolve({ok: false, status: 502, json: async () => ({detail: 'Temporary error'})}); }
                return original(url, options);
            };
            document.dispatchEvent(new Event('visibilitychange'));
        });
        await page.waitForFunction(() => document.querySelector('[data-engagement-summary-status]').textContent === 'Temporary error');
        await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
        await page.waitForFunction(() => !document.querySelector('[data-engagement-summary-status]').textContent);
        assert.doesNotMatch(await page.locator('.dashboard-engagement-card').textContent(), /Temporary error/);
    } finally { await browser.close(); }
});

test('summary navigation during an action is applied after that action finishes', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await create(page, 'polls'); await create(page, 'predictions');
        await openSummary(page.locator('.dashboard-engagement-card').first());
        await page.evaluate(() => {
            const original = window.fetch;
            window.fetch = (url, options) => url.endsWith('/action') ? new Promise(resolve => {
                window.finishAction = () => original(url, options).then(resolve);
            }) : original(url, options);
        });
        await page.click('[data-engagement-summary-lock]');
        await page.waitForFunction(() => typeof finishAction === 'function');
        await page.evaluate(() => { location.hash = '#predictions-summary'; });
        await page.waitForFunction(() => location.hash === '#predictions-summary');
        await page.evaluate(() => finishAction());
        await page.waitForFunction(() => document.querySelector('[data-engagement-summary-title]').textContent === 'Will we win?');
        assert.equal(await page.locator('[data-engagement-summary-heading]').textContent(), 'Prediction summary');
        assert.equal(await page.evaluate(() => window.items['poll-1'].status), 'TERMINATED');
    } finally { await browser.close(); }
});
