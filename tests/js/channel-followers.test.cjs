const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();
const skip = !chromium || !fs.existsSync(executablePath || '');
async function setup(browser, width = 1100, hash = '') {
    const page = await browser.newPage({viewport: {width, height: 850}});
    await page.route('https://test.local/**', route => route.fulfill({contentType: 'text/html', body: '<html></html>'}));
    await page.route('https://static-cdn.jtvnw.net/**', route => route.fulfill({contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/f1sAAAAASUVORK5CYII=', 'base64')}));
    await page.goto(`https://test.local/${hash}`);
    const template = fs.readFileSync('web/templates/channel/followers.html', 'utf8');
    const content = '<section class="followers-page"' + template.split('<section class="followers-page"')[1].split('</section>')[0] + '</section>';
    await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}\n${fs.readFileSync('web/static/css/channel-followers.css', 'utf8')}body{margin:0;padding:16px;box-sizing:border-box}</style>${content.replace('data-channel-id="{{ channel_id }}"', 'data-channel-id="1"')}`);
    await page.evaluate(() => {
        window.calls = []; window.profileCalls = [];
        window.fetch = async (url, options) => {
            const params = new URL(url, location.href).searchParams;
            if (url.startsWith('/channel/api/followers/profiles')) {
                profileCalls.push(url);
                return {ok: true, json: async () => ({profiles: params.get('ids').split(',').map(id => ({id, profile_image_url: `https://static-cdn.jtvnw.net/test/${id}.png`}))})};
            }
            calls.push(url);
            if (params.get('search') === 'error') return {ok: false, json: async () => ({detail: 'Reconnect Twitch.'})};
            let rows = Array.from({length: 128}, (_, i) => ({user_id: String(i + 1), name: i === 8 ? 'USER9' : i === 9 ? 'Friendly Cat' : `User${String(i + 1).padStart(3, '0')}`, login: `user${i + 1}`,
                followed_at: '2026-10-01T00:00:00Z', label: i === 1 ? 'VIP · Sub tier 2' : 'Follower', role_labels: i === 1 ? ['VIP', 'Sub tier 2'] : [], points: i * 10, messages: i,
                lifetime_points: i * 20, first_redeems: 3, check_ins: 12, achievement_count: 2, points_spent: null, watch_minutes: 125, first_seen: null, last_watched: i === 0 ? null : '2026-10-25 22:00:00', last_seen: i === 0 ? null : '2026-10-26 01:00:00', ...(window.rowUpdates?.[String(i + 1)] || {})}));
            if (params.get('rank')) rows = rows.filter(row => row.role_labels.includes('VIP'));
            if (params.get('mutual') === 'true') rows = rows.filter(row => row.user_id === '2');
            if (params.get('raid_favorites') === 'true') rows = rows.filter(row => (params.get('favorites') || '').split(',').includes(row.user_id));
            if (params.get('search')) rows = rows.filter(row => row.name.toLowerCase().includes(params.get('search').toLowerCase()));
            const size = Number(params.get('page_size')), pages = Math.max(1, Math.ceil(rows.length / size)), page = Math.min(Number(params.get('page')), pages), count = rows.length;
            rows = rows.slice((page - 1) * size, page * size);
            return {ok: true, json: async () => ({rows, page, pages, count, total: 128, loaded: 128, loading: false, warnings: [], error: ''})};
        };
    });
    await page.addScriptTag({content: fs.readFileSync('web/static/js/channel-followers.js', 'utf8')});
    await page.waitForFunction(() => document.querySelector('[data-followers-rows]').dataset.totalRows === '25');
    return page;
}

