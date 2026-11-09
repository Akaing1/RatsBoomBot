const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('GIF artwork fits narrow chat panels and remains bounded on desktop', {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
    const browser = await chromium.launch({executablePath, headless: true});
    try {
        const page = await browser.newPage();
        await page.route('https://media.giphy.com/**', route => route.fulfill({contentType: 'image/svg+xml',
            body: '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600"><rect width="800" height="600" fill="purple"/></svg>'}));
        for (const width of [320, 1200]) {
            await page.setViewportSize({width, height: 700});
            await page.setContent(`<style>${fs.readFileSync('web/static/css/style.css', 'utf8')}body{padding:16px}#shell{width:100%;max-width:400px}#feed{height:400px;overflow:auto}</style><div id="shell"><div id="feed"></div></div>`);
            await page.addScriptTag({content: fs.readFileSync('web/static/js/live-chat-feed.js', 'utf8')});
            await page.evaluate(() => {
                window.testFeed = window.createTwitchPreviewFeed(document.querySelector('#feed'));
                window.testFeed.receive({type: 'message', message: {id: 'gif', platform: 'twitch', username: 'tester',
                    segments: [{type: 'gif', text: 'GIF', url: 'https://media.giphy.com/media/example/giphy.gif?cid=original'}]}});
            });
            await page.waitForFunction(() => document.querySelector('.live-chat-gif')?.naturalWidth > 0);
            const fits = await page.locator('.live-chat-gif').evaluate(image => {
                const bounds = image.getBoundingClientRect(), body = image.parentElement.getBoundingClientRect();
                return bounds.width <= 280 && bounds.height <= 180 && bounds.left >= body.left && bounds.right <= body.right + 1;
            });
            assert.equal(fits, true);
            await page.evaluate(() => window.testFeed.destroy());
        }
    } finally { await browser.close(); }
});

test('timestamps reserve a compact gutter only when present, not space for the hover buttons', () => {
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    const content = styles.split('.live-chat-message-content {')[1].split('}')[0];
    assert.ok(!content.includes('padding-right'));
    assert.match(styles, /\.live-chat-message-content:has\(> \.live-chat-time\) \{ padding-right: 48px;/);
});
const source = fs.readFileSync('web/static/js/live-chat-feed.js', 'utf8');

test('event notices share the muted appearance of bot messages in both chats', () => {
    const styles = fs.readFileSync('web/static/css/style.css', 'utf8');
    assert.match(styles, /\.live-chat-message\.is-bot:not\(\.is-deleted\) \.live-chat-message-content \{ filter: grayscale\(\.55\); opacity: \.72; \}/);
    assert.ok(!styles.includes('.live-chat-message.has-notice'));
});

class Element {
    constructor(tag = 'div') {
        this.tagName = tag; this.children = []; this.dataset = {}; this.style = {}; this.handlers = {};
        this.classes = new Set(); this.clientHeight = 100; this.scrollTop = 0;
        this.classList = {add: name => this.classes.add(name), contains: name => this.classes.has(name),
            toggle: (name, on) => on ? this.classes.add(name) : this.classes.delete(name)};
    }
    set className(value) { this.classes = new Set(value.split(/\s+/)); }
    get className() { return [...this.classes].join(' '); }
    set textContent(value) { this._text = String(value); this.children = []; }
    get textContent() { return (this._text || '') + this.children.map(child => child.textContent || '').join(''); }
    get scrollHeight() { return this.children.length * 20; }
    appendChild(child) { child.parentNode = this; this.children.push(child); }
    append(...children) { children.forEach(child => this.appendChild(child)); }
    prepend(child) { child.parentNode = this; this.children.unshift(child); }
    remove() {
        if (this.parentNode) this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1);
        this.parentNode = null;
    }
    replaceWith(child) { const parent = this.parentNode, index = parent.children.indexOf(this); parent.children[index] = child; child.parentNode = parent; this.parentNode = null; }
    setAttribute(name, value) { this[name] = value; }
    addEventListener(name, callback) { this.handlers[name] = callback; }
    removeEventListener(name) { delete this.handlers[name]; }
    querySelectorAll(selector) {
        const result = [];
        for (const child of this.children) {
            const matches = selector === 'img' ? child.tagName === 'img'
                : selector === '.live-chat-message:not(.is-activity-removing)'
                    ? child.classes.has('live-chat-message') && !child.classes.has('is-activity-removing')
                    : selector.startsWith('.') && child.classes.has(selector.slice(1));
            if (matches) result.push(child);
            result.push(...child.querySelectorAll(selector));
        }
        return result;
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0]; }
}

