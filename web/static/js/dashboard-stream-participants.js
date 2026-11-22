(() => {
    const rail = document.querySelector('[data-stream-participants]');
    const mount = document.querySelector('[data-stream-player]');
    if (!rail || !mount) return;
    const own = mount.dataset.channel;
    const icons = rail.querySelector('[data-stream-participant-icons]');
    const card = rail.closest('.dashboard-video-card');
    const dashboard = card.closest('[data-dashboard-carousel]');
    const header = card.querySelector('.dashboard-video-header');
    const frame = card.querySelector('.dashboard-video-frame');
    const root = document.body.dataset.channelRoot || '/channel';
    const sharedChatShortcuts = [...document.querySelectorAll('[data-shared-chat-shortcut]')];
    const chatShortcut = sharedChatShortcuts.find(link => link.matches('.dashboard-shared-chat-link'));
    const ownCallUrl = chatShortcut?.getAttribute('href');
    const buttons = new Map();
    const sampleImage = document.createElement('img');
    sampleImage.className = 'dashboard-stream-test-image';
    let sampleEntries = null, liveEntries = [], liveSelection = own;
    let selected = own, request, stopped = false, positionFrame, rosterSignature;
    let streamTogetherActive = false, sharedChatActive = false, hostingCall = false;
    function updateSharedChatShortcuts() {
        if (dashboard?.hidden) return;
        if (chatShortcut) {
            chatShortcut.hidden = !streamTogetherActive || Boolean(sampleEntries);
            if (hostingCall && ownCallUrl) {
                chatShortcut.setAttribute('href', ownCallUrl);
                chatShortcut.removeAttribute('aria-disabled');
                chatShortcut.removeAttribute('role');
            } else {
                chatShortcut.removeAttribute('href');
                chatShortcut.setAttribute('aria-disabled', 'true');
                chatShortcut.setAttribute('role', 'link');
            }
        }
        const active = sharedChatActive && !sampleEntries;
        for (const shortcut of sharedChatShortcuts) {
            const guestIndicator = shortcut === chatShortcut && !hostingCall;
            const label = guestIndicator
                ? (active ? 'Shared Chat is active' : 'Only the host can start Shared Chat')
                : (active ? 'Shared Chat is active. Open Twitch call' : 'Start Shared Chat on Twitch');
            shortcut.classList.toggle('is-active', active);
            if (shortcut.getAttribute('aria-label') === label) continue;
            shortcut.setAttribute('aria-label', label);
            shortcut.title = label;
        }
    }
    const order = window.createDashboardParticipantOrder(icons, 'button', button => button.dataset.channel,
        () => render(sampleEntries ?? liveEntries), button => button.dataset.channel !== own);
    function positionStrip() {
        positionFrame = null;
        if (rail.hidden || stopped || dashboard?.hidden) return;
        const edge = header ? header.getBoundingClientRect().bottom : mount.getBoundingClientRect().top;
        const top = Math.max(0, edge - card.getBoundingClientRect().top - card.clientTop) + 8;
        const value = `${top}px`;
        if (rail.style.getPropertyValue('--stream-participants-top') !== value) rail.style.setProperty('--stream-participants-top', value);
        const style = getComputedStyle(icons);
        const available = Math.max(0, icons.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom));
        const count = buttons.size;
        if (count) {
            const gap = Math.min(8, available / (count * 4));
            const size = Math.min(42, (available - gap * (count - 1)) / count);
            icons.style.setProperty('--participant-gap', `${gap}px`);
            icons.style.setProperty('--participant-size', `${size}px`);
        }
    }
    function schedulePosition() { if (!positionFrame && !stopped) positionFrame = requestAnimationFrame(positionStrip); }
    const observer = new ResizeObserver(schedulePosition);
    observer.observe(card); observer.observe(mount);
    observer.observe(icons);
    if (header) observer.observe(header, {box: 'border-box'});
    function select(login, force = false) {
        if (!force && selected === login) return;
        selected = login;
        buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.live === 'true' && button.dataset.channel === selected)));
        const sample = sampleEntries?.find(entry => entry.login === login);
        if (sample) {
            sampleImage.src = sample.thumbnail_url;
            sampleImage.alt = `${sample.display_name} · ${sample.is_streaming ? 'Simulated live preview' : 'Simulated offline preview'}`;
            if (sampleImage.parentNode !== mount) mount.append(sampleImage);
        } else sampleImage.remove();
        window.dispatchEvent(new CustomEvent('dashboard-stream-preview-select', {detail: {channel: login, simulated: Boolean(sample)}}));
    }
    function render(entries) {
        if (!Array.isArray(entries)) return;
        const valid = entries.filter(entry => /^[0-9]{1,25}$/.test(entry.id) && /^[a-zA-Z0-9_]{1,25}$/.test(entry.login))
            .sort((left, right) => Number(right.login === own) - Number(left.login === own)
                || Number(right.is_streaming === true) - Number(left.is_streaming === true));
        order.sort(valid, entry => entry.login);
        valid.sort((left, right) => Number(right.login === own) - Number(left.login === own));
        const ids = new Set(valid.map(entry => entry.id));
        buttons.forEach((button, id) => { if (!ids.has(id)) { button.remove(); buttons.delete(id); } });
        const focused = document.activeElement;
        for (const [index, entry] of valid.entries()) {
            let button = buttons.get(entry.id);
            if (!button) {
                button = document.createElement('button'); button.type = 'button';
                const image = document.createElement('img'); image.alt = ''; image.width = image.height = 36; image.decoding = 'async';
                const fallback = document.createElement('span'); fallback.setAttribute('aria-hidden', 'true');
                image.addEventListener('error', () => { image.hidden = true; fallback.hidden = false; });
                button.append(image, fallback);
                button.addEventListener('click', () => {
                    if (button.dataset.live === 'true') select(button.dataset.channel);
                });
                buttons.set(entry.id, button); icons.append(button);
            }
            button.dataset.channel = entry.login;
            const displayName = entry.display_name || entry.login;
            const label = displayName.toLocaleLowerCase() === entry.login.toLocaleLowerCase()
                ? entry.login : `${displayName}\n(${entry.login})`;
            const live = entry.is_streaming === true;
            button.dataset.live = String(live);
            button.setAttribute('aria-disabled', String(!live));
            button.tabIndex = live ? 0 : -1;
            button.title = label;
            button.setAttribute('aria-label', label);
            button.setAttribute('aria-pressed', String(live && entry.login === selected));
            const image = button.querySelector('img'), fallback = button.querySelector('span');
            const url = sampleEntries || entry.profile_image_url?.startsWith('https://') ? entry.profile_image_url || '' : '';
            if (image.getAttribute('src') !== url) {
                image.hidden = !url; fallback.hidden = Boolean(url);
                if (url) image.src = url; else image.removeAttribute('src');
            }
            fallback.textContent = (entry.display_name || entry.login).slice(0, 1).toUpperCase();
            if (icons.children[index] !== button) icons.insertBefore(button, icons.children[index] || null);
        }
        if (icons.contains(focused) && document.activeElement !== focused) focused.focus({preventScroll: true});
        if (!valid.some(entry => entry.login === selected && entry.is_streaming === true)) select(own);
        rail.hidden = valid.length === 0;
        frame.classList.toggle('has-participants', !rail.hidden);
        schedulePosition();
    }
    async function refresh() {
        if (stopped || request || sampleEntries || document.hidden || dashboard?.hidden) return;
        const controller = new AbortController(); request = controller;
        try {
            const response = await fetch(`${root}/api/stream-together/participants`, {signal: controller.signal, cache: 'no-store'});
            if (!response.ok) return;
            const data = await response.json();
            if (!stopped && !controller.signal.aborted && Array.isArray(data.participants)) {
                streamTogetherActive = data.active === true;
                hostingCall = data.is_host === true;
                sharedChatActive = data.shared_chat_active === true;
                updateSharedChatShortcuts();
                const signature = JSON.stringify(data.participants);
                if (signature !== rosterSignature) {
                    rosterSignature = signature;
                    liveEntries = data.participants;
                    render(liveEntries);
                }
            }
        } catch (_) { /* Keep the current selection during a temporary connection failure. */ }
        finally { if (request === controller) request = null; }
    }
    window.addEventListener('dashboard-stream-together-test-changed', event => {
        if (event.detail) {
            if (!sampleEntries) liveSelection = selected;
            request?.abort(); request = null;
            sampleEntries = event.detail.map(guest => ({id: guest.user_id,
                login: String(guest.slot_id) === '0' ? own : guest.user_login,
                display_name: guest.user_display_name, profile_image_url: guest.profile_image_url,
                thumbnail_url: guest.thumbnail_url, is_streaming: guest.is_streaming}));
            render(sampleEntries);
            select(selected, true);
        } else if (sampleEntries) {
            sampleEntries = null;
            render(liveEntries);
            select(liveEntries.some(entry => entry.login === liveSelection && entry.is_streaming === true) ? liveSelection : own, true);
            refresh();
        }
        updateSharedChatShortcuts();
    });
    window.addEventListener('dashboard-stream-participants-changed', refresh);
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    document.addEventListener('dashboard-view-changed', () => {
        if (dashboard?.hidden) {
            request?.abort();
            request = null;
        } else {
            updateSharedChatShortcuts();
            schedulePosition();
            refresh();
        }
    });
    const timer = window.setInterval(refresh, 30000);
    window.addEventListener('beforeunload', () => { stopped = true; order.destroy(); request?.abort(); window.clearInterval(timer); observer.disconnect(); cancelAnimationFrame(positionFrame); });
    refresh();
})();