test('followers pagination, page sizes, rank filters and expandable details', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-followers-next]');
        await page.waitForFunction(() => document.querySelector('.follower-name').textContent.startsWith('User026'));
        assert.equal(await page.locator('.followers-pagination [name=page_size]').count(), 1);
        await page.selectOption('[name=page_size]', '10');
        await page.waitForFunction(() => document.querySelector('[data-followers-rows]').dataset.totalRows === '10');
        assert.equal(await page.textContent('[data-followers-page]'), 'Page 1 of 13');
        await page.selectOption('[name=page_size]', '50');
        await page.waitForFunction(() => document.querySelector('[data-followers-rows]').dataset.totalRows === '50');
        assert.equal(await page.textContent('[data-followers-page]'), 'Page 1 of 3');
        await page.selectOption('[name=page_size]', '100');
        await page.waitForFunction(() => document.querySelector('[data-followers-rows]').dataset.totalRows === '100');
        const channel = page.locator('.follower-name').first();
        assert.equal(await channel.getAttribute('href'), 'https://www.twitch.tv/user1');
        assert.equal(await channel.getAttribute('target'), '_blank');
        assert.equal(await channel.getAttribute('rel'), 'noopener noreferrer');
        assert.equal(await channel.locator('.follower-avatar').count(), 0, 'The profile picture is outside the link');
        const bounds = await channel.evaluate(node => ({link: node.getBoundingClientRect().width, text: node.firstChild.getBoundingClientRect().width, row: node.parentElement.getBoundingClientRect().width}));
        assert.ok(Math.abs(bounds.link - bounds.text) < 1);
        assert.ok(bounds.link < bounds.row, 'The link does not fill the empty row space');
        await page.locator('.follower-expand').first().click();
        assert.equal(await page.locator('.follower-expand').first().getAttribute('aria-expanded'), 'true');
        const firstRow = page.locator('[data-follower-index="0"]').first();
        await firstRow.locator('td').nth(2).click();
        assert.equal(await page.locator('.follower-expand').first().getAttribute('aria-expanded'), 'false');
        await firstRow.locator('td').nth(3).click();
        assert.equal(await page.locator('.follower-expand').first().getAttribute('aria-expanded'), 'true');
        await channel.evaluate(node => node.addEventListener('click', event => event.preventDefault(), {once: true}));
        await channel.click();
        assert.equal(await page.locator('.follower-expand').first().getAttribute('aria-expanded'), 'true', 'Name links do not toggle details');
        assert.match(await page.locator('.follower-details').first().textContent(), /Watch time2h 5m/);
        assert.match(await page.locator('.follower-details').first().textContent(), /First redeems3Check-ins12Achievements2Current points0Points earned0Points spentNot recorded/);
        assert.doesNotMatch(await page.locator('.follower-details').first().textContent(), /Last watched/);
        assert.doesNotMatch(await page.locator('thead').textContent(), /Last watched/);
        assert.equal(await page.locator('[name=sort] option[value=last_watched]').count(), 0);
        await page.click('.followers-roles-menu summary');
        await page.check('[name=rank][value=vip]');
        await page.waitForFunction(() => document.querySelectorAll('.follower-name').length === 1);
        assert.match(await page.locator('.follower-name').textContent(), /User002/);
        assert.equal(await page.locator('select[name=sort], select[name=direction]').count(), 0);
        await page.check('[name=rank][value=tier2]');
        assert.equal(await page.locator('[data-followers-role-count]').textContent(), '(2)');
        await page.locator('[name=rank][value=tier2]').press('Escape');
        assert.equal(await page.locator('.followers-roles-menu').getAttribute('open'), null);
        assert.deepEqual(new URL(await page.evaluate(() => calls.at(-1)), 'https://test.local').searchParams.getAll('rank'), ['vip', 'tier2']);
        await page.click('[data-followers-sort=messages]');
        await page.click('[data-followers-sort=messages]');
        await page.waitForFunction(() => window.calls.at(-1).includes('direction=asc'));
        assert.match(await page.evaluate(() => calls.at(-1)), /sort=messages/);
        await page.click('.followers-roles-menu summary');
        await page.check('[name=mutual]');
        assert.equal(await page.locator('.followers-roles-menu [name=mutual]').count(), 1);
        assert.equal(await page.locator('[data-followers-role-count]').textContent(), '(3)');
        await page.waitForFunction(() => calls.at(-1).includes('mutual=true'));
        assert.equal(await page.locator('[name=rank][value=vip]').isChecked(), true);
        assert.equal(await page.locator('.follower-name').count(), 1);
    } finally { await browser.close(); }
});