function setup(debug = false) {
    const frames = new Map(), observers = []; let nextFrame = 0;
    const documentHandlers = {};
    class ResizeObserver {
        constructor(callback) { this.callback = callback; this.observed = []; observers.push(this); }
        observe(row) { this.observed.push(row); }
        disconnect() { this.disconnected = true; }
    }
    const window = {ResizeObserver,
        requestAnimationFrame(callback) { frames.set(++nextFrame, callback); return nextFrame; },
        cancelAnimationFrame(id) { frames.delete(id); }};
    if (debug) window.dashboardChatDebug = {};
    vm.runInNewContext(source, {window, ResizeObserver,
        document: {querySelectorAll: () => [], createElement: tag => new Element(tag), createTextNode: text => Object.assign(new Element('#text'), {textContent: text}),
            addEventListener: (type, handler) => { documentHandlers[type] = handler; },
            removeEventListener: type => { delete documentHandlers[type]; }}});
    const shell = new Element(), element = new Element(); shell.appendChild(element);
    const feed = window.createTwitchPreviewFeed(element);
    return {feed, element, shell, frames, observers, documentHandlers,
        receive(id) { feed.receive({type: 'message', message: {id: String(id), user_id: 'user',
            platform: 'twitch', kind: 'message', username: 'chatter', message: 'hello'}}); },
        flush() { const pending = [...frames.values()]; frames.clear(); pending.forEach(callback => callback()); }};
}

test('shared chat renders GIFs without rewriting signed URLs and handles unavailable media', () => {
    const app = setup(), url = 'https://media.giphy.com/media/example/giphy.gif?cid=full%2Ftoken';
    app.feed.receive({type: 'message', message: {id: 'gif', platform: 'twitch', username: 'chatter', segments: [{type: 'gif', text: 'GIF', url}]}});
    const row = app.element.children.at(-1), gif = row.querySelector('.live-chat-gif');
    assert.equal(gif.src, url);
    assert.equal(gif.srcset, undefined);
    assert.equal(gif.alt, 'GIF');
    assert.equal(gif.referrerPolicy, 'no-referrer');
    gif.handlers.error();
    assert.equal(row.querySelector('.live-chat-gif-fallback').textContent, 'GIF unavailable');
    app.feed.receive({type: 'message', message: {id: 'bad-gif', platform: 'twitch', segments: [{type: 'gif', text: 'GIF', url: 'javascript:alert(1)'}]}});
    assert.equal(app.element.children.at(-1).querySelector('.live-chat-gif'), undefined);
});

test('local notice samples reach an open preview and detach when it closes', () => {
    const app = setup(true);
    const handler = app.documentHandlers['dashboard-chat-test-notice'];
    handler({detail: {id: 'sample', test_mode: true, platform: 'twitch', kind: 'chat',
        username: 'test', notice: 'Raiding with 25 viewers', notice_type: 'raid'}});
    assert.equal(app.element.children.length, 1);
    assert.equal(app.element.children[0].dataset.noticeType, 'raid');
    handler({detail: {id: 'not-test', platform: 'twitch'}});
    assert.equal(app.element.children.length, 1);
    app.feed.destroy();
    assert.equal(app.documentHandlers['dashboard-chat-test-notice'], undefined);
});

test('Bits messages show the diamond icon, amount, and purple highlight without changing ordinary messages', () => {
    const app = setup();
    app.feed.receive({type: 'message', message: {id: 'bits', platform: 'twitch', username: 'cheerer', bits: 1000, message: 'Cheer1000 hello'}});
    const row = app.element.children.at(-1), bits = row.querySelector('.live-chat-bits');
    assert.equal(row.classList.contains('has-bits'), true);
    assert.equal(bits['aria-label'], '1,000 Bits');
    assert.match(bits.innerHTML, /<svg/);
    assert.equal(row.querySelector('.live-chat-text').textContent, '1,000 hello');
    assert.equal(row.querySelector('.live-chat-message-heading').querySelector('.live-chat-bits'), undefined);
    app.receive('ordinary');
    assert.equal(app.element.children.at(-1).classList.contains('has-bits'), false);
});

