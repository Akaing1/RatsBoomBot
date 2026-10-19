const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('vertical preview centers the video within a full-width black row of matching height', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        for (const width of [750, 650, 514]) {
            const page = await browser.newPage({viewport: {width, height: 950}});
            const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
            const markup = '<dialog id="dashboard-raid-preview"' + template.split('<dialog id="dashboard-raid-preview"')[1].split('</dialog>')[0] + '</dialog>';
            await page.route('**/*', route => route.abort());
            await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}</style>${markup}`);
            await page.evaluate(() => document.querySelector('dialog').showModal());
            const layout = await page.evaluate(() => {
                const row = document.querySelector('.raid-preview-video-row'), video = row.firstElementChild;
                const a = row.getBoundingClientRect(), b = video.getBoundingClientRect();
                const main = document.querySelector('.raid-preview-main');
                return {center: a.x + a.width / 2 - b.x - b.width / 2, height: a.height - b.height,
                    width: a.width - main.clientWidth, background: getComputedStyle(row).backgroundColor,
                    videoWidth: b.width, videoHeight: b.height};
            });
            assert.ok(Math.abs(layout.center) < 1);
            assert.ok(Math.abs(layout.height) < 1);
            assert.ok(Math.abs(layout.width) < 1);
            assert.equal(layout.background, 'rgb(0, 0, 0)');
            assert.ok(layout.videoWidth >= 400 && layout.videoHeight >= 300);
            await page.close();
        }
    } finally { await browser.close(); }
});

test('Search label is vertically centered with the collection tabs', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
        const markup = '<dialog id="dashboard-raid-browser"' + template.split('<dialog id="dashboard-raid-browser"')[1].split('</dialog>')[0] + '</dialog>';
        for (const width of [1500, 1100, 800, 760]) {
            const page = await browser.newPage({viewport: {width, height: 900}});
            await page.route('**/*', route => route.abort());
            await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}</style>${markup}`);
            await page.evaluate(() => document.querySelector('dialog').showModal());
            const offset = await page.evaluate(() => {
                const label = document.querySelector('.raid-browser-search-heading').getBoundingClientRect();
                const tab = document.querySelector('[data-raid-browser-tab="browse"]').getBoundingClientRect();
                return label.top + label.height / 2 - tab.top - tab.height / 2;
            });
            assert.ok(Math.abs(offset) <= 1, `Search/tab center offset at ${width}px: ${offset}`);
            await page.close();
        }
    } finally { await browser.close(); }
});
let PNG;
try { ({PNG} = require('pngjs')); } catch (_) {}

test('selected tab covers the panel border without a horizontal seam', {skip: !chromium || !PNG || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({viewport: {width: 1200, height: 800}, reducedMotion: 'reduce'});
        const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
        const markup = '<dialog id="dashboard-raid-browser"' + template.split('<dialog id="dashboard-raid-browser"')[1].split('</dialog>')[0] + '</dialog>';
        await page.route('**/*', route => route.abort());
        await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}</style>${markup}`);
        await page.evaluate(() => document.querySelector('dialog').showModal());
        const sample = await page.evaluate(() => {
            const tabs = document.querySelector('[data-raid-collection-tabs]');
            const selected = tabs.querySelector('[aria-pressed="true"]');
            const rect = selected.getBoundingClientRect(), parent = tabs.getBoundingClientRect();
            for (const [key, value] of Object.entries({x: rect.left - parent.left, y: rect.top - parent.top,
                width: rect.width, height: rect.height + 1})) tabs.style.setProperty(`--raid-tab-${key}`, `${value}px`);
            tabs.classList.add('has-tab-indicator');
            const panel = document.querySelector('.raid-browser-results-shell');
            return {x: Math.round(rect.left + rect.width / 2), y: Math.ceil(panel.getBoundingClientRect().top),
                color: getComputedStyle(panel).backgroundColor.match(/\d+/g).slice(0, 3).map(Number)};
        });
        const pixels = PNG.sync.read(await page.screenshot());
        for (const y of [sample.y, sample.y + 1]) {
            const offset = (y * pixels.width + sample.x) * 4;
            assert.deepEqual([...pixels.data.subarray(offset, offset + 3)], sample.color, 'Panel border must not cross the selected tab');
        }
    } finally { await browser.close(); }
});

test('favorite star slides into the hidden menu space and back on hover without moving cards', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({viewport: {width: 900, height: 700}});
        await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}</style>
            <div class="raid-browser-dialog" style="width:400px;margin:100px">
                <article class="raid-browser-channel is-favorite" style="height:200px">
                    <button class="raid-browser-pin" aria-pressed="true">★</button>
                    <button class="raid-browser-more" aria-expanded="false">⋮</button>
                </article>
            </div>`);
        const star = page.locator('.raid-browser-pin');
        const card = page.locator('.raid-browser-channel');
        const idle = await star.boundingBox(), before = await card.boundingBox();
        await page.mouse.move(before.x + 50, before.y + 80);
        await page.waitForFunction(() => getComputedStyle(document.querySelector('.raid-browser-pin')).transform === 'matrix(1, 0, 0, 1, 0, 0)');
        const hovered = await star.boundingBox();
        assert.ok(Math.abs(idle.x - hovered.x - 26) < 1);
        assert.deepEqual(await card.boundingBox(), before);
        await page.mouse.move(0, 0);
        await page.waitForFunction(() => getComputedStyle(document.querySelector('.raid-browser-pin')).transform === 'matrix(1, 0, 0, 1, 26, 0)');
        await page.emulateMedia({reducedMotion: 'reduce'});
        assert.equal(await star.evaluate(node => getComputedStyle(node).transitionDuration), '0s');
        await page.evaluate(() => document.querySelector('.raid-browser-dialog').classList.add('is-list-view'));
        assert.equal(await star.evaluate(node => getComputedStyle(node).transform), 'none');
    } finally { await browser.close(); }
});