test('column switch reveals sortable bot statistics and restores standard columns', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        const button = page.locator('[data-followers-columns]');
        const nameWidth = await page.locator('thead th').first().evaluate(node => node.getBoundingClientRect().width);
        await page.click('[data-followers-sort=messages]');
        await page.waitForFunction(() => calls.at(-1).includes('sort=messages'));
        const callsBefore = await page.evaluate(() => calls.length);
        const originalNames = await page.locator('.follower-name').allTextContents();
        await page.evaluate(() => { window.originalFollowerNode = document.querySelector('.follower-name'); });
        await button.click();
        await page.waitForFunction(() => document.querySelector('.followers-table').dataset.columns === 'bot' && !document.querySelector('[data-followers-columns]').disabled);
        assert.deepEqual(await page.locator('thead [data-followers-sort]').evaluateAll(nodes => nodes.map(node => node.firstChild.textContent)), ['Name', '★', 'Roles', 'Messages', 'Following Since', 'Last Active', 'First redeems', 'Check-ins', 'Achievements', 'Current points', 'Points earned', 'Points spent', 'Watch time']);
        assert.ok(Math.abs(await page.locator('thead th').first().evaluate(node => node.getBoundingClientRect().width) - nameWidth) < 1, 'Name width stays fixed');
        assert.equal(await button.locator('[data-followers-columns-arrow]').textContent(), '‹');
        assert.equal(await page.evaluate(() => originalFollowerNode === document.querySelector('.follower-name')), true, 'The same row remains mounted during the slide');
        assert.equal(await page.locator('.followers-table').count(), 1, 'Only the original table exists');
        assert.equal(await page.evaluate(() => calls.length), callsBefore, 'Switching columns does not reload or reorder the list');
        assert.deepEqual(await page.locator('.follower-name').allTextContents(), originalNames);
        const cells = page.locator('[data-follower-index="0"]').first().locator('td');
        assert.deepEqual((await cells.allTextContents()).slice(8), ['3', '12', '2', '0', '0', '—', '2h 5m']);
        await page.click('[data-followers-sort=check_ins]');
        await page.waitForFunction(() => calls.at(-1).includes('sort=check_ins'));
        await page.click('[data-followers-sort=check_ins]');
        await page.waitForFunction(() => calls.at(-1).includes('direction=asc'));
        await page.locator('.follower-expand').first().click();
        assert.equal(await page.locator('.follower-details td').first().getAttribute('colspan'), '15');
        await button.click();
        await page.waitForFunction(() => document.querySelector('.followers-table').dataset.columns === 'standard' && !document.querySelector('[data-followers-columns]').disabled);
        assert.equal(await page.locator('thead th').count(), 15);
        assert.equal(await page.locator('[data-followers-column=messages]').getAttribute('aria-sort'), 'none');
        assert.equal(await page.locator('[name=sort]').inputValue(), 'check_ins');
        assert.equal(await page.locator('.follower-details td').first().getAttribute('colspan'), '15');
        await button.click();
        await page.waitForFunction(() => document.querySelector('.followers-table').dataset.columns === 'bot' && !document.querySelector('[data-followers-columns]').disabled);
        assert.equal(await page.locator('[data-followers-column=check_ins]').getAttribute('aria-sort'), 'ascending');
    } finally { await browser.close(); }
});