test('watch streak notices show the count, flame icon and matching highlighted border', () => {
    const app = setup();
    app.feed.receive({type: 'message', message: {id: 'streak', platform: 'twitch', username: 'watcher',
        notice_type: 'watch_streak', notice_label: 'Watch streak', notice: 'Watched 10 consecutive streams!', watch_streak: 10, message: 'Happy to be here!'}});
    const row = app.element.children.at(-1);
    assert.equal(row.classList.contains('has-watch-streak'), true);
    assert.equal(row.querySelector('.live-chat-notice-label').textContent, '10 watch streak');
    assert.equal(row.querySelector('.live-chat-notice-separator').textContent, '·');
    assert.equal(row.querySelector('.live-chat-notice').querySelector('.live-chat-text').textContent, 'Happy to be here!');
    assert.match(row.querySelector('.live-chat-notice-icon').innerHTML, /<svg/);
});

test('a single Bit displays only its icon while keeping an accessible amount', () => {
    const app = setup();
    app.feed.receive({type: 'message', message: {id: 'single-bit', platform: 'twitch', bits: 1, message: 'Cheer1'}});
    const bits = app.element.children.at(-1).querySelector('.live-chat-bits');
    assert.equal(bits['aria-label'], '1 Bit');
    assert.equal(bits.textContent, '');
    assert.match(bits.innerHTML, /<svg/);
});

test('Bits spaced through a message replace each cheer in place without a total', () => {
    const app = setup();
    app.feed.receive({type: 'message', message: {id: 'spaced-bits', platform: 'twitch', bits: 150, message: 'Cheer100 hello Cheer50 world'}});
    const row = app.element.children.at(-1);
    assert.deepEqual(row.querySelectorAll('.live-chat-bits').map(bits => bits['aria-label']), ['100 Bits', '50 Bits']);
    const text = row.querySelector('.live-chat-text').textContent;
    assert.equal(text.replace(/\s+/g, ' '), '100 hello 50 world');
    assert.doesNotMatch(text, /Cheer\d+/i);
});

test('Bits-only cheers show only the icon and count, including custom cheermote names', () => {
    const app = setup();
    for (const segments of [[], [{type: 'cheermote', text: 'CustomCheer500'}]]) {
        app.feed.receive({type: 'message', message: {id: `cheer-${segments.length}`, platform: 'twitch', bits: 500, message: 'Cheer500', segments}});
        const row = app.element.children.at(-1);
        assert.equal(row.querySelector('.live-chat-bits')['aria-label'], '500 Bits');
        assert.equal(row.querySelector('.live-chat-text').textContent, '500');
    }
});

test('gigantified power-ups enlarge native emotes and load their higher-resolution artwork', () => {
    const app = setup(), url = 'https://static-cdn.jtvnw.net/emoticons/v2/25/static/dark/2.0';
    for (const large of [true, false]) {
        app.feed.receive({type: 'message', message: {id: `large-${large}`, platform: 'twitch', gigantified_emote: large,
            segments: [{type: 'emote', text: 'Kappa', url}]}});
        const row = app.element.children.at(-1), emote = row.querySelector('.live-chat-emote');
        assert.equal(row.classList.contains('has-gigantified-emote'), large);
        assert.equal(emote.classList.contains('is-gigantified'), large);
        assert.equal(emote.src, large ? url.replace('/2.0', '/3.0') : url);
    }
});

test('mixed gigantified messages enlarge only the last native emote occurrence', () => {
    const app = setup(), native = 'https://static-cdn.jtvnw.net/emoticons/v2/25/static/dark/2.0';
    const thirdParty = 'https://cdn.7tv.app/emote/test/2x.webp';
    app.feed.receive({type: 'message', message: {id: 'mixed-large', platform: 'twitch', gigantified_emote: true,
        segments: [{type: 'emote', text: 'Kappa', url: native}, {type: 'text', text: ' '},
            {type: 'emote', text: 'Kappa', url: native}, {type: 'emote', text: 'Other', url: thirdParty}]}});
    const emotes = app.element.children.at(-1).querySelectorAll('.live-chat-emote');
    assert.deepEqual(emotes.map(emote => emote.classList.contains('is-gigantified')), [false, true, false]);
    assert.deepEqual(emotes.map(emote => emote.src), [native, native.replace('/2.0', '/3.0'), thirdParty]);
});

