const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

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