test('horizontal scrolling snaps to the nearest column section without requests', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        const callsBefore = await page.evaluate(() => calls.length);
        const panel = page.locator('.followers-table-wrap');
        const right = await panel.evaluate(node => Math.max(1080, node.clientWidth) * .66);
        await panel.evaluate((node, right) => { node.scrollLeft = right * .75; }, right);
        await page.waitForFunction(right => {
            const panel = document.querySelector('.followers-table-wrap');
            return panel.dataset.columns === 'bot' && Math.abs(panel.scrollLeft - right) < 1 && !document.querySelector('[data-followers-columns]').disabled;
        }, right);
        await panel.evaluate((node, right) => { node.scrollLeft = right * .25; }, right);
        await page.waitForFunction(() => {
            const panel = document.querySelector('.followers-table-wrap');
            return panel.dataset.columns === 'standard' && panel.scrollLeft === 0 && !document.querySelector('[data-followers-columns]').disabled;
        });
        assert.equal(await page.evaluate(() => calls.length), callsBefore);
    } finally { await browser.close(); }
});

test('unchanged refreshes preserve rows and search blur does not duplicate requests', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.evaluate(() => { window.originalName = document.querySelector('.follower-name'); });
        await page.click('[data-followers-refresh]');
        await page.waitForFunction(() => !document.querySelector('[data-followers]').hasAttribute('aria-busy'));
        assert.equal(await page.evaluate(() => originalName === document.querySelector('.follower-name')), true);
        await page.fill('[name=search]', 'User001');
        await page.waitForFunction(() => document.querySelectorAll('.follower-name').length === 1);
        const callsBefore = await page.evaluate(() => calls.length);
        await page.click('h2');
        await page.waitForTimeout(300);
        assert.equal(await page.evaluate(() => calls.length), callsBefore);
    } finally { await browser.close(); }
});

test('stat refreshes replace only changed rows', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.evaluate(() => {
            window.firstFollower = document.querySelector('[data-follower-index="0"] .follower-name');
            window.secondFollower = document.querySelector('[data-follower-index="1"] .follower-name');
            window.rowUpdates = {'2': {messages: 123}};
        });
        await page.click('[data-followers-refresh]');
        await page.waitForFunction(() => !document.querySelector('[data-followers]').hasAttribute('aria-busy'));
        assert.equal(await page.evaluate(() => firstFollower === document.querySelector('[data-follower-index="0"] .follower-name')), true);
        assert.equal(await page.evaluate(() => secondFollower === document.querySelector('[data-follower-index="1"] .follower-name')), false);
        assert.equal(await page.locator('[data-follower-index="1"]').first().locator('td').nth(3).textContent(), '123');
    } finally { await browser.close(); }
});

test('URL fragments restore column view and sorting, including browser history', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.click('[data-followers-sort=roles]');
        assert.equal(new URL(page.url()).hash, '#columns=standard&sort=roles&direction=desc');
        await page.click('[data-followers-sort=roles]');
        assert.equal(new URL(page.url()).hash, '#columns=standard&sort=roles&direction=asc');
        await page.locator('[data-followers-columns]').click();
        await page.waitForFunction(() => !document.querySelector('[data-followers-columns]').disabled);
        const hash = new URL(page.url()).hash;
        assert.equal(hash, '#columns=bot&sort=roles&direction=asc');
        await page.goBack();
        await page.waitForFunction(() => document.querySelector('.followers-table').dataset.columns === 'standard' && !document.querySelector('[data-followers-columns]').disabled);
        const restored = await setup(browser, 1100, hash);
        assert.equal(await restored.locator('.followers-table').getAttribute('data-columns'), 'bot');
        assert.equal(await restored.locator('[data-followers-column=roles]').getAttribute('aria-sort'), 'ascending');
        assert.match(await restored.evaluate(() => calls[0]), /sort=roles&direction=asc/);
        const invalid = await setup(browser, 1100, '#columns=bad&sort=bad&direction=bad');
        assert.equal(await invalid.locator('.followers-table').getAttribute('data-columns'), 'standard');
        assert.equal(await invalid.locator('[data-followers-column=followed_at]').getAttribute('aria-sort'), 'descending');
    } finally { await browser.close(); }
});

