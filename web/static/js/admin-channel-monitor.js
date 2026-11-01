(() => {
    'use strict';
    const root = document.querySelector('[data-admin-monitor]');
    if (!root) return;
    const status = root.querySelector('[data-monitor-status]');
    const pause = root.querySelector('[data-monitor-pause]');
    let paused = false, stopped = false, timer, controller, delay = 5000;
    function line(tag, text) {
        const node = document.createElement(tag);
        node.textContent = text || '';
        return node;
    }
    function render(key, entries) {
        const target = root.querySelector(`[data-monitor-feed="${key}"]`);
        const rows = (Array.isArray(entries) ? entries : []).slice(0, 100).map(entry => {
            const row = document.createElement('article');
            if (key === 'feed') {
                row.append(line('strong', entry.reward_title || entry.type || 'Check-in'),
                    line('p', [entry.user_label || entry.username, entry.redeemed_at].filter(Boolean).join(' · ')), line('p', entry.user_input));
            } else if (key === 'mod_actions') {
                row.append(line('strong', [entry.action, entry.target].filter(Boolean).join(' · ')),
                    line('p', [entry.moderator, entry.timestamp].filter(Boolean).join(' · ')),
                    line('p', entry.reason), line('p', entry.message));
            } else {
                row.append(line('strong', entry.display_name || entry.username), line('p', entry.message),
                    line('p', [entry.reason, entry.held_at].filter(Boolean).join(' · ')));
            }
            return row;
        });
        const position = target.scrollTop;
        target.replaceChildren(...(rows.length ? rows : [line('p', 'No activity yet.')]));
        target.scrollTop = position;
    }
    async function refresh() {
        clearTimeout(timer);
        if (paused || stopped || document.hidden || controller) return;
        controller = new AbortController();
        const timeout = setTimeout(() => controller?.abort(), 8000);
        try {
            const response = await fetch(root.dataset.stateUrl, {signal: controller.signal, headers: {Accept: 'application/json'}, cache: 'no-store'});
            if (response.status === 401 || response.status === 403 || response.redirected) {
                stopped = true; pause.disabled = true;
                status.textContent = 'Administrator session ended. Sign in again to continue.';
                return;
            }
            if (!response.ok) throw new Error('Unavailable');
            const state = await response.json();
            ['feed', 'mod_actions', 'automod'].forEach(key => render(key, state.activity?.[key]));
            root.querySelector('[data-monitor-live]').textContent = state.is_live ? 'Live' : 'Offline';
            window.dispatchEvent(new CustomEvent('dashboard-stream-live-changed', {detail: {isLive: state.is_live}}));
            status.textContent = `Updated ${new Date().toLocaleTimeString()}`;
            delay = 5000;
        } catch {
            if (!paused && !document.hidden) status.textContent = 'Activity unavailable. Retrying; the last activity remains visible.';
            delay = Math.min(delay * 2, 30000);
        } finally {
            clearTimeout(timeout); controller = null;
            if (!paused && !stopped && !document.hidden) timer = setTimeout(refresh, delay);
        }
    }
    pause.addEventListener('click', () => {
        paused = !paused;
        pause.textContent = paused ? 'Resume activity' : 'Pause activity';
        if (paused) { clearTimeout(timer); controller?.abort(); status.textContent = 'Activity paused. Stream and chat remain live.'; }
        else refresh();
    });
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) { clearTimeout(timer); controller?.abort(); }
        else refresh();
    });
    window.addEventListener('pagehide', () => { stopped = true; clearTimeout(timer); controller?.abort(); });
    refresh();
})();
