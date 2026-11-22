const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('Stream Together session controls work on desktop and mobile without creating a chat connection',
    {skip: !chromium || !fs.existsSync(executablePath || '')}, async () => {
        const browser = await chromium.launch({executablePath, headless: true});
        try {
            for (const width of [1200, 390]) {
                const page = await browser.newPage({viewport: {width, height: 844}, hasTouch: width === 390});
                const errors = []; page.on('pageerror', error => errors.push(error.message));
                const template = fs.readFileSync('web/templates/channel/_stream_together_call.html', 'utf8');
                const chatTemplate = fs.readFileSync('web/templates/channel/_combined_chat.html', 'utf8');
                const chatShortcut = chatTemplate.match(/<a class="chat-filter-toggle dashboard-shared-chat-link"[^\n]+<\/a>/)[0]
                    .replace('{{ broadcaster.login | urlencode }}', 'owner');
                const start = template.indexOf('<dialog id="dashboard-stream-together"');
                const dialogTemplate = template.slice(start, template.indexOf('</dialog>', start) + '</dialog>'.length);
                function renderDialog(standalone) {
                    return dialogTemplate.replace(/\{% if stream_together_page %\}([\s\S]*?)(?:\{% else %\}([\s\S]*?))?\{% endif %\}/g,
                        (_, fullPage, overlay = '') => standalone ? fullPage : overlay)
                    .replace('{% if stream_together_initial %} open{% endif %}', standalone ? ' open' : '')
                    .replace('{{ csrf_token }}', 'test-csrf')
                    .replace('{{ broadcaster.id }}', '1')
                    .replace("{{ broadcaster.login or '' }}", 'owner')
                    .replace("{{ broadcaster.name or broadcaster.login or 'Your channel' }}", 'Owner')
                    .replace("{{ broadcaster.profile_image_url or '' }}", '/owner-avatar.svg')
                    .replaceAll('{{ broadcaster.login | urlencode }}', 'owner')
                    .replace(/\{% with (picker_search_url=.*?) %\}[\s\S]*?\{% endwith %\}/g, (_, argumentsText) => {
                        const fields = Object.fromEntries([...argumentsText.matchAll(/(picker_\w+)=(?:'([^']*)'|(\d+))/g)]
                            .map(([, name, stringValue, numberValue]) => [name, stringValue ?? numberValue]));
                        return fs.readFileSync('web/templates/shared/user_search_form.html', 'utf8')
                            .replace('{% if picker_add_label | default(\'\') %} data-add-label="{{ picker_add_label }}"{% endif %}', ` data-add-label="${fields.picker_add_label}"`)
                            .replace(/\{\{ (picker_\w+)(?: \| default\((?:'([^']*)'|(\d+))\))? \}\}/g,
                                (_, name, stringDefault, numberDefault) => fields[name] ?? stringDefault ?? numberDefault);
                    })
                    .replace(/\{% with user_search_add_url=[\s\S]*?\{% endwith %\}/g, '<form data-protected-user-result data-user-search-local hidden><input data-protected-result-id><strong data-protected-result-label></strong><small data-protected-result-user-id></small><button data-protected-add></button></form>')
                    .replaceAll('{{ state_toggle_contents(false) }}', '<span class="state-toggle-current">Disabled</span><span class="state-toggle-alternate">Enable</span>');
                }
                const dialog = renderDialog(false);
                const actions = [];
                let denied = false, sharedChatActive = false, joined = false, guestDetected = false;
                const call = {state: 'active', slot_count: 6, session: {id: 'call', guests: [{slot_id: '0', user_id: '1', user_display_name: 'Owner', is_streaming: false},
                    {slot_id: '1', user_id: '2', user_display_name: 'Friend', is_streaming: true, is_live: true, volume: 75, audio_settings: {is_host_enabled: true}, video_settings: {is_host_enabled: true}}]},
                    invites: [{user_id: '3', status: 'READY'}]};
                await page.context().route('https://www.twitch.tv/popout/**/guest-star', route => route.fulfill({contentType: 'text/html', body: '<h1>Twitch call</h1>'}));
                await page.route('http://dashboard.test/**', async route => {
                    const requestUrl = new URL(route.request().url());
                    const path = requestUrl.pathname;
                    if (path === '/channel/stream-together') {
                        const scriptTags = ['protected-users', 'dashboard-test-names', 'dashboard-carousel', 'dashboard-participant-order',
                            'dashboard-stream-participants', 'dashboard-viewer-queue', 'dashboard-stream-together-cards',
                            'dashboard-stream-together-controls', 'dashboard-stream-together', 'dashboard-ad-status'].map(script => `<script src="/static/js/${script}.js" defer></script>`).join('');
                        return route.fulfill({contentType: 'text/html', body: `<!doctype html><link rel="stylesheet" href="/static/css/style.css"><link rel="stylesheet" href="/static/css/dashboard-stream-together.css">
                            <body class="dashboard-page channel-page channel-page-stream-together" data-channel-root="/channel"><div class="app-shell sidebar-collapsed">
                            <aside class="sidebar" id="channel-navigation" data-channel-sidebar><nav class="navigation"><a class="nav-link" href="/channel">Overview</a><a class="nav-link active" href="/channel/stream-together" aria-current="page">Stream Together</a></nav>
                            <span data-dashboard-carousel-position><span data-dashboard-carousel-count></span><span data-dashboard-carousel-name></span></span></aside>
                            <main class="main-content streamer-main-content">
                            <div class="channel-dashboard-layout" data-dashboard-carousel hidden>
                            <div class="dashboard-chat-column">
                            <div class="dashboard-header-side"><div class="dashboard-header-stats">
                            ${['Offline', 'Viewers 42', 'Followers 1,024', 'Subs 15 (18 pts)']
                                .map(label => `<button class="dashboard-header-stat">${label}</button>`).join('')}
                            <div class="dashboard-ad-stat dashboard-ad-sticky" data-ad-status-mirror><span class="stream-together-ad-label">Ads</span><strong data-ad-status-mirror-text>Checking…</strong></div>
                            </div></div>
                            <section class="panel live-chat-panel"><h3>Combined Chat</h3><div data-live-chat-feed style="height:60px;overflow:auto"><div style="height:400px">Chat history</div></div><textarea aria-label="Chat message"></textarea></section>
                            </div>
                            <div class="dashboard-ads-panel" data-ad-status data-state="loading"><strong data-ad-status-text>Checking…</strong></div>
                            <div class="dashboard-video-card">
                                <nav data-stream-participants hidden><div data-stream-participant-icons></div></nav>
                                <div class="dashboard-video-frame"><div data-stream-player data-channel="owner"></div></div>
                            </div>
                            <div data-viewer-queue-panel data-read-only="true" data-state-url="/channel/api/viewer-queue">
                                <span data-queue-count></span><span class="queue-state-current"></span><div id="viewer-queue-content"></div>
                            </div><div class="dashboard-actions-panel"></div>
                            <div class="dashboard-moderation-panel"></div><div class="dashboard-community-panel"></div>
                            <div class="dashboard-carousel-deck" data-dashboard-carousel-deck></div>
                            <button data-dashboard-carousel-prev>Previous</button><button data-dashboard-carousel-next>Next</button></div>
                            <div class="stream-together-page" data-stream-together-layout>${renderDialog(true)}<div id="stream-together-chat" class="stream-together-page-chat"></div></div>
                            </main></div>${scriptTags}</body>`});
                    }
                    if (/^\/static\/(?:js|css)\/[\w.-]+$/.test(path)) {
                        return route.fulfill({path: `web${path}`, contentType: path.endsWith('.css') ? 'text/css' : 'text/javascript'});
                    }
                    if (path === '/channel/api/ad-status') return route.fulfill({json: {state: 'none', label: 'No ad scheduled'}});
                    if (path === '/channel/api/viewer-queue') return route.fulfill({json: {open: false, users: []}});
                    if (path === '/channel/api/stream-together/guests' && joined && requestUrl.searchParams.get('refresh') === 'true') {
                        guestDetected = sharedChatActive = true;
                    }
                    const guestSession = guestDetected || requestUrl.searchParams.get('guest_host') === 'another' ? {id: 'guest-call', guests: [{user_id: '1', slot_id: '0', user_display_name: 'Owner'}, {user_id: '4', slot_id: '1', user_display_name: 'Another'}]} : null;
                    if (path === '/owner-avatar.svg') return route.fulfill({contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="purple"/></svg>'});
                    if (path === '/channel/api/stream-together/participants') {
                        return route.fulfill({json: {participants: guestSession ? [
                            {id: '1', login: 'owner', is_streaming: true}, {id: '4', login: 'another', is_streaming: true}
                        ] : [], active: Boolean(call.session || guestSession),
                            is_host: Boolean(call.session) && call.is_host !== false, shared_chat_active: sharedChatActive}});
                    }
                    if (path === '/channel/protected-users/search') return route.fulfill({json: {users: [{id: '4', login: 'another', display_name: 'Another', already_protected: true, related: true}]}});
                    if (path === '/channel/api/stream-together/guests') {
                        return route.fulfill(denied ? {status: 403, json: {detail: 'Reconnect Twitch to allow Stream Together controls.', reconnect: true}}
                            : {json: guestSession ? {...call, is_host: false, session: guestSession, host_id: '4', call_url: 'https://www.twitch.tv/popout/another/guest-star'} : call});
                    }
                    if (path === '/channel/api/stream-together/control') {
                        const action = Object.fromEntries(new URLSearchParams(route.request().postData())); actions.push(action);
                        if (action.action === 'end') call.session = null;
                        if (action.action === 'start') call.session = {id: 'new-call', guests: []};
                        return route.fulfill({json: {ok: true}});
                    }
                    return route.fulfill({contentType: 'text/html; charset=utf-8', body: `<body data-channel-root="/channel"><style>@media(max-width:750px){#test-layout{grid-template-columns:1fr!important;grid-template-rows:60% 40%;}}</style><div id="test-layout" class="channel-dashboard-layout" style="display:grid;grid-template-columns:minmax(0,1fr) 32%;height:calc(100vh - 16px)"><section><button data-stream-together-open>Stream Together</button><button data-stream-request-end>Hang up</button></section><section class="panel live-chat-panel" aria-label="Dashboard chat"><header>Chat ${chatShortcut}</header><div class="live-chat-feed-shell"><div class="dashboard-chat-feed">Existing chat message</div></div><textarea aria-label="Chat message"></textarea></section></div>${dialog}</body>`});
                });
                await page.addInitScript(() => {
                    window.fetched = [];
                    const fetchRequest = window.fetch.bind(window);
                    window.fetch = (url, ...args) => {
                        fetched.push(new URL(url, location.href).pathname);
                        return fetchRequest(url, ...args);
                    };
                    window.streams = [];
                    window.EventSource = class {
                        constructor(url) { this.url = String(url); this.listeners = {}; streams.push(this); }
                        addEventListener(type, handler) { this.listeners[type] = handler; }
                        close() { this.closed = true; }
                        emit(type, data) { (type === 'message' ? this.onmessage : this.listeners[type])?.({data: JSON.stringify(data)}); }
                    };
                });
                await page.goto('http://dashboard.test/');
                await page.evaluate(() => {
                    document.querySelector('#test-layout > section').insertAdjacentHTML('beforeend', `<div class="dashboard-video-card">
                        <nav class="dashboard-stream-participants" data-stream-participants hidden><div data-stream-participant-icons></div></nav>
                        <div class="dashboard-video-frame"><div id="test-player" class="dashboard-video-player" data-stream-player data-channel="owner"></div></div></div>`);
                    window.testPlayerChannels = [];
                    class Player {
                        addEventListener(event, callback) { if (event === 'READY') queueMicrotask(callback); }
                        setChannel(login) { testPlayerChannels.push(login); }
                    }
                    Player.READY = 'READY';
                    window.Twitch = {Player};
                });
                for (const css of ['style', 'dashboard-stream-together']) await page.addStyleTag({path: `web/static/css/${css}.css`});
                await page.addScriptTag({path: 'web/static/js/hover-labels.js'});
                for (const js of ['protected-users', 'dashboard-test-names', 'dashboard-stream-player', 'dashboard-participant-order', 'dashboard-stream-participants', 'dashboard-stream-together-cards', 'dashboard-stream-together-controls', 'dashboard-stream-together']) {
                    await page.addScriptTag({path: `web/static/js/${js}.js`});
                }
                const chatBounds = await page.locator('.live-chat-panel').boundingBox();
                await page.evaluate(() => { window.originalChatPanel = document.querySelector('.live-chat-panel'); });
                await page.locator('[data-stream-together-open]').first().click();
                assert.deepEqual(await page.locator('.live-chat-panel').boundingBox(), chatBounds, 'Opening the call must not reposition or resize chat');
                assert.equal(await page.locator('.live-chat-panel').getAttribute('popover'), null);
                assert.equal(await page.evaluate(() => document.querySelector('.live-chat-panel') === originalChatPanel), true);
                await page.getByRole('textbox', {name: 'Chat message', exact: true}).fill('chat stays usable');
                assert.equal(await page.locator('[data-stream-together]').evaluate(dialog => dialog.open), true);
                await page.getByRole('button', {name: 'Expand Friend', exact: true}).click();
                const sharedChat = page.locator('[data-stream-together] [data-shared-chat-shortcut]');
                const headerSharedChat = page.locator('.live-chat-panel [data-shared-chat-shortcut]');
                assert.equal(await page.getByRole('button', {name: 'Manage participant', exact: true}).count(), 0);
                assert.equal(await page.getByRole('button', {name: 'Start a call', exact: true}).isVisible(), false);
                await page.getByRole('button', {name: 'Friend options', exact: true}).click();
                await page.getByRole('menuitem', {name: 'Kick', exact: true}).click();
                await page.keyboard.press('Escape');
                assert.equal(actions.length, 0);
                await page.getByRole('button', {name: 'Friend options', exact: true}).click();
                await page.getByRole('menuitem', {name: 'Kick', exact: true}).click();
                await page.getByRole('menuitem', {name: 'Confirm kick', exact: true}).click();
                await page.waitForFunction(() => document.querySelector('[data-stream-together-controls]').getAttribute('aria-busy') !== 'true');
                assert.equal(actions[0].action, 'remove');
                await page.locator('[data-stream-invitations] summary').click();
                const guestSlot = page.getByRole('combobox', {name: 'Guest slot', exact: true});
                await guestSlot.selectOption('4');
                await page.getByRole('button', {name: 'Revoke invite', exact: true}).click();
                call.session.guests[1].thumbnail_url = 'https://images.test/refreshed.jpg';
                await page.evaluate(() => window.dispatchEvent(new Event('dashboard-stream-participants-changed')));
                await page.waitForFunction(() => !document.querySelector('[data-stream-together-refresh]').disabled);
                assert.equal(await guestSlot.inputValue(), '4', 'Thumbnail refreshes preserve the selected invite slot');
                assert.equal(await page.getByRole('button', {name: 'Revoke invite?', exact: true}).isVisible(), true,
                    'Thumbnail refreshes preserve the pending confirmation');
                await page.getByRole('button', {name: 'Cancel', exact: true}).click();
                await guestSlot.selectOption('2');
                await page.getByRole('button', {name: 'Add to call', exact: true}).click();
                await page.waitForFunction(() => document.querySelector('[data-stream-together-controls]').getAttribute('aria-busy') !== 'true');
                assert.equal(actions[1].slot_id, '2'); assert.equal(actions[1].guest_id, '3');
                await page.locator('[data-stream-invite] summary').click();
                await page.locator('#stream-invite-query').fill('another');
                await page.getByRole('button', {name: 'Invite', exact: true}).click();
                await page.waitForFunction(() => document.querySelector('[data-stream-together-controls]').getAttribute('aria-busy') !== 'true');
                assert.equal(actions[2].action, 'invite'); assert.equal(actions[2].guest_id, '4');
                await page.locator('[data-stream-together-controls]').evaluate(panel => { panel.scrollTop = 0; });
                await page.screenshot({path: `.data/stream-together-controls-${width}.png`});
                const callHangup = page.locator('[data-stream-together]').getByRole('button', {name: 'Hang up', exact: true});
                const stripHangup = page.locator('[data-stream-request-end]');
                async function assertCenteredHover(button, label) {
                    await button.evaluate(element => Promise.allSettled(element.getAnimations().map(animation => animation.finished)));
                    await page.mouse.move(0, 0);
                    await button.hover();
                    const tooltip = page.locator('.dashboard-hover-tooltip:visible').filter({hasText: label});
                    await tooltip.waitFor();
                    const bounds = await button.locator('..').boundingBox();
                    const hover = await tooltip.boundingBox();
                    assert.ok(Math.abs(hover.x + hover.width / 2 - bounds.x - bounds.width / 2) < 1, label);
                }
                if (width === 1200) await assertCenteredHover(callHangup, 'Hang up');
                await callHangup.click();
                assert.equal(actions.length, 3, 'Ending requires confirmation');
                const confirmCall = page.getByRole('button', {name: 'End call', exact: true});
                assert.equal(await confirmCall.textContent(), '×');
                assert.equal(await confirmCall.evaluate(button => button.parentElement.getAnimations({subtree: true})
                    .some(animation => animation.transitionProperty === 'transform')), true, 'Hang up slides the confirmation into view');
                if (width === 1200) await assertCenteredHover(confirmCall, 'End call');
                await confirmCall.click();
                await page.getByRole('button', {name: 'Start a call', exact: true}).waitFor();
                await headerSharedChat.waitFor({state: 'hidden'});
                assert.equal(await sharedChat.isVisible(), false);
                assert.equal(await page.getByRole('switch', {name: 'Hide non-streaming participants', exact: true}).isVisible(), false);
                assert.equal(await page.getByRole('link', {name: 'Open Twitch call', exact: true}).isVisible(), false);
                assert.equal(await page.getByText('Starting a session opens Twitch', {exact: false}).isVisible(), true);
                assert.equal(await callHangup.isVisible(), false);
                assert.equal(actions[3].session_id, 'call');
                await page.evaluate(() => { window.originalOpen = window.open; window.open = () => null; });
                await page.getByRole('button', {name: 'Start a call', exact: true}).click();
                assert.equal(actions.length, 4, 'A blocked popup must not create a call without its Twitch interface');
                assert.match(await page.locator('[data-stream-controls-status]').innerText(), /Allow popups/);
                await page.evaluate(() => { window.open = (...args) => { window.callTabArguments = args; return window.originalOpen(...args); }; });
                const popupPromise = page.waitForEvent('popup');
                await page.getByRole('button', {name: 'Start a call', exact: true}).click();
                const popup = await popupPromise;
                await popup.waitForURL('https://www.twitch.tv/popout/owner/guest-star');
                assert.deepEqual(await page.evaluate(() => callTabArguments), ['about:blank', '_blank'], 'The call opens as a regular tab without popup window features');
                assert.equal(await popup.evaluate(() => window.opener), null);
                await popup.close();
                await callHangup.waitFor();
                assert.equal(actions[4].action, 'start');
                sharedChatActive = true;
                await page.evaluate(() => window.dispatchEvent(new Event('dashboard-stream-participants-changed')));
                for (const shortcut of [headerSharedChat, sharedChat]) {
                    await page.waitForFunction(element => element.classList.contains('is-active'), await shortcut.elementHandle());
                    assert.equal(await shortcut.getAttribute('aria-label'), 'Shared Chat is active. Open Twitch call');
                    const popup = page.waitForEvent('popup');
                    await shortcut.click();
                    const twitchCall = await popup;
                    await twitchCall.waitForURL('https://www.twitch.tv/popout/owner/guest-star');
                    await twitchCall.close();
                }
                sharedChatActive = false;
                denied = true;
                await page.locator('[data-stream-together-refresh]').click();
                await page.locator('[data-stream-reconnect]').waitFor();
                assert.equal(await page.evaluate(() => streams.length), 0, 'The popup must not open another chat connection');
                assert.equal(await page.locator('[data-stream-together-chat], [data-stream-together-channels], [data-stream-together-view]').count(), 0);
                const fits = await page.locator('[data-stream-together]').evaluate(dialog => {
                    const bounds = dialog.getBoundingClientRect();
                    return bounds.left >= 0 && bounds.right <= innerWidth && bounds.bottom <= innerHeight
                        && dialog.scrollHeight <= dialog.clientHeight + 1;
                });
                assert.equal(fits, true, `${width}px overlay stays in one viewport`);
                await page.locator('[data-stream-together-close]').click();
                await page.waitForFunction(() => !document.querySelector('[data-stream-together]').open);
                await page.waitForFunction(() => !document.documentElement.classList.contains('stream-together-open'));
                await page.evaluate(() => { location.hash = '#stream-together'; });
                await page.waitForFunction(() => document.querySelector('[data-stream-together]').open);
                await page.locator('[data-stream-together-close]').press('Escape');
                await page.waitForFunction(() => !document.querySelector('[data-stream-together]').open);
                await page.waitForFunction(() => !document.documentElement.classList.contains('stream-together-open'));
                denied = false;
                await stripHangup.click();
                await page.getByRole('button', {name: 'End call', exact: true}).waitFor();
                assert.equal(actions.length, 5, 'Hang up asks for confirmation before ending the call');
                assert.equal(await page.locator('[data-stream-together]').evaluate(dialog => dialog.open), false);
                assert.equal(new URL(page.url()).hash, '');
                await page.keyboard.press('Escape');
                await page.getByRole('button', {name: 'End call', exact: true}).waitFor({state: 'hidden'});
                await page.evaluate(() => dashboardStreamTogetherTest.start(3));
                assert.equal(await page.getByRole('textbox', {name: 'Chat message', exact: true}).inputValue(), 'chat stays usable');
                assert.equal(await page.locator('.stream-call-card:visible').count(), 3);
                const ownCard = page.locator('.stream-call-card:visible').first();
                assert.equal(await ownCard.getAttribute('data-user-id'), '1');
                assert.equal(await ownCard.locator('.stream-call-card-name strong').innerText(), 'Owner');
                assert.equal(await ownCard.locator('.stream-call-portrait').getAttribute('src'), '/owner-avatar.svg');
                await page.getByRole('button', {name: 'Expand test_squid', exact: true}).click();
                assert.equal(await page.locator('.stream-call-grid').evaluate(grid => grid.classList.contains('is-focused')), true);
                await page.getByRole('switch', {name: 'Hide non-streaming participants', exact: true}).click();
                assert.equal(await page.locator('.stream-call-card:visible').count(), 2);
                const visibility = page.locator('[data-stream-hide-offline]');
                assert.equal(await visibility.evaluate(button => getComputedStyle(button).getPropertyValue('--visibility-cut').trim()), '100%', 'Clicking keeps the square visible');
                await visibility.dispatchEvent('pointerenter');
                assert.equal(await visibility.evaluate(button => getComputedStyle(button).getPropertyValue('--visibility-cut').trim()), '50%', 'Hovering the active square previews the two halves');
                assert.equal(await page.locator('.stream-call-card:visible').count(), 2, 'Hovering does not change the filter');
                await visibility.click();
                assert.equal(await page.locator('.stream-call-card:visible').count(), 3);
                assert.equal(await visibility.evaluate(button => getComputedStyle(button).getPropertyValue('--visibility-cut').trim()), '50%', 'Toggling back restores the two halves');
                await visibility.dispatchEvent('pointerleave');
                await visibility.dispatchEvent('pointerenter');
                assert.equal(await visibility.evaluate(button => getComputedStyle(button).getPropertyValue('--visibility-cut').trim()), '100%', 'Hovering previews the square option again');
                await visibility.click();
                assert.equal(await page.locator('.stream-call-card:visible').count(), 2);
                const previewOptions = page.getByRole('button', {name: 'test_squid options', exact: true});
                await previewOptions.click();
                await page.getByRole('menuitem', {name: 'Kick', exact: true}).click();
                assert.equal(await previewOptions.count(), 1, 'Kicking a preview participant requires confirmation');
                await page.getByRole('menuitem', {name: 'Confirm kick', exact: true}).click();
                const kickedCard = page.locator('.stream-call-card[data-user-id="9000000001"]');
                await kickedCard.waitFor({state: 'detached'});
                assert.equal(await page.locator('.stream-call-card:visible').count(), 1);
                assert.equal(actions.length, 5, 'Preview kicks do not send session changes');
                await callHangup.click();
                const confirmTest = page.getByRole('button', {name: 'End test', exact: true});
                assert.equal(await confirmTest.textContent(), '×');
                await confirmTest.click();
                assert.equal(actions.length, 5, 'Test mode must not send session changes');
                await page.waitForFunction(() => document.querySelector('[data-stream-controls-status]').textContent === 'Session active.');
                assert.equal(await page.locator('.dashboard-stream-test-image').count(), 0);
                await page.evaluate(() => dashboardStreamTogetherTest.start(6, 4));
                assert.equal(await page.locator('.stream-call-card:visible').count(), 4, 'The second argument is the online participant count');
                await page.evaluate(() => dashboardStreamTogetherTest.start(6, 6));
                assert.equal(await page.locator('.stream-call-card:visible').count(), 6);
                for (let count = 2; count <= 6; count++) {
                    await page.evaluate(count => dashboardStreamTogetherTest.start(count, count), count);
                    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
                    const fits = await page.locator('[data-stream-together]').evaluate(dialog => {
                        const stage = dialog.querySelector('.stream-call-stage'), footer = dialog.querySelector('.stream-call-footer');
                        const call = dialog.getBoundingClientRect(), chat = document.querySelector('.live-chat-panel').getBoundingClientRect();
                        return stage.scrollHeight <= stage.clientHeight + 1 && footer.scrollHeight <= footer.clientHeight + 1
                            && dialog.scrollHeight <= dialog.clientHeight + 1
                            && (call.right <= chat.left + 1 || call.bottom <= chat.top + 1);
                    });
                    assert.equal(fits, true, `${count} cards fit at ${width}px while chat stays separate`);
                }
                await page.getByRole('button', {name: 'Expand test_car', exact: true}).click();
                await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
                assert.equal(await page.locator('.stream-call-stage').evaluate(stage => stage.scrollHeight <= stage.clientHeight + 1), true, 'Expanded view fits without scrolling');
                await page.getByRole('textbox', {name: 'Chat message', exact: true}).fill('still chatting');
                assert.equal(await page.locator('[data-stream-together]').evaluate(dialog => dialog.open), true);
                await page.screenshot({path: `.data/stream-together-docked-${width}.png`});
                await page.locator('[data-stream-together-close]').click();
                await page.waitForFunction(() => !document.documentElement.classList.contains('stream-together-open'));
                const sampleButton = page.locator('[data-stream-participant-icons] [data-channel="test_squid"]');
                await sampleButton.click();
                assert.equal(await sampleButton.getAttribute('aria-pressed'), 'true');
                assert.match(await page.locator('.dashboard-stream-test-image').getAttribute('alt'), /^test_squid/);
                assert.deepEqual(await page.evaluate(() => testPlayerChannels), [], 'Simulated channels never load through Twitch');
                await page.locator('[data-stream-together-open]').first().click();
                assert.equal(await page.locator('.stream-call-card:visible').count(), 6, 'Reopening restores the simulated call');
                await page.locator('[data-stream-together-close]').click();
                await stripHangup.click();
                await page.getByRole('button', {name: 'End test', exact: true}).click();
                assert.equal(await page.locator('.dashboard-stream-test-image').count(), 0);
                assert.equal(await page.locator('[data-stream-together]').evaluate(dialog => dialog.open), false);
                assert.equal(actions.length, 5);
                await page.locator('[data-stream-together-open]').first().click();
                await page.waitForFunction(() => document.querySelector('[data-stream-controls-status]').textContent === 'Session active.');
                assert.equal(await page.locator('.stream-call-card').count(), 0);
                call.is_host = false;
                sharedChatActive = true;
                call.call_url = 'https://www.twitch.tv/popout/other_host/guest-star';
                call.session = {id: 'connected', guests: [{user_id: '2', slot_id: '0', user_display_name: 'Other host'}, {user_id: '1', slot_id: '1', user_display_name: 'Owner'}]};
                await page.locator('[data-stream-together-refresh]').click();
                await page.evaluate(() => window.dispatchEvent(new Event('dashboard-stream-participants-changed')));
                await page.waitForFunction(() => document.querySelector('.dashboard-shared-chat-link').getAttribute('aria-disabled') === 'true');
                assert.equal(await headerSharedChat.getAttribute('href'), null);
                assert.equal(await headerSharedChat.getAttribute('aria-label'), 'Shared Chat is active');
                await page.waitForFunction(() => document.querySelector('.stream-together-session-actions a').href.includes('/other_host/'));
                assert.equal(await sharedChat.isVisible(), false);
                assert.equal(await page.locator('[data-stream-invite]').isVisible(), false, 'Guests do not get host invite controls');
                await page.getByRole('button', {name: 'Owner options', exact: true}).click();
                assert.equal(await page.getByRole('menuitem', {name: 'Kick', exact: true}).isVisible(), false, 'Guests cannot kick other participants');
                await page.keyboard.press('Escape');
                const guestPopup = page.waitForEvent('popup');
                await callHangup.click();
                const connectedCall = await guestPopup;
                await connectedCall.waitForURL('https://www.twitch.tv/popout/other_host/guest-star');
                assert.equal(await callHangup.getAttribute('aria-expanded'), 'false');
                assert.equal(await page.locator('#stream-call-hangup-status').innerText(), 'Guests must leave the call from Twitch.');
                await connectedCall.close();
                await page.locator('[data-stream-together-close]').click();
                const stripGuestPopup = page.waitForEvent('popup');
                await stripHangup.click();
                const stripCall = await stripGuestPopup;
                await stripCall.waitForURL('https://www.twitch.tv/popout/other_host/guest-star');
                assert.equal(await stripHangup.getAttribute('aria-expanded'), 'false');
                assert.equal(await page.locator('#stream-strip-hangup-status').innerText(), 'Guests must leave the call from Twitch.');
                assert.equal(actions.length, 5, 'Guest hang-up only opens Twitch');
                await stripCall.close();
                call.is_host = true;
                call.session = {id: 'strip-call', guests: []};
                await stripHangup.click();
                await page.getByRole('button', {name: 'End call', exact: true}).click();
                await page.getByRole('button', {name: 'End call', exact: true}).waitFor({state: 'hidden'});
                assert.equal(actions[5].session_id, 'strip-call');
                assert.equal(await page.locator('[data-stream-together]').evaluate(dialog => dialog.open), false);
                sharedChatActive = false;
                await page.locator('[data-stream-together-open]').first().click();
                const guestSetup = page.getByRole('region', {name: 'Join a call', exact: true});
                await guestSetup.getByText('Accept the call invite on Twitch first', {exact: false}).waitFor();
                assert.equal(await page.getByRole('region', {name: 'Host a call', exact: true})
                    .getByRole('button', {name: 'Start a call', exact: true}).isVisible(), true);
                joined = true;
                await guestSetup.getByRole('button', {name: 'Refresh', exact: true}).click();
                await page.getByRole('button', {name: 'Expand Another', exact: true}).waitFor();
                assert.equal(await page.locator('.stream-call-card[data-user-id="4"] small').innerText(), 'Host');
                await page.locator('[data-stream-participant-icons] [data-channel="another"]').waitFor();
                assert.equal(actions.length, 6, 'Refreshing only detects the existing call');
                assert.equal(await page.evaluate(() => streams.length), 0);
                guestDetected = sharedChatActive = joined = false;
                await page.goto('http://dashboard.test/channel/stream-together');
                const guestsPath = '/channel/api/stream-together/guests';
                const participantsPath = '/channel/api/stream-together/participants';
                const queuePath = '/channel/api/viewer-queue';
                assert.equal(await page.evaluate(({participantsPath, queuePath}) => {
                    window.dispatchEvent(new Event('dashboard-stream-participants-changed'));
                    return fetched.some(path => path === participantsPath || path === queuePath);
                }, {participantsPath, queuePath}), false, 'The call view skips dashboard polling');
                const sidebar = page.locator('#channel-navigation');
                assert.equal(await sidebar.isVisible(), true);
                const chatLayout = page.locator('#stream-together-chat');
                await page.getByRole('button', {name: 'Hide chat', exact: true}).click();
                assert.equal(await chatLayout.isVisible(), false);
                await page.getByRole('button', {name: 'Show chat', exact: true}).click();
                assert.equal(await chatLayout.isVisible(), true);
                assert.equal(await chatLayout.locator('.dashboard-header-stats > :visible').count(), 5);
                await chatLayout.getByText('No ad scheduled', {exact: true}).waitFor();
                const callBox = await page.locator('[data-stream-together]').boundingBox();
                const navBox = await sidebar.boundingBox();
                assert.ok(callBox.y + callBox.height <= 845);
                if (width === 1200) {
                    assert.ok(callBox.x >= navBox.x + navBox.width);
                    const chatBox = await chatLayout.locator('.live-chat-panel').boundingBox();
                    assert.ok(Math.abs(callBox.y + callBox.height - chatBox.y - chatBox.height) < 1);
                } else assert.ok(callBox.y >= navBox.y + navBox.height);
                await page.getByRole('combobox', {name: 'Twitch host or call link'}).fill('https://www.twitch.tv/popout/another/guest-star');
                await page.getByRole('button', {name: 'Show call', exact: true}).click();
                await page.getByRole('button', {name: 'Expand Another', exact: true}).waitFor();
                await page.getByRole('textbox', {name: 'Chat message'}).fill('unsent draft');
                await page.evaluate(() => {
                    window.mountedChat = document.querySelector('.live-chat-panel');
                    mountedChat.querySelector('[data-live-chat-feed]').scrollTop = 64;
                });
                if (width === 390) await page.emulateMedia({reducedMotion: 'reduce'});
                const expandingBubbles = await page.getByRole('link', {name: 'Return to dashboard'}).evaluate(link => {
                    link.click();
                    return [...document.querySelectorAll('.dashboard-header-stats .dashboard-header-stat')]
                        .filter(bubble => bubble.getAnimations().some(animation => {
                            const frames = animation.effect.getKeyframes();
                            const scale = Number(frames[0].transform?.match(/scaleX\(([^)]+)\)/)?.[1]);
                            return scale < 1 && frames.every(frame => frame.opacity === undefined);
                        })).length;
                });
                if (width === 1200) assert.ok(expandingBubbles > 0, 'Individual bubbles grow into the available space');
                else assert.equal(expandingBubbles, 0);
                await page.locator('.stream-together-stats-exit').waitFor({state: 'detached'});
                await page.waitForURL('http://dashboard.test/channel');
                assert.equal(await page.evaluate(({participantsPath, queuePath, guestsPath}) => {
                    if (!fetched.includes(participantsPath) || !fetched.includes(queuePath)) return false;
                    const count = fetched.filter(path => path === guestsPath).length;
                    window.dispatchEvent(new Event('dashboard-stream-participants-changed'));
                    return fetched.filter(path => path === guestsPath).length === count;
                }, {participantsPath, queuePath, guestsPath}), true, 'The dashboard resumes its own requests and pauses call requests');
                assert.equal(await page.evaluate(() => mountedChat === document.querySelector('.channel-dashboard-layout .live-chat-panel')), true);
                if (width === 390) assert.equal(await page.evaluate(() => Boolean(mountedChat.closest('.dashboard-carousel-slide'))), true);
                assert.equal(await page.getByRole('textbox', {name: 'Chat message'}).inputValue(), 'unsent draft');
                await page.goBack();
                await page.waitForURL('http://dashboard.test/channel/stream-together');
                assert.equal(await chatLayout.isVisible(), true);
                assert.equal(await page.evaluate(() => mountedChat.querySelector('[data-live-chat-feed]').scrollTop), 64);
                assert.equal(await page.getByRole('textbox', {name: 'Chat message'}).inputValue(), 'unsent draft');
                await page.goForward();
                await page.waitForURL('http://dashboard.test/channel');
                const statsExpand = await page.locator('.navigation a[href="/channel/stream-together"]').evaluate(link => {
                    link.click();
                    return document.querySelector('#stream-together-chat [data-ad-status-mirror]').getAnimations().some(animation => {
                        const frames = animation.effect.getKeyframes();
                        return frames[0].transform.includes('scaleX(0)') &&
                            frames.every(frame => frame.opacity === undefined);
                    });
                });
                assert.equal(statsExpand, width === 1200);
                await page.waitForURL('http://dashboard.test/channel/stream-together');
                assert.equal(await page.evaluate(() => mountedChat === document.querySelector('#stream-together-chat .live-chat-panel')), true);
                assert.deepEqual(errors, []);
                await page.close();
            }
        } finally { await browser.close(); }
    });