test('followers search, empty states and permission errors use safe text', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.fill('[name=search]', 'User128');
        await page.waitForFunction(() => document.querySelectorAll('.follower-name').length === 1);
        assert.match(await page.locator('.follower-name').textContent(), /user128/i);
        await page.fill('[name=search]', '<img src=x onerror=alert(1)>');
        await page.waitForFunction(() => document.querySelector('[data-followers-rows]').textContent.includes('No followers'));
        assert.equal(await page.locator('[data-followers-rows] img').count(), 0);
        await page.fill('[name=search]', 'error');
        await page.waitForFunction(() => document.querySelector('[data-followers-warning]').textContent === 'Reconnect Twitch.');
        assert.equal(await page.locator('[data-followers-refresh]').isEnabled(), true);
    } finally { await browser.close(); }
});

test('follower names use username alone or DisplayName (username), without a second login line', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        assert.equal(await page.locator('[data-follower-index="8"] .follower-person-text').textContent(), 'user9', 'Case-only display differences do not duplicate the username');
        assert.equal(await page.locator('[data-follower-index="9"] .follower-person-text').textContent(), 'Friendly Cat (user10)');
        assert.equal(await page.locator('.follower-login').count(), 0);
    } finally { await browser.close(); }
});

test('follow date shows only the date with the full local datetime on hover', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        const values = await page.locator('.follower-name').first().evaluate(node => {
            const cell = node.closest('tr').cells[4], date = new Date('2026-10-01T00:00:00Z');
            return {display: cell.textContent, title: cell.title, expectedDisplay: date.toLocaleDateString(), expectedTitle: date.toLocaleString()};
        });
        assert.equal(values.display, values.expectedDisplay);
        assert.equal(values.title.split('\n')[0], values.expectedTitle);
        assert.match(values.title, /\nFollowing for (?:[\d,]+ days?|less than a day)$/);
        assert.notEqual(values.display, values.title);
        const lastSeen = await page.locator('[data-follower-index="1"] .follower-name').evaluate(node => {
            const cell = node.closest('tr').cells[5], date = new Date('2026-10-26T01:00:00Z');
            return {display: cell.textContent, title: cell.title, expectedDisplay: date.toLocaleDateString(), expectedTitle: date.toLocaleString()};
        });
        assert.equal(lastSeen.display, lastSeen.expectedDisplay);
        assert.equal(lastSeen.title, lastSeen.expectedTitle);
    } finally { await browser.close(); }
});