test('chosen name colors survive dashboard legacy and preview formats', () => {
    const app = setup();
    for (const [id, color, expected] of [['old', '0x7800A0', '#7800A0'], ['new', '#12ab34', '#12ab34']]) {
        app.feed.receive({type: 'message', message: {id, color, platform: 'twitch', kind: 'message', username: 'chatter'}});
        const name = app.element.children.at(-1).querySelector('.live-chat-name');
        assert.equal(name.style.color, expected);
        assert.equal(name.dataset.chatNameColor, expected);
    }
});

test('preview jump arrow uses a centered vector instead of font alignment', () => {
    const app = setup();
    const button = app.shell.querySelector('.live-chat-jump');
    assert.match(button.innerHTML, /viewBox="0 0 24 24"/);
    assert.match(button.innerHTML, /M12 5v14m-6-6 6 6 6-6/);
});

test('local send errors retain platform identity and have an accessible private label', () => {
    const app = setup();
    app.feed.receive({type: 'message', message: {id: 'local-error:1', platform: 'youtube',
        kind: 'send-error', local_only: true, display_name: 'YouTube send error · Only you', message: 'Reconnect YouTube.'}});
    const row = app.element.children.at(-1);
    assert.equal(row.role, 'alert');
    assert.equal(row.classList.contains('platform-youtube'), true);
    assert.equal(row.querySelector('.live-chat-platform').textContent, 'YT');
    assert.match(row.querySelector('.live-chat-name').textContent, /Only you/);
    assert.equal(row.querySelector('.live-chat-message-actions'), undefined);
});

test('shared feed renders notices and optional emote-bearing text without blank message rows', () => {
    const app = setup();
    for (const noticeType of ['sub', 'resub', 'watch_streak', 'sub_gift', 'community_sub_gift', 'redemption']) {
        app.feed.receive({type: 'message', message: {id: noticeType, platform: 'twitch', kind: 'chat',
            username: 'viewer', notice_type: noticeType, notice_label: 'Event', notice: 'Event details', message: ''}});
        const row = app.element.children.at(-1);
        assert.equal(row.dataset.noticeType, noticeType);
        assert.equal(row.classList.contains('is-bot'), true);
        assert.equal(row.querySelector('.live-chat-notice-label').textContent, noticeType === 'watch_streak' ? 'Watch streak' : 'Event');
        assert.equal(row.querySelector('.live-chat-notice-text').textContent, 'Event details');
        assert.equal(row.querySelector('.live-chat-text'), undefined);
    }
    app.feed.receive({type: 'message', message: {id: 'with-text', platform: 'twitch', kind: 'chat',
        username: 'viewer', notice: 'Resubscribed', message: 'Kappa',
        segments: [{type: 'emote', text: 'Kappa', url: 'https://static-cdn.jtvnw.net/emoticons/v2/25/static/dark/2.0'}]}});
    assert.equal(app.element.children.at(-1).querySelector('.live-chat-emote').alt, 'Kappa');
});

test('message bursts share scroll frames and reuse one row resize observer', () => {
    const app = setup();
    for (let id = 0; id < 25; id++) app.receive(id);
    assert.equal(app.frames.size, 1); assert.equal(app.observers.length, 1);
    assert.equal(app.observers[0].observed.length, 25);
    app.flush(); assert.equal(app.frames.size, 1);
    app.receive('later'); assert.equal(app.frames.size, 1);
    app.flush(); assert.equal(app.frames.size, 0);
    assert.equal(app.element.scrollTop, app.element.scrollHeight);
});

test('message limits, duplicate suppression and deletion retain their behavior', () => {
    const app = setup();
    for (let id = 0; id < 160; id++) app.receive(id);
    assert.equal(app.element.children.length, 150);
    assert.equal(app.element.children[0].dataset.messageId, '10');
    app.receive(159); assert.equal(app.element.children.length, 150);
    app.feed.receive({type: 'message_delete', id: '159'});
    assert.equal(app.element.children.length, 149);
    app.feed.receive({type: 'clear_user_messages', user_id: 'user'});
    assert.equal(app.element.children.length, 0);
    app.receive(159); assert.equal(app.element.children.length, 1);
    app.feed.receive({type: 'clear'}); assert.equal(app.element.children.length, 0);
});