test('cards fill the reclaimed footer space and search-side status does not resize them', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
        const markup = '<dialog id="dashboard-raid-browser"' + template.split('<dialog id="dashboard-raid-browser"')[1].split('</dialog>')[0] + '</dialog>';
        for (const width of [1100, 390]) {
            const page = await browser.newPage({viewport: {width, height: 900}});
            await page.route('**/*', route => route.abort());
            await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}</style>${markup}`);
            await page.evaluate(() => document.querySelector('dialog').showModal());
            const measure = () => page.evaluate(() => {
                const dialog = document.querySelector('dialog');
                const style = getComputedStyle(dialog);
                const cards = document.querySelector('.raid-browser-results-shell').getBoundingClientRect();
                return {height: cards.height, bottom: cards.bottom,
                    availableBottom: dialog.getBoundingClientRect().bottom - parseFloat(style.paddingBottom) - parseFloat(style.borderBottomWidth)};
            });
            const before = await measure();
            assert.ok(Math.abs(before.bottom - before.availableBottom) < 1, `Unused card height at ${width}px: ${JSON.stringify(before)}`);
            await page.evaluate(() => {
                document.querySelector('dialog').classList.add('is-filters-open');
                const status = document.querySelector('[data-raid-browser-status]');
                status.textContent = 'Could not load more channels. Existing results are still available.';
                status.classList.add('error');
            });
            const after = await measure();
            assert.equal(after.height, before.height, `Status must not reduce card height at ${width}px`);
            assert.equal(after.bottom, before.bottom);
            await page.close();
        }
    } finally {
        await browser.close();
    }
});

test('filter focus outlines fit inside desktop and mobile scroll containers', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
        const form = '<form id="raid-browser-filters"' + template.split('<form id="raid-browser-filters"')[1].split('</form>')[0] + '</form>';
        for (const width of [1100, 390]) {
            const page = await browser.newPage({viewport: {width, height: 800}});
            await page.route('**/*', route => route.abort());
            await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}
                .raid-browser-dialog { display:block; position:relative; width:100%; height:700px; }
                .raid-browser-filters { display:flex; position:relative; width:320px; height:500px; top:auto; right:auto; left:auto; }
                </style><div class="raid-browser-dialog is-filters-open">${form}</div>`);
            const clipped = await page.evaluate(() => {
                // Exercise the team control in its visible Stream team state too.
                document.querySelector('[data-raid-team-filter]').hidden = false;
                const failures = [];
                for (const input of document.querySelectorAll('.raid-browser-filters input:not([type="hidden"]), .raid-browser-filters select')) {
                    input.focus();
                    const bounds = input.getBoundingClientRect();
                    for (let parent = input.parentElement; parent; parent = parent.parentElement) {
                        if (!/auto|hidden|clip|scroll/.test(getComputedStyle(parent).overflowX)) continue;
                        const clip = parent.getBoundingClientRect();
                        if (bounds.left - 3 < clip.left - .5 || bounds.right + 3 > clip.right + .5) {
                            failures.push({field: input.name || input.placeholder, container: parent.className});
                        }
                    }
                }
                return failures;
            });
            assert.deepEqual(clipped, [], `Clipped focus outlines at ${width}px`);
            await page.close();
        }
    } finally {
        await browser.close();
    }
});