test('headers toggle sorting including roles, and non-name columns are centered', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        const headerOrder = await page.locator('thead th').evaluateAll(nodes => nodes.map(node => node.firstChild.textContent.trim()));
        assert.deepEqual(headerOrder, ['Name↕', '★↕', 'Roles↕', 'Messages↕', 'Following Since▼', 'Last Active↕', '›', '‹', 'First redeems↕', 'Check-ins↕', 'Achievements↕', 'Current points↕', 'Points earned↕', 'Points spent↕', 'Watch time↕']);
        await page.click('[data-followers-next]');
        await page.waitForFunction(() => document.querySelector('[data-followers-page]').textContent.startsWith('Page 2'));
        await page.click('[data-followers-sort=messages]');
        await page.waitForFunction(() => calls.at(-1).includes('sort=messages'));
        let params = new URL(await page.evaluate(() => calls.at(-1)), 'https://test.local').searchParams;
        assert.equal(params.get('direction'), 'desc'); assert.equal(params.get('page'), '1');
        assert.equal(await page.locator('[data-followers-column=messages]').getAttribute('aria-sort'), 'descending');
        await page.click('[data-followers-sort=messages]');
        await page.waitForFunction(() => calls.at(-1).includes('direction=asc'));
        assert.equal(await page.locator('[data-followers-column=messages]').getAttribute('aria-sort'), 'ascending');
        await page.click('[data-followers-sort=name]');
        await page.waitForFunction(() => calls.at(-1).includes('sort=name'));
        assert.equal(await page.locator('[data-followers-column=name]').getAttribute('aria-sort'), 'ascending');
        await page.click('[data-followers-sort=roles]');
        await page.waitForFunction(() => calls.at(-1).includes('sort=roles'));
        assert.equal(await page.locator('[data-followers-column=roles]').getAttribute('aria-sort'), 'descending');
        await page.click('[data-followers-sort=roles]');
        await page.waitForFunction(() => calls.at(-1).includes('direction=asc'));
        assert.equal(await page.locator('[data-followers-column=roles]').getAttribute('aria-sort'), 'ascending');
        assert.equal(await page.locator('.followers-role-filter label').nth(3).textContent(), 'Mutual followers');
        assert.ok(await page.locator('thead th').evaluateAll(nodes => nodes.every(node => getComputedStyle(node).textAlign === 'center')));
        assert.ok(await page.locator('.follower-number').evaluateAll(nodes => nodes.every(node => getComputedStyle(node).textAlign === 'center')));
        assert.ok(await page.locator('tr:not(.follower-details) > td .follower-roles').evaluateAll(nodes => nodes.every(node => getComputedStyle(node).justifyContent === 'center')));
        assert.ok(await page.locator('.follower-date').evaluateAll(nodes => nodes.every(node => getComputedStyle(node).textAlign === 'center')));
        assert.equal(await page.locator('.follower-date.follower-empty').count(), 1);
        assert.ok(await page.locator('.follower-empty').evaluateAll(nodes => nodes.every(node => getComputedStyle(node).textAlign === 'center')));
        assert.ok(await page.locator('.follower-roles.is-empty').evaluateAll(nodes => nodes.every(node => getComputedStyle(node).justifyContent === 'center')));
        const second = page.locator('[data-followers-rows] > tr:not(.follower-details)').nth(1);
        assert.deepEqual(await second.locator('.follower-role-tag').allTextContents(), ['VIP', 'Sub tier 2']);
        await second.locator('.follower-expand').click();
        assert.deepEqual(await page.locator('.follower-details').nth(1).locator('.follower-role-tag').allTextContents(), ['VIP', 'Sub tier 2']);
        for (const sort of ['followed_at', 'messages', 'last_seen']) {
            await page.click(`[data-followers-sort=${sort}]`);
            await page.waitForFunction(sort => new URL(calls.at(-1), location.href).searchParams.get('sort') === sort, sort);
            assert.equal(await page.locator(`[data-followers-column=${sort}]`).getAttribute('aria-sort'), 'descending');
        }
    } finally { await browser.close(); }
});

test('followers table retains horizontal scrolling on mobile and keeps controls visible', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser, 375);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        const panel = page.locator('.followers-table-wrap');
        assert.ok(await panel.evaluate(node => node.scrollWidth > node.clientWidth));
        const controls = await page.locator('.followers-controls :is(input,select)').evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().right));
        assert.ok(controls.every(right => right <= 375));
    } finally { await browser.close(); }
});

test('table height expands with row count without an internal vertical scrollbar', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        const panel = page.locator('.followers-table-wrap');
        await page.selectOption('[name=page_size]', '10');
        await page.waitForFunction(() => document.querySelector('[data-followers-rows]').dataset.totalRows === '10');
        await page.waitForTimeout(100);
        const ten = await panel.evaluate(node => node.getBoundingClientRect().height);
        await page.selectOption('[name=page_size]', '100');
        await page.waitForFunction(() => document.querySelector('[data-followers-rows]').dataset.totalRows === '100');
        await page.waitForTimeout(100);
        const size = await panel.evaluate(node => ({height: node.getBoundingClientRect().height, content: node.scrollHeight, viewport: node.clientHeight, max: getComputedStyle(node).maxHeight}));
        assert.ok(size.height > ten * 5, JSON.stringify({ten, ...size}));
        assert.ok(size.content <= size.viewport + 1, 'The table has no internal vertical overflow');
        assert.equal(size.max, 'none');
        assert.ok(await page.locator('.follower-name').count() < 30, 'Page scrolling still virtualizes large pages');
    } finally { await browser.close(); }
});