test('closing a preview cancels scheduled scrolling, detaches listeners and ignores late messages', () => {
    const app = setup(); app.receive(1);
    const jump = app.shell.children[1];
    app.feed.destroy(); app.feed.destroy();
    assert.equal(app.frames.size, 0); assert.equal(app.observers[0].disconnected, true);
    assert.deepEqual(app.element.handlers, {}); assert.deepEqual(jump.handlers, {});
    assert.equal(app.shell.children.length, 1);
    app.feed.receive({type: 'clear'}); app.receive(2);
    assert.equal(app.element.children.length, 1);
    assert.equal(app.observers.length, 1);
});

test('user scroll position is not overwritten by a pending message-burst scroll', () => {
    const app = setup();
    for (let id = 0; id < 20; id++) app.receive(id);
    app.element.scrollTop = 0; app.element.handlers.scroll();
    app.flush(); app.flush();
    assert.equal(app.element.scrollTop, 0); assert.equal(app.shell.children[1].hidden, false);
    app.shell.children[1].handlers.click();
    assert.equal(app.element.scrollTop, app.element.scrollHeight);
});

test('pinned-message polling never overlaps requests and releases its guard after failures', async () => {
    const refresh = source.match(/    async function refreshPinned\(feed\) \{[\s\S]*?\n    \}/)[0];
    let requests = 0, resolve, reject;
    const context = {document: {hidden: false}, renderPinned() {},
        fetch() { requests++; return new Promise((yes, no) => { resolve = yes; reject = no; }); }};
    vm.createContext(context); vm.runInContext(refresh, context);
    const feed = {pinnedUrl: '/pin'};
    let pending = context.refreshPinned(feed);
    await context.refreshPinned(feed); assert.equal(requests, 1);
    reject(new Error('offline')); await pending; assert.equal(feed.refreshingPinned, false);
    pending = context.refreshPinned(feed); assert.equal(requests, 2);
    resolve({ok: false}); await pending; assert.equal(feed.refreshingPinned, false);
    pending = context.refreshPinned(feed);
    resolve({ok: true, json: async () => ({message: null})}); await pending;
    assert.equal(feed.refreshingPinned, false);
});

test('filtering queries rows and viewport once while retaining filtering and follow behavior', () => {
    const callback = source.match(/const refreshFilters = \(\) => \{([\s\S]*?)\n        \};/)[1];
    const rows = ['allowed', 'blocked'].map(user => ({hidden: false,
        dataset: {chatUser: user, chatType: 'messages'}, getBoundingClientRect: () => ({top: 10, bottom: 30})}));
    let queries = 0, measurements = 0, scrolls = 0;
    const element = {querySelectorAll() { queries++; return rows; },
        getBoundingClientRect() { measurements++; return {top: 0}; }};
    const feed = {followNewest: true, filters: {allows: category => category.user === 'allowed'}};
    vm.runInNewContext(`(() => {${callback}\n})()`, {element, feed,
        scrollToNewest: () => { scrolls++; }, updateJumpButton() {}});
    assert.equal(queries, 1); assert.equal(measurements, 0); assert.equal(scrolls, 1);
    assert.equal(rows[0].hidden, false); assert.equal(rows[1].hidden, true);
});

test('filtering preserves the visible anchor when not following new messages', () => {
    const callback = source.match(/const refreshFilters = \(\) => \{([\s\S]*?)\n        \};/)[1];
    const before = {hidden: false, dataset: {chatUser: 'blocked', chatType: 'messages'},
        getBoundingClientRect: () => ({top: -20, bottom: -1})};
    const anchor = {hidden: false, dataset: {chatUser: 'allowed', chatType: 'messages'},
        getBoundingClientRect: () => ({top: before.hidden ? 10 : 40, bottom: 60})};
    let measurements = 0;
    const element = {scrollTop: 100, querySelectorAll: () => [before, anchor],
        getBoundingClientRect() { measurements++; return {top: 0}; }};
    const feed = {followNewest: false, filters: {allows: category => category.user === 'allowed'}};
    vm.runInNewContext(`(() => {${callback}})()`, {element, feed,
        scrollToNewest() { throw new Error('Must preserve scrolled position'); }, updateJumpButton() {}});
    assert.equal(measurements, 1);
    assert.equal(element.scrollTop, 70);
    assert.equal(before.hidden, true);
    assert.equal(anchor.hidden, false);
});