test('raid tabs use spare header space before overflowing', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({viewport: {width: 1200, height: 800}, reducedMotion: 'reduce'});
        await page.route('**/*', route => route.abort());
        await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}</style>
            <div class="raid-browser-results-toolbar" style="width:1000px">
                <div class="raid-browser-heading-group"><h3>Raid browser</h3>
                    <div class="raid-browser-tab-scroll"><div class="raid-browser-tabs has-tab-indicator" data-raid-collection-tabs>
                        <button>Browse</button><button>Favorites</button><button aria-pressed="true">Stream team</button>
                    </div></div>
                </div>
                <div class="raid-browser-result-controls" style="width:200px;height:38px"></div>
            </div>`);
        async function measure(width) {
            return page.evaluate(width => {
                const toolbar = document.querySelector('.raid-browser-results-toolbar');
                toolbar.style.width = `${width}px`;
                const tabs = toolbar.querySelector('.raid-browser-tabs');
                const selected = tabs.querySelector('[aria-pressed="true"]');
                for (const [key, value] of Object.entries({x: selected.offsetLeft, y: selected.offsetTop,
                    width: selected.offsetWidth, height: selected.offsetHeight})) {
                    tabs.style.setProperty(`--raid-tab-${key}`, `${value}px`);
                }
                const scroller = toolbar.querySelector('.raid-browser-tab-scroll');
                const heading = toolbar.querySelector('h3').getBoundingClientRect();
                const controls = toolbar.querySelector('.raid-browser-result-controls').getBoundingClientRect();
                const bounds = scroller.getBoundingClientRect();
                return {width: scroller.clientWidth, content: scroller.scrollWidth, headingWidth: heading.width,
                    tabRight: bounds.right, controlsLeft: controls.left, headingTop: heading.top, controlsTop: controls.top};
            }, width);
        }
        const wide = await measure(1000);
        assert.ok(wide.content <= wide.width + 1, `Unnecessary tab overflow: ${JSON.stringify(wide)}`);
        const narrow = await measure(500);
        assert.ok(narrow.content > narrow.width + 1, 'Tabs must still scroll when space actually runs out');
        assert.equal(narrow.headingWidth, wide.headingWidth, 'The heading must not shrink');
        assert.ok(narrow.tabRight <= narrow.controlsLeft + 12, 'Tabs must not overlap the right controls');
    } finally {
        await browser.close();
    }
});

test('returning from a mouse-opened preview does not leave the card expanded', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({viewport: {width: 1200, height: 800}, reducedMotion: 'reduce'});
        await page.route('**/*', route => route.abort());
        await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}</style>
            <div class="raid-browser-dialog" style="width:800px;height:auto;margin:0">
                <article class="raid-browser-channel" style="--raid-browser-row-height:180px;width:360px">
                    <button class="raid-browser-thumbnail" style="height:60px;aspect-ratio:auto">Preview</button>
                    <p class="raid-browser-stream-title">${'Long channel title '.repeat(40)}</p>
                    <div class="raid-browser-channel-footer"><div class="raid-browser-tags"><span>Art</span></div>
                        <button class="raid-browser-start-raid">Raid</button></div>
                </article>
            </div>
            <dialog id="preview"><button id="back">Back</button></dialog>`);
        await page.evaluate(() => {
            const source = document.querySelector('.raid-browser-thumbnail');
            const preview = document.querySelector('#preview');
            source.addEventListener('click', () => preview.showModal());
            document.querySelector('#back').addEventListener('click', () => preview.close());
            preview.addEventListener('close', () => source.focus({preventScroll: true}));
        });
        const card = page.locator('.raid-browser-channel');
        await page.mouse.move(1100, 700);
        const collapsed = await card.evaluate(node => node.getBoundingClientRect().height);
        await page.locator('.raid-browser-thumbnail').click();
        await page.locator('#back').click();
        await page.mouse.move(1100, 700);
        await page.waitForFunction(() => !document.querySelector('#preview').open
            && document.activeElement.matches('.raid-browser-thumbnail'));
        assert.equal(await card.evaluate(node => node.getBoundingClientRect().height), collapsed);
        await page.keyboard.press('Tab');
        assert.ok(await card.evaluate(node => node.getBoundingClientRect().height) > collapsed,
            'Keyboard focus must still expand the card');
        await page.keyboard.press('Shift+Tab');
        await page.keyboard.press('Enter');
        await page.keyboard.press('Escape');
        await page.waitForFunction(() => !document.querySelector('#preview').open);
        assert.ok(await card.evaluate(node => node.getBoundingClientRect().height) > collapsed,
            'Returning to the thumbnail with the keyboard must preserve keyboard expansion');
    } finally {
        await browser.close();
    }
});