test('fixed column grid does not shift when sorting, filtering or expanding rows', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser, 1440);
        const widths = () => page.locator('thead th').evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().width));
        const expected = await widths();
        const stable = async () => {
            const actual = await widths();
            actual.forEach((width, index) => assert.ok(Math.abs(width - expected[index]) < .5, `Column ${index} stays fixed: ${width} vs ${expected[index]}`));
        };
        await page.click('[data-followers-sort=messages]');
        await page.waitForFunction(() => calls.at(-1).includes('sort=messages'));
        await stable();
        await page.locator('.follower-expand').first().click(); await stable();
        await page.click('.followers-roles-menu summary');
        await page.check('[name=rank][value=vip]');
        await page.waitForFunction(() => document.querySelectorAll('.follower-name').length === 1);
        await stable();
        await page.fill('[name=search]', 'no-match');
        await page.waitForFunction(() => document.querySelector('[data-followers-rows]').textContent.includes('No followers'));
        await stable();
        const tableWidth = await page.locator('.followers-table-wrap').evaluate(node => Math.max(1080, node.clientWidth));
        assert.ok(Math.abs(expected[0] / tableWidth - .28) < .01);
    } finally { await browser.close(); }
});

test('followers virtualize rows, lazy-load avatars, and preserve expanded rows after scrolling', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.selectOption('[name=page_size]', '100');
        await page.waitForFunction(() => document.querySelector('[data-followers-rows]').dataset.totalRows === '100');
        await page.waitForFunction(() => profileCalls.length > 0);
        assert.ok(await page.locator('.follower-name').count() < 30, 'Only visible rows plus overscan are mounted');
        assert.ok(await page.locator('.follower-spacer').count() > 0);
        assert.ok(await page.locator('.follower-avatar img').evaluateAll(nodes => nodes.every(node => node.loading === 'lazy' && node.width === 34 && node.height === 34)));
        const requested = await page.evaluate(() => profileCalls.flatMap(url => new URL(url, location.href).searchParams.get('ids').split(',')));
        assert.ok(new Set(requested).size < 35, 'Pictures are not fetched for the entire page');
        await page.locator('.follower-expand').first().click();
        await page.waitForTimeout(100);
        await page.locator('[name=page_size]').focus();
        const panel = page.locator('.followers-table-wrap');
        const callsBefore = await page.evaluate(() => calls.length);
        await panel.evaluate(node => node.scrollIntoView({block: 'end'}));
        await page.waitForFunction(() => [...document.querySelectorAll('.follower-name')].some(node => node.textContent.toLowerCase().startsWith('user100')));
        assert.ok(await page.locator('.follower-name').count() < 30);
        assert.equal(await page.locator('#follower-1').count(), 0);
        assert.equal(await page.evaluate(() => calls.length), callsBefore, 'Scrolling does not reload the directory');
        await panel.evaluate(node => node.scrollIntoView({block: 'start'}));
        await page.waitForFunction(() => document.querySelector('.follower-name')?.textContent.startsWith('User001'));
        assert.equal(await page.locator('.follower-expand').first().getAttribute('aria-expanded'), 'true');
        assert.equal(await page.locator('#follower-1').isVisible(), true);
        const last = page.locator('.follower-name').last();
        const lastIndex = await last.evaluate(node => Number(node.closest('[data-follower-index]').dataset.followerIndex));
        await last.focus(); await page.keyboard.press('Tab'); await page.keyboard.press('Tab');
        assert.equal(await page.evaluate(() => Number(document.activeElement.closest('[data-follower-index]').dataset.followerIndex)), lastIndex + 1, 'Keyboard navigation reaches unmounted rows');
    } finally { await browser.close(); }
});

