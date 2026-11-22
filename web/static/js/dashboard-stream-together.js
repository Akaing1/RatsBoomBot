(() => {
    const dialog = document.querySelector('[data-stream-together]');
    if (!dialog) return;
    const refreshButton = dialog.querySelector('[data-stream-together-refresh]');
    const layout = document.querySelector('.channel-dashboard-layout');
    const chat = document.querySelector('.live-chat-panel');
    const root = document.documentElement;
    const channelRoot = document.body.dataset.channelRoot || '/channel';
    const standalone = dialog.hasAttribute('data-stream-together-page');
    const standaloneLayout = dialog.closest('[data-stream-together-layout]');
    const switchable = Boolean(standaloneLayout && layout && chat);
    const stats = switchable ? document.querySelector('.dashboard-header-side') : null;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const dashboardTitle = document.title.trim();
    const dashboardPath = channelRoot;
    const callPath = `${channelRoot}/stream-together`;
    const chatToggle = dialog.querySelector('[data-stream-chat-toggle]');
    const chatArea = document.getElementById('stream-together-chat');
    const feed = chat?.querySelector('[data-live-chat-feed]');
    let chatScroll;
    function rememberChatScroll() {
        if (feed?.getClientRects().length) {
            chatScroll = {top: feed.scrollTop, atEnd: feed.scrollHeight - feed.clientHeight - feed.scrollTop <= 24};
        }
    }
    function restoreChatScroll() {
        if (feed && chatScroll) feed.scrollTop = chatScroll.atEnd ? feed.scrollHeight : chatScroll.top;
    }
    chatToggle?.addEventListener('click', () => {
        rememberChatScroll();
        chatArea.hidden = !chatArea.hidden;
        standaloneLayout.classList.toggle('is-chat-hidden', chatArea.hidden);
        chatToggle.setAttribute('aria-expanded', String(!chatArea.hidden));
        const label = chatArea.hidden ? 'Show chat' : 'Hide chat';
        chatToggle.setAttribute('aria-label', label);
        chatToggle.title = label;
        if (!chatArea.hidden) restoreChatScroll();
    });
    const sampleKey = `stream-together-preview:${dialog.dataset.channelId}`;
    const callRefresh = dialog.querySelector('[data-stream-call-refresh]');
    let pendingHangup, ending = false;
    let controls, opener, timer, dockFrame, sample = null;
    function setSample(data) {
        cancelHangup();
        sample = data;
        try {
            if (sample) sessionStorage.setItem(sampleKey, JSON.stringify(sample));
            else sessionStorage.removeItem(sampleKey);
        } catch (_) { /* Preview still works on this page. */ }
        window.dispatchEvent(new CustomEvent('dashboard-stream-together-test-changed', {detail: sample?.session.guests ?? null}));
    }
    function stopTest() {
        controls?.simulate(null);
        setSample(null);
        return 'Stream Together test mode off.';
    }
    async function endCall(sessionId) {
        const response = await fetch(`${channelRoot}/api/stream-together/control`, {
            method: 'POST',
            body: new URLSearchParams({action: 'end', session_id: sessionId, csrf_token: dialog.dataset.csrfToken})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Could not end the call.');
        controls?.sessionEnded();
        window.dispatchEvent(new CustomEvent('dashboard-stream-participants-changed'));
    }
    function cancelHangup(restoreFocus = false) {
        if (!pendingHangup || ending) return;
        const {button, wrapper, confirmHangup, hangupStatus, request} = pendingHangup;
        pendingHangup = null;
        request.abort();
        wrapper.classList.remove('is-confirming');
        confirmHangup.disabled = true;
        hangupStatus.textContent = '';
        button.setAttribute('aria-expanded', 'false');
        if (restoreFocus && button.getClientRects().length) button.focus();
    }
    async function requestEnd(button, state) {
        if (ending) return;
        if (pendingHangup?.button === button && pendingHangup.run) {
            cancelHangup(true);
            return;
        }
        cancelHangup();
        const wrapper = button.closest('.stream-hangup-action');
        const confirmHangup = wrapper.querySelector('.stream-hangup-confirm');
        const hangupStatus = wrapper.querySelector('[role="status"]');
        const request = new AbortController();
        const pending = {button, wrapper, confirmHangup, hangupStatus, request, run: null};
        pendingHangup = pending;
        confirmHangup.disabled = true;
        confirmHangup.setAttribute('aria-label', 'End call');
        if (sample) {
            hangupStatus.textContent = 'End the simulated call?';
            confirmHangup.setAttribute('aria-label', 'End test');
            pending.run = stopTest;
        } else {
            try {
                if (!state) {
                    hangupStatus.textContent = 'Checking the current call…';
                    const response = await fetch(`${channelRoot}/api/stream-together/guests`, {signal: request.signal, cache: 'no-store'});
                    state = await response.json();
                    if (!response.ok) throw new Error(state.detail || 'Could not check the current call.');
                }
                if (request.signal.aborted) return;
                if (!state.session) {
                    hangupStatus.textContent = 'There is no active Stream Together call to end.';
                } else if (state.is_host === false) {
                    if (/^https:\/\/www\.twitch\.tv\/popout\/[a-z0-9_]{1,25}\/guest-star$/i.test(state.call_url || '')) {
                        hangupStatus.textContent = state.host_id === dialog.dataset.channelId
                            ? 'End the call from Twitch.' : 'Guests must leave the call from Twitch.';
                        const callTab = window.open('about:blank', '_blank');
                        if (callTab) {
                            callTab.opener = null;
                            callTab.location.replace(state.call_url);
                        } else {
                            const link = document.createElement('a');
                            link.href = state.call_url;
                            link.target = '_blank';
                            link.rel = 'noopener noreferrer';
                            link.textContent = 'Open Twitch call';
                            hangupStatus.append(' ', link);
                        }
                        return;
                    }
                    hangupStatus.textContent = 'The Twitch call link is unavailable.';
                } else {
                    hangupStatus.textContent = 'This ends the call for everyone.';
                    pending.run = () => endCall(state.session.id);
                }
            } catch (error) {
                if (!request.signal.aborted) hangupStatus.textContent = error.message;
            }
        }
        if (pendingHangup !== pending || !pending.run) return;
        wrapper.classList.add('is-confirming');
        button.setAttribute('aria-expanded', 'true');
        confirmHangup.disabled = false;
        confirmHangup.title = confirmHangup.getAttribute('aria-label');
        if (pending.run && document.activeElement === button) confirmHangup.focus({preventScroll: true});
    }
    for (const button of document.querySelectorAll('[data-stream-request-end], [data-stream-action="end"]')) {
        const wrapper = document.createElement('div');
        wrapper.className = 'stream-hangup-action';
        const track = document.createElement('div');
        track.className = 'stream-hangup-track';
        const confirm = document.createElement('button');
        confirm.type = 'button';
        confirm.className = 'stream-hangup-confirm';
        confirm.disabled = true;
        const cross = document.createElement('span');
        cross.setAttribute('aria-hidden', 'true');
        cross.textContent = '×';
        confirm.append(cross);
        const status = document.createElement('p');
        status.className = 'stream-hangup-status';
        status.setAttribute('role', 'status');
        button.setAttribute('aria-expanded', 'false');
        button.before(wrapper);
        track.append(button, confirm);
        wrapper.append(track, status);
        status.id = button.hasAttribute('data-stream-request-end') ? 'stream-strip-hangup-status' : 'stream-call-hangup-status';
        confirm.setAttribute('aria-describedby', status.id);
        confirm.addEventListener('click', async () => {
            const pending = pendingHangup;
            if (!pending?.run || pending.confirmHangup !== confirm || ending) return;
            ending = confirm.disabled = true;
            try {
                await pending.run();
                ending = false;
                cancelHangup(true);
            } catch (error) {
                status.textContent = error.message;
                confirm.disabled = false;
            } finally {
                ending = false;
            }
        });
    }
    document.addEventListener('pointerdown', event => {
        if (pendingHangup && !pendingHangup.wrapper.contains(event.target)) cancelHangup();
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && pendingHangup) {
            event.preventDefault();
            event.stopPropagation();
            cancelHangup(true);
        }
    }, true);
    const stripHangup = document.querySelector('[data-stream-request-end]');
    stripHangup?.addEventListener('click', () => requestEnd(stripHangup));
    function position() {
        dockFrame = null;
        if (standalone || !dialog.open) return;
        const viewport = window.visualViewport;
        const x = viewport?.offsetLeft || 0, y = viewport?.offsetTop || 0;
        const width = viewport?.width || innerWidth, height = viewport?.height || innerHeight;
        const bounds = layout?.getBoundingClientRect();
        const nav = document.querySelector('.sidebar')?.getBoundingClientRect();
        const left = Math.max(x + 8, Math.min(bounds?.left || x + 8, x + width - 240));
        const right = x + width - 8;
        const top = Math.max(y + 8, bounds?.top || 0, nav && nav.width > width * .7 && nav.height < 120 ? nav.bottom + 8 : 0);
        const bottom = y + height - 8;
        let callWidth = right - left, callHeight = bottom - top;
        if (chat) {
            const area = chat.getBoundingClientRect();
            if (area.width && area.height && area.top < bottom && area.bottom > top) {
                if (area.left > left + 200 && area.left < right) callWidth = area.left - left - 12;
                else if (area.top > top && area.top < bottom) callHeight = area.top - top - 8;
            }
        }
        for (const [name, value] of Object.entries({left, top, width: callWidth, height: callHeight})) dialog.style.setProperty(`--stream-call-${name}`, `${value}px`);
    }
    function schedulePosition() { if (!standalone && dialog.open && !dockFrame) dockFrame = requestAnimationFrame(position); }
    const observer = new ResizeObserver(schedulePosition);
    if (layout) observer.observe(layout);
    if (chat) observer.observe(chat);
    layout?.addEventListener('transitionend', schedulePosition);
    window.addEventListener('resize', schedulePosition);
    window.addEventListener('scroll', schedulePosition, {passive: true});
    window.visualViewport?.addEventListener('resize', schedulePosition);
    window.visualViewport?.addEventListener('scroll', schedulePosition);
    async function refresh(manual = false) {
        if (!controls || refreshButton.disabled || document.hidden || (switchable && standaloneLayout.hidden)) return;
        const current = controls;
        refreshButton.disabled = callRefresh.disabled = true;
        try {
            await current.refresh(false, manual === true);
            if (manual === true && controls === current) {
                window.dispatchEvent(new CustomEvent('dashboard-stream-participants-changed'));
            }
        } finally {
            if (controls === current) refreshButton.disabled = callRefresh.disabled = false;
        }
    }
    function startPolling() {
        refresh();
        timer = window.setInterval(refresh, 10000);
    }
    function open(button) {
        if (controls) { if (sample) controls.simulate(sample); return; }
        opener = button;
        if (!dialog.open) dialog.show();
        document.dispatchEvent(new CustomEvent('dashboard-stream-together-opened'));
        if (!standalone) root.classList.add('stream-together-open');
        position();
        controls = window.createStreamTogetherControls(dialog, setSample, requestEnd);
        if (sample) controls.simulate(sample);
        refreshButton.disabled = callRefresh.disabled = false;
        startPolling();
    }
    document.querySelectorAll('[data-stream-together-open]').forEach(button => button.addEventListener('click', () => {
        if (location.hash !== '#stream-together') history.pushState(null, '', '#stream-together');
        open(button);
    }));
    let mountedInCall = false;
    let statAnimations = [], departingAd;
    const homePositions = new Map();
    const statsMotion = {duration: 200, easing: 'ease-out'};
    const adStat = stats?.querySelector('[data-ad-status-mirror]');
    const statBubbles = [...stats?.querySelectorAll('.dashboard-header-stat, [data-ad-status-mirror]') || []];
    function measureStats() {
        const positions = new Map();
        for (const bubble of statBubbles) {
            if (bubble === adStat && !bubble.classList.contains('is-visible')) continue;
            const rect = bubble.getBoundingClientRect();
            if (rect.width && rect.height) positions.set(bubble, rect);
        }
        return positions;
    }
    function collapseAd({left, top, width, height}) {
        const exit = document.createElement('div');
        exit.className = 'dashboard-header-stats stream-together-stats-exit';
        exit.inert = true;
        exit.setAttribute('aria-hidden', 'true');
        const bubble = adStat.cloneNode(true);
        bubble.removeAttribute('data-ad-status-mirror');
        exit.append(bubble);
        Object.assign(exit.style, {left: `${left}px`, top: `${top}px`, width: `${width}px`, height: `${height}px`});
        document.body.append(exit);
        departingAd = exit;
        bubble.animate([{transform: 'scaleX(1)'}, {transform: 'scaleX(0)'}], statsMotion).onfinish = () => {
            exit.remove();
            if (departingAd === exit) departingAd = null;
        };
    }
    function resizeStatBubbles(before) {
        const after = measureStats();
        if (before.has(adStat) && !after.has(adStat)) collapseAd(before.get(adStat));
        for (const [bubble, current] of after) {
            const previous = before.get(bubble);
            // The mobile navbar and the call's chat column are separate placements.
            const offset = previous && Math.abs(previous.top - current.top) < 48 ? previous.left - current.left : 0;
            const scale = previous ? previous.width / current.width : 0;
            if (Math.abs(offset) < 0.5 && Math.abs(scale - 1) < 0.01) continue;
            const transformOrigin = previous ? 'left center' : 'right center';
            statAnimations.push(bubble.animate([
                {transform: `translateX(${offset}px) scaleX(${scale})`, transformOrigin},
                {transform: 'translateX(0) scaleX(1)', transformOrigin}
            ], statsMotion));
        }
    }
    function switchView(focus = false) {
        const inCall = location.pathname.replace(/\/$/, '') === callPath;
        if (inCall === mountedInCall && layout.hidden === inCall) return;
        rememberChatScroll();
        const animateStats = !reduceMotion.matches && Boolean(stats);
        const before = animateStats ? measureStats() : null;
        statAnimations.forEach(animation => animation.cancel());
        statAnimations = [];
        departingAd?.remove();
        departingAd = null;
        if (animateStats) stats.classList.add('is-switching-stats');
        mountedInCall = inCall;
        document.body.classList.toggle('channel-page-overview', !inCall);
        document.body.classList.toggle('channel-page-stream-together', inCall);
        layout.hidden = inCall;
        standaloneLayout.hidden = !inCall;
        document.querySelector('[data-setup-welcome]')?.toggleAttribute('hidden', inCall);
        if (inCall) {
            for (const element of [stats, chat]) {
                if (!element) continue;
                const marker = document.createComment('dashboard panel position');
                element.before(marker);
                homePositions.set(element, marker);
                chatArea.append(element);
            }
        } else {
            for (const [element, marker] of homePositions) marker.replaceWith(element);
            homePositions.clear();
            cancelHangup();
        }
        const selectedPath = inCall ? callPath : dashboardPath;
        for (const link of document.querySelectorAll('.navigation .nav-link')) {
            if (link.pathname !== callPath && link.pathname !== dashboardPath) continue;
            const active = link.pathname === selectedPath;
            link.classList.toggle('active', active);
            if (active) link.setAttribute('aria-current', 'page');
            else link.removeAttribute('aria-current');
        }
        document.title = inCall ? 'Stream Together | RatsBoomBot' : dashboardTitle;
        document.dispatchEvent(new CustomEvent('dashboard-view-changed', {detail: {streamTogether: inCall}}));
        if (before) {
            resizeStatBubbles(before);
            stats.classList.remove('is-switching-stats');
        }
        restoreChatScroll();
        if (inCall) {
            if (controls) {
                controls.syncSharedChat();
                startPolling();
            } else open();
            if (focus) dialog.querySelector('#stream-together-title')?.focus({preventScroll: true});
        } else {
            window.clearInterval(timer);
            controls?.pause();
            if (focus) document.querySelector('.navigation .nav-link[aria-current="page"]')?.focus({preventScroll: true});
        }
    }
    if (switchable) {
        document.addEventListener('click', event => {
            if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            const link = event.target.closest('a[href]');
            if (!link || link.target || link.hasAttribute('download') || link.origin !== location.origin || link.search || link.hash) return;
            if (link.pathname !== dashboardPath && link.pathname !== callPath) return;
            event.preventDefault();
            if (link.href !== location.href) history.pushState(null, '', link.href);
            switchView(true);
        });
        window.addEventListener('popstate', () => switchView());
    }
    for (const button of [refreshButton, callRefresh]) button.addEventListener('click', () => refresh(true));
    window.addEventListener('dashboard-stream-participants-changed', refresh);
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
    dialog.querySelector('[data-stream-together-close]')?.addEventListener('click', () => dialog.close());
    dialog.addEventListener('keydown', event => {
        if (event.key === 'Escape' && !event.defaultPrevented) {
            event.preventDefault();
            const menu = dialog.querySelector('.stream-call-participant-menu:popover-open');
            if (menu) menu.hidePopover();
            else if (!standalone) dialog.close();
        }
    });
    dialog.addEventListener('close', () => {
        if (dialog.contains(pendingHangup?.button)) cancelHangup();
        window.clearInterval(timer); controls?.destroy(); controls = null;
        cancelAnimationFrame(dockFrame); dockFrame = null;
        root.classList.remove('stream-together-open');
        if (location.hash === '#stream-together') history.replaceState(null, '', location.pathname + location.search);
        opener?.focus();
    });
    function syncHash() { if (standalone) return; if (location.hash === '#stream-together') open(); else if (dialog.open) dialog.close(); }
    window.addEventListener('hashchange', syncHash); window.addEventListener('popstate', syncHash);
    window.addEventListener('beforeunload', () => { window.clearInterval(timer); controls?.destroy(); observer.disconnect(); cancelAnimationFrame(dockFrame); });
    function startTest(count = 6, online = Math.max(0, count - 1)) {
        if (!Number.isInteger(count) || count < 1 || count > 6 || !Number.isInteger(online) || online < 0 || online > count) {
            throw new Error('Use dashboardStreamTogetherTest.start(1–6, onlineCount), or dashboardStreamTogetherTest.stop().');
        }
        const guests = Array.from({length: count}, (_, index) => {
            const color = ['#7653bf', '#397779', '#aa557c', '#576b9d', '#9a783f', '#665979'][index];
            const own = index === 0;
            const testName = window.dashboardTestNames[own ? 0 : index - 1];
            const art = `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"><rect width="640" height="360" fill="${color}"/><circle cx="320" cy="145" r="55" fill="#ffffff30"/><path d="M190 300a130 110 0 0 1 260 0" fill="#ffffff30"/></svg>`)}`;
            return {user_id: own && dialog.dataset.channelId ? dialog.dataset.channelId : String(9000000000 + index),
                user_login: own && dialog.dataset.channelLogin ? dialog.dataset.channelLogin : testName,
                user_display_name: own && dialog.dataset.channelName ? dialog.dataset.channelName : testName,
                slot_id: String(index), is_live: true, is_streaming: index < online, test_mode: true, volume: 70,
                thumbnail_url: art, profile_image_url: own && dialog.dataset.channelAvatar ? dialog.dataset.channelAvatar : art,
                audio_settings: {is_host_enabled: true}, video_settings: {is_host_enabled: true}};
        });
        setSample({state: 'active', slot_count: 6, session: {id: 'local-test', guests}, invites: []});
        if (switchable && !mountedInCall) {
            history.pushState(null, '', callPath);
            switchView();
        } else {
            if (!standalone && location.hash !== '#stream-together') history.pushState(null, '', '#stream-together');
            open();
        }
        return `Showing ${count} simulated participants (${online} online). Use dashboardStreamTogetherTest.stop() to stop.`;
    }
    window.dashboardStreamTogetherTest = {
        start: startTest,
        stop: stopTest
    };
    try {
        const saved = JSON.parse(sessionStorage.getItem(sampleKey));
        if (saved?.session?.id === 'local-test' && Array.isArray(saved.session.guests)) setSample(saved);
    } catch (_) { /* Ignore an unavailable preview. */ }
    if (switchable) {
        if (location.hash === '#stream-together') history.replaceState(null, '', callPath);
        switchView();
    } else if (standalone) open();
    else syncHash();
})();