test('private send failures are bot messages for the affected platform and obey filter changes', () => {
    const context = {window: {}, feed: {}, localErrorSequence: 0};
    vm.createContext(context);
    vm.runInContext(fs.readFileSync('web/static/js/dashboard-chat-filters.js', 'utf8'), context);
    const handler = source.match(/const onSendError = event => renderMessage\(feed, \{[\s\S]*?\n            \}\);/)[0];
    const rows = [];
    context.renderMessage = (_feed, message) => {
        assert.equal(message.local_only, true);
        assert.equal(message.is_bot, true);
        const category = context.window.dashboardChatFilters.category(message);
        rows.push({hidden: false, dataset: {localOnly: 'true', chatUser: category.user, chatType: category.type},
            getBoundingClientRect: () => ({top: 10, bottom: 30})});
    };
    vm.runInContext(`${handler}\nonSendError({detail:{platform:'twitch',message:'Failed'}}); onSendError({detail:{platform:'youtube',message:'Failed'}});`, context);
    assert.deepEqual(rows.map(row => row.dataset.chatUser), ['bots', 'youtube_bots']);
    assert.ok(rows.every(row => row.dataset.chatType === 'messages'));
    const callback = source.match(/const refreshFilters = \(\) => \{([\s\S]*?)\n        \};/)[1];
    const allowed = new Set(['bots']);
    context.feed = {followNewest: true, filters: {allows: category => allowed.has(category.user)}};
    context.element = {querySelectorAll: () => rows, getBoundingClientRect: () => ({top: 0})};
    context.scrollToNewest = context.updateJumpButton = () => {};
    vm.runInContext(`(() => {${callback}})()`, context);
    assert.deepEqual(rows.map(row => row.hidden), [false, true]);
    allowed.delete('bots'); allowed.add('youtube_bots');
    vm.runInContext(`(() => {${callback}})()`, context);
    assert.deepEqual(rows.map(row => row.hidden), [true, false]);
});

test('gigantified preference resizes existing emotes without hiding their messages', () => {
    const callback = source.match(/const refreshFilters = \(\) => \{([\s\S]*?)\n        \};/)[1];
    let large = false, applied;
    const emote = {classList: {toggle: (name, enabled) => { applied = enabled; }}};
    const row = {hidden: false, dataset: {chatUser: 'non_subs', chatType: 'messages'}, querySelectorAll: () => [emote]};
    const context = {element: {querySelectorAll: () => [row], getBoundingClientRect: () => ({top: 0})},
        feed: {followNewest: true, filters: {allows: () => true, gigantified: () => large}}, scrollToNewest() {}, updateJumpButton() {}};
    vm.runInNewContext(`(() => {${callback}})()`, context);
    assert.equal(applied, false); assert.equal(row.hidden, false);
    large = true;
    vm.runInNewContext(`(() => {${callback}})()`, context);
    assert.equal(applied, true); assert.equal(row.hidden, false);
});

test('local display previews remain visible when chat filters exclude their category', () => {
    const callback = source.match(/const refreshFilters = \(\) => \{([\s\S]*?)\n        \};/)[1];
    const rows = [
        {hidden: false, dataset: {localPreview: 'true', chatUser: 'bots', chatType: 'redeems'}},
        {hidden: false, dataset: {chatUser: 'bots', chatType: 'redeems'}},
    ];
    vm.runInNewContext(`(() => {${callback}})()`, {
        element: {querySelectorAll: () => rows, getBoundingClientRect: () => ({top: 0})},
        feed: {followNewest: true, filters: {allows: () => false}}, scrollToNewest() {}, updateJumpButton() {},
    });
    assert.equal(rows[0].hidden, false);
    assert.equal(rows[1].hidden, true);
});

test('shared messages display a text-safe source label and retain the destination message ID', () => {
    const app = setup();
    app.feed.receive({type: 'message', message: {id: 'destination', platform: 'twitch', kind: 'chat',
        username: 'viewer', message: 'Hello', is_shared: true, source_channel_name: '<img src=x onerror=bad()>',
        source_channel_id: 'other', source_message_id: 'original'}});
    const row = app.element.children[0];
    assert.equal(row.dataset.messageId, 'destination');
    assert.equal(row.dataset.chatOrigin, 'shared');
    assert.equal(row.querySelector('.live-chat-source').textContent, 'From <img src=x onerror=bad()>');
    assert.equal(row.querySelectorAll('img').length, 0);
});