test('raid favorites stay pinned, share dashboard storage and use a sliding removal confirmation', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        const star = page.locator('.follower-favorite').first();
        const before = await star.boundingBox();
        const initialCalls = await page.evaluate(() => calls.length);
        await star.click();
        await page.waitForFunction(() => document.querySelector('.follower-favorite').getAttribute('aria-pressed') === 'true');
        assert.deepEqual(await page.evaluate(() => JSON.parse(localStorage.getItem('ratsboombot:raid-favorites:1'))), ['1']);
        assert.equal(await page.evaluate(() => calls.length), initialCalls, 'Favoriting does not reload an unfiltered list');
        await page.locator('[data-followers-columns]').click();
        await page.waitForFunction(() => !document.querySelector('[data-followers-columns]').disabled);
        const after = await star.boundingBox();
        assert.ok(Math.abs(before.x - after.x) < 1, 'Favorite stars remain pinned beside the names');
        await page.click('.followers-roles-menu summary');
        await page.check('[name=raid_favorites]');
        await page.waitForFunction(() => document.querySelectorAll('.follower-name').length === 1);
        await page.click('.followers-roles-menu summary');
        const callsBefore = await page.evaluate(() => calls.length);
        await star.click();
        assert.equal(await page.locator('.follower-favorite-action.is-confirming').count(), 1);
        const remove = page.locator('.follower-favorite-remove').first();
        assert.equal(await remove.isEnabled(), true);
        await page.waitForTimeout(200);
        const fit = await page.locator('.follower-favorite-action.is-confirming').evaluate(action => {
            const bounds = action.getBoundingClientRect(), range = document.createRange();
            range.selectNodeContents(action.querySelector('.follower-favorite'));
            const star = range.getBoundingClientRect(), remove = action.querySelector('.follower-favorite-remove').getBoundingClientRect();
            return star.left >= bounds.left && star.right <= bounds.right && remove.left >= bounds.left && remove.right <= bounds.right;
        });
        assert.equal(fit, true, 'Both the full star and remove button fit inside the confirmation');
        await page.click('h2');
        assert.equal(await page.locator('.follower-favorite-action.is-confirming').count(), 0);
        assert.equal(await star.getAttribute('aria-pressed'), 'true');
        assert.equal(await page.evaluate(() => calls.length), callsBefore);
        await star.click();
        await remove.click();
        await page.waitForFunction(() => document.querySelector('[data-followers-rows]').textContent.includes('No followers'));
        assert.deepEqual(await page.evaluate(() => JSON.parse(localStorage.getItem('ratsboombot:raid-favorites:1'))), []);
    } finally { await browser.close(); }
});

test('details build on demand and horizontal slides do not rebuild rows', {skip}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await setup(browser);
        await page.waitForTimeout(150);
        assert.equal(await page.locator('.follower-detail-content').count(), 0);
        await page.evaluate(() => {
            window.rowMutations = 0;
            window.rowMutationObserver = new MutationObserver(changes => { rowMutations += changes.length; });
            rowMutationObserver.observe(document.querySelector('[data-followers-rows]'), {childList: true});
        });
        await page.locator('[data-followers-columns]').click();
        await page.waitForFunction(() => !document.querySelector('[data-followers-columns]').disabled);
        assert.equal(await page.evaluate(() => rowMutations), 0);
        await page.evaluate(() => { rowMutationObserver.disconnect(); document.querySelector('.followers-table-wrap').scrollLeft = 200; });
        await page.locator('.follower-expand').first().click();
        await page.waitForTimeout(100);
        assert.equal(await page.locator('.follower-detail-content').count(), 1);
        assert.equal(await page.locator('.followers-table-wrap').evaluate(node => node.scrollLeft), 200, 'Expanding a row does not reset horizontal scrolling');
    } finally { await browser.close(); }
});
