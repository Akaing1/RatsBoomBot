const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('raid controls stay side by side with the countdown at the end', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const template = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
        const start = template.indexOf('<div class="dashboard-pending-raid"');
        const end = template.indexOf('<div class="dashboard-raid-progress"', start);
        const markup = (template.slice(start, end) + '</div>').replace(/\{%[\s\S]*?%\}/g, '');
        const page = await browser.newPage({viewport: {width: 700, height: 800}});
        await page.route('**/*', route => route.abort());
        await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}</style>${markup}`);
        for (const width of [320, 500]) {
            const bounds = await page.evaluate(width => {
                const banner = document.querySelector('[data-pending-raid]');
                banner.hidden = false; banner.style.width = `${width}px`;
                const follow = document.querySelector('.dashboard-follow-raid').getBoundingClientRect();
                const cancel = document.querySelector('[data-pending-raid-cancel]').getBoundingClientRect();
                const timer = document.querySelector('[data-pending-raid-countdown]').getBoundingClientRect();
                return {follow: {right: follow.right, center: follow.top + follow.height / 2},
                    cancel: {left: cancel.left, right: cancel.right, center: cancel.top + cancel.height / 2},
                    timer: {left: timer.left, right: timer.right}, bannerRight: banner.getBoundingClientRect().right};
            }, width);
            assert.equal(bounds.follow.center, bounds.cancel.center);
            assert.ok(bounds.follow.right < bounds.cancel.left);
            assert.ok(bounds.cancel.right < bounds.timer.left);
            assert.ok(bounds.timer.right <= bounds.bannerRight);
        }
    } finally {
        await browser.close();
    }
});

test('raid animation conforms its border to the chat banner without stretching its content', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage({viewport: {width: 1200, height: 800}});
        await page.route('**/*', route => route.abort());
        await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}</style>
            <div class="dashboard-pending-raid" data-pending-raid hidden style="position:fixed;left:650px;top:80px;width:320px;height:90px">
                <img data-pending-raid-avatar hidden><a data-pending-raid-channel></a><span data-pending-raid-text></span>
                <input type="checkbox" data-pending-raid-follow><button data-pending-raid-cancel>Cancel</button>
            </div>`);
        await page.evaluate(() => { window.fetch = async () => ({ok: true, json: async () => ({raid: null})}); });
        await page.addScriptTag({content: fs.readFileSync('web/static/js/dashboard-raid-status.js', 'utf8')});
        await page.evaluate(() => {
            const flyer = document.createElement('article');
            flyer.className = 'raid-browser-channel';
            flyer.textContent = 'Channel preview';
            document.dispatchEvent(new CustomEvent('dashboard-raid-started', {detail: {
                raid: {login: 'target', display_name: 'Target', target_id: '2', expires_at: Date.now() / 1000 + 90},
                flyer, sourceRect: {left: 100, top: 100, width: 800, height: 500}
            }}));
        });
        await page.waitForSelector('.raid-browser-flyer');
        const geometry = await page.evaluate(() => {
            const frame = document.querySelector('.raid-browser-flyer');
            const animation = frame.getAnimations()[0];
            animation.pause(); animation.currentTime = 600;
            const banner = document.querySelector('[data-pending-raid]');
            const actual = frame.getBoundingClientRect(), expected = banner.getBoundingClientRect();
            const style = getComputedStyle(frame), targetStyle = getComputedStyle(banner);
            const content = frame.firstElementChild;
            const transform = new DOMMatrix(getComputedStyle(content).transform);
            return {actual: {x: actual.x, y: actual.y, width: actual.width, height: actual.height},
                expected: {x: expected.x, y: expected.y, width: expected.width, height: expected.height},
                radius: style.borderRadius, targetRadius: targetStyle.borderRadius,
                color: style.borderColor, targetColor: targetStyle.borderColor,
                border: style.borderWidth, targetBorder: targetStyle.borderWidth, scaleX: transform.a, scaleY: transform.d};
        });
        for (const key of ['x', 'y', 'width', 'height']) assert.ok(Math.abs(geometry.actual[key] - geometry.expected[key]) < 1, key);
        assert.equal(geometry.radius, geometry.targetRadius);
        assert.equal(geometry.color, geometry.targetColor);
        assert.equal(geometry.border, geometry.targetBorder);
        assert.equal(geometry.scaleX, geometry.scaleY);
    } finally {
        await browser.close();
    }
});
