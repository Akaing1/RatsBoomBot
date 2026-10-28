(() => {
    const host = document.querySelector('[data-engagement-cards]');
    const dialog = document.querySelector('[data-engagement-summary]');
    if (!host || !dialog) return;
    const creator = document.querySelector('[data-engagement]');
    const title = dialog.querySelector('[data-engagement-summary-title]');
    const state = dialog.querySelector('[data-engagement-summary-state]');
    const options = dialog.querySelector('[data-engagement-summary-options]');
    const status = dialog.querySelector('[data-engagement-summary-status]');
    const lock = dialog.querySelector('[data-engagement-summary-lock]');
    const resolve = dialog.querySelector('[data-engagement-summary-resolve]');
    const remove = dialog.querySelector('[data-engagement-summary-delete]');
    const createNew = dialog.querySelector('[data-engagement-summary-new]');
    const repeat = dialog.querySelector('[data-engagement-summary-repeat]');
    const confirmation = dialog.querySelector('[data-engagement-summary-confirm]');
    const records = new Map();
    const requests = new Map();
    const totalsCache = new WeakMap();
    const storageKey = `dashboard-engagement-active:${host.dataset.channelId}:v1`;
    let current = null, pendingAction = null, busy = false, backdropPress = false;
    let summaryReturn = null, summaryOpener = null;
    const valid = item => ['polls', 'predictions'].includes(item?.kind) && /^[A-Za-z0-9_-]{1,100}$/.test(item?.id || '');
    const label = item => item.kind === 'polls' ? 'Poll' : 'Prediction';
    const active = item => ['ACTIVE', 'LOCKED'].includes(item.status);
    function setText(node, value) { if (node.textContent !== value) node.textContent = value; }
    function remember() {
        try { localStorage.setItem(storageKey, JSON.stringify([...records.values()].map(({item}) => ({kind: item.kind, id: item.id})))); } catch (_) {}
    }
    function message(text, error = false) { status.textContent = text; status.style.color = error ? 'var(--danger)' : ''; }
    function description(item) {
        if (item.status === 'ACTIVE') {
            const start = Date.parse(item.created_at), remaining = Math.max(0, Math.ceil((start + Number(item.duration) * 1000 - Date.now()) / 1000));
            if (!Number.isFinite(start)) return 'Voting open';
            return remaining ? `${Math.floor(remaining / 60)}m${remaining % 60}s left` : item.kind === 'predictions' ? 'Awaiting outcome' : 'Finishing…';
        }
        return {LOCKED: 'Awaiting outcome', RESOLVED: 'Resolved', CANCELED: 'Cancelled · points refunded',
            COMPLETED: 'Completed', TERMINATED: 'Closed', ARCHIVED: 'Archived'}[item.status] || item.status;
    }
    function updateCard(record) {
        if (!record.card) return;
        setText(record.heading, record.item.title || label(record.item));
        updateCardDescription(record);
        record.buttons.forEach(button => { if (button.disabled !== busy) button.disabled = busy; });
        renderMiniChart(record);
        renderQuickPreview(record);
    }
    function updateCardDescription(record) {
        if (record.card) setText(record.description, `${label(record.item)} · ${record.error || description(record.item)}`);
    }
    function resultTotals(item) {
        if (!item.options) return {votes: 0, points: 0};
        let totals = totalsCache.get(item.options);
        if (!totals) {
            totals = item.options.reduce((total, option) => {
                total.votes += option.votes || 0; total.points += option.points || 0; return total;
            }, {votes: 0, points: 0});
            totalsCache.set(item.options, totals);
        }
        return totals;
    }
    function summaryDescription(item) {
        const totals = resultTotals(item);
        return `${description(item)} · ` + (item.kind === 'polls' ? `${totals.votes.toLocaleString()} total votes` : `${totals.votes.toLocaleString()} total predictions · ${totals.points.toLocaleString()} total points`);
    }
    function resultShare(item, option) {
        const field = item.kind === 'polls' ? 'votes' : 'points', total = resultTotals(item)[field];
        return total ? Math.round((option[field] || 0) / total * 100) : 0;
    }
    function renderMiniChart(record) {
        const signature = JSON.stringify(record.item.options);
        if (record.miniSignature === signature) return;
        record.miniSignature = signature;
        const chart = record.card.querySelector('.engagement-mini-chart'), results = record.item.options || [];
        const descriptions = [];
        for (const [index, option] of results.entries()) {
            let bar = chart.children[index];
            if (!bar) {
                bar = document.createElement('div');
                const fill = document.createElement('div');
                bar.append(fill, document.createElement('small'), document.createElement('span')); chart.append(bar);
            }
            const share = resultShare(record.item, option);
            bar.firstChild.style.height = `${share}%`;
            bar.querySelector('small').textContent = String(share);
            const name = [...option.title];
            bar.lastChild.textContent = name.length > 6 ? `${name.slice(0, 5).join('')}…` : option.title;
            bar.title = `${option.title}: ${share}%`; descriptions.push(bar.title);
        }
        [...chart.children].slice(results.length).forEach(bar => bar.remove());
        chart.setAttribute('aria-label', descriptions.length ? `Results: ${descriptions.join(', ')}` : 'No results yet');
    }
    function renderQuickPreview(record) {
        if (!record.expanded) return;
        const signature = JSON.stringify([record.item.options, record.item.winning_outcome_id]);
        if (record.previewSignature === signature) return;
        record.previewSignature = signature;
        const preview = record.card.querySelector('.engagement-quick-preview');
        const results = record.item.options || [];
        if (!preview.children.length) preview.replaceChildren();
        for (const [index, option] of results.entries()) {
            let row = preview.children[index];
            if (!row) {
                row = document.createElement('div'); row.className = 'engagement-quick-option';
                const track = document.createElement('div'); track.className = 'engagement-quick-track';
                track.setAttribute('role', 'progressbar'); track.setAttribute('aria-valuemin', '0'); track.setAttribute('aria-valuemax', '100');
                track.append(document.createElement('div'));
                row.append(document.createElement('span'), document.createElement('small'), track); preview.append(row);
            }
            const share = resultShare(record.item, option);
            row.style.setProperty('--result-share', `${share}%`);
            const name = row.querySelector('span'); name.textContent = option.title + (record.item.winning_outcome_id === option.id ? ' · Winner' : '');
            const count = row.querySelector('small');
            count.textContent = `${share}% · ${(record.item.kind === 'polls' ? option.votes || 0 : option.points || 0).toLocaleString()} ${record.item.kind === 'polls' ? 'votes' : 'points'}`;
            const track = row.querySelector('.engagement-quick-track');
            track.setAttribute('aria-label', option.title); track.setAttribute('aria-valuenow', String(share));
        }
        [...preview.children].slice(results.length).forEach(row => row.remove());
        if (!preview.children.length) preview.textContent = 'No results available yet.';
    }
    function toggleQuickPreview(record) {
        if (busy) return;
        record.expanded = !record.expanded;
        record.card.setAttribute('aria-expanded', String(record.expanded));
        record.card.querySelector('.engagement-quick-preview').hidden = !record.expanded;
        renderQuickPreview(record);
        if (record.expanded) read(record).catch(() => {});
    }
    function rememberItem(item) {
        if (!valid(item)) return null;
        let record = records.get(item.kind);
        if (record && record.item.id !== item.id) { record.card.remove(); records.delete(item.kind); record = null; }
        if (!record) {
            const card = document.createElement('div'); card.tabIndex = 0; card.setAttribute('role', 'group'); card.className = 'dashboard-engagement-card';
            card.append(document.createElement('strong'), document.createElement('span'));
            const actions = document.createElement('div'); actions.className = 'dashboard-engagement-card-actions';
            const chart = document.createElement('div'); chart.className = 'engagement-mini-chart'; chart.setAttribute('role', 'img');
            for (const [action, text] of [['summary', 'Summary'], ['close', 'Close']]) {
                const button = document.createElement('button'); button.type = 'button'; button.className = 'button secondary';
                button.dataset.engagementCardAction = action; button.textContent = text; actions.append(button);
            }
            const preview = document.createElement('div'); preview.className = 'engagement-quick-preview'; preview.hidden = true;
            preview.id = `engagement-quick-${item.kind}`;
            card.setAttribute('aria-controls', preview.id); card.setAttribute('aria-expanded', 'false');
            card.append(chart, actions, preview);
            record = {item, card, reading: null, heading: card.querySelector('strong'), description: card.querySelector('span'), buttons: [...actions.children]};
            records.set(item.kind, record); host.append(card);
            card.addEventListener('click', event => {
                if (busy) return;
                const action = event.target.closest('[data-engagement-card-action]')?.dataset.engagementCardAction;
                if (action === 'close') {
                    record.card.remove(); records.delete(record.item.kind); remember();
                    document.querySelector(`[data-engagement-open="${record.item.kind}"]`)?.focus({preventScroll: true});
                }
                else if (action) openSummary(record);
                else if (!event.target.closest('.dashboard-engagement-card-actions')) toggleQuickPreview(record);
            });
            card.addEventListener('keydown', event => {
                if (event.target === card && ['Enter', ' '].includes(event.key)) { event.preventDefault(); toggleQuickPreview(record); }
            });
        }
        record.item = item; updateCard(record); remember();
        return record;
    }
    function requestSummary(kind, id) {
        const url = `/channel/api/engagement/${kind}/${encodeURIComponent(id)}`;
        if (requests.has(url)) return requests.get(url).promise;
        const controller = new AbortController();
        const promise = (async () => {
            const response = await fetch(url, {signal: controller.signal, cache: 'no-store', headers: {Accept: 'application/json'}});
            return {ok: response.ok, status: response.status, payload: await response.json()};
        })().finally(() => { if (requests.get(url)?.promise === promise) requests.delete(url); });
        requests.set(url, {promise, controller});
        return promise;
    }
    async function read(record) {
        const {kind, id} = record.item;
        const summary = dialog.open && current === record;
        const routeHash = window.location.hash;
        const requestedId = summary ? summaryRoute()?.id || 'latest' : id;
        if (record.reading && record.readingId === requestedId) return record.reading;
        const revision = record.readRevision = (record.readRevision || 0) + 1;
        record.lastRead = Date.now();
        const reading = (async () => {
            const {ok, status: responseStatus, payload} = await requestSummary(kind, requestedId);
            if (record.readRevision !== revision) return;
            if (summary && (!dialog.open || current !== record || window.location.hash !== routeHash)) return;
            if (!summary && (records.get(kind) !== record || record.item.id !== id)) return;
            if (!ok) {
                record.unavailable = [401, 403, 404].includes(responseStatus);
                record.error = payload.detail || 'Could not refresh the summary.';
                if (record.card) updateCard(record);
                throw new Error(record.error);
            }
            if (summary && record.error) message('');
            if (summary && payload.item.id !== id) {
                current = rememberItem(payload.item); resetConfirmation(); renderSummary(); return;
            }
            const previousStatus = record.item.status;
            record.item = payload.item; record.error = ''; record.unavailable = false;
            if (record.card) updateCard(record);
            if (current === record && previousStatus !== record.item.status) resetConfirmation();
            if (current === record && dialog.open) renderSummary();
        })().catch(error => {
            if (record.readRevision === revision && error.name !== 'AbortError') throw error;
        });
        record.reading = reading; record.readingId = requestedId;
        try { await reading; } finally { if (record.reading === reading) record.reading = null; }
    }
    function resetConfirmation() { pendingAction = null; confirmation.hidden = true; }
    function renderSummary() {
        if (!current) return;
        const item = current.item;
        setText(title, item.title);
        setText(dialog.querySelector('[data-engagement-summary-heading]'), `${label(item)} summary`);
        setText(state, summaryDescription(item));
        const seconds = Number(item.duration);
        dialog.querySelector('[data-engagement-summary-duration]').textContent = Number.isFinite(seconds)
            ? `Voting duration: ${Math.floor(seconds / 60)}m${seconds % 60}s` : '';
        const details = [];
        for (const [field, prefix] of [['created_at', ''], ['locked_at', 'Locked: ']]) {
            const timestamp = Date.parse(item[field]);
            if (Number.isFinite(timestamp)) details.push(`${prefix}${new Date(timestamp).toLocaleString()}`);
        }
        const ended = Date.parse(item.ended_at);
        if (Number.isFinite(ended)) {
            const endTime = new Date(ended).toLocaleTimeString();
            if (details.length) details[details.length - 1] += ` - ${endTime}`;
            else details.push(`- ${endTime}`);
        }
        dialog.querySelector('[data-engagement-summary-times]').textContent = details.join(' ');
        const previous = new Map([...options.children].map(row => [row.dataset.optionKey, row]));
        const itemKey = `${item.kind}:${item.id}`;
        const results = item.options || [];
        for (const [index, option] of results.entries()) {
            const optionKey = `${itemKey}:${option.id || index}`;
            let row = previous.get(optionKey);
            if (!row) {
                row = document.createElement('label'); row.className = 'engagement-summary-option'; row.dataset.optionKey = optionKey;
                const track = document.createElement('div'); track.className = 'engagement-quick-track';
                track.setAttribute('role', 'progressbar'); track.setAttribute('aria-valuemin', '0'); track.setAttribute('aria-valuemax', '100');
                track.append(document.createElement('div'));
                row.append(document.createElement('span'), document.createElement('small'), track);
            }
            previous.delete(optionKey);
            let radio = row.querySelector('input');
            if (item.kind === 'predictions' && active(item) && option.id) {
                if (!radio) {
                    radio = document.createElement('input'); radio.type = 'radio'; radio.name = 'engagement-winning-outcome';
                    radio.value = option.id; row.prepend(radio);
                }
                if (radio.disabled !== busy) radio.disabled = busy;
            } else radio?.remove();
            const share = resultShare(item, option);
            const winner = item.winning_outcome_id === option.id;
            row.classList.toggle('is-winner', winner);
            setText(row.querySelector('span'), option.title + (winner ? ' · Winner' : ''));
            setText(row.querySelector('small'), `${share}% · ` + (item.kind === 'polls' ? `${option.votes || 0} votes` : `${option.votes || 0} viewers · ${(option.points || 0).toLocaleString()} points`));
            const track = row.querySelector('.engagement-quick-track');
            if (track.style.getPropertyValue('--result-share') !== `${share}%`) track.style.setProperty('--result-share', `${share}%`);
            if (track.getAttribute('aria-label') !== option.title) track.setAttribute('aria-label', option.title);
            if (track.getAttribute('aria-valuenow') !== String(share)) track.setAttribute('aria-valuenow', String(share));
            if (options.children[index] !== row) options.insertBefore(row, options.children[index] || null);
        }
        previous.forEach(row => row.remove());
        lock.hidden = item.status !== 'ACTIVE'; lock.textContent = item.kind === 'polls' ? 'Close poll' : 'Lock voting';
        resolve.hidden = item.kind !== 'predictions' || !active(item);
        remove.hidden = !active(item);
        createNew.textContent = item.kind === 'polls' ? 'New poll' : 'New prediction';
        createNew.href = `#${item.kind}`;
        createNew.setAttribute('aria-disabled', String(busy));
        dialog.querySelectorAll('.engagement-summary-header button, .engagement-summary-actions button, .engagement-summary-confirm button').forEach(button => { button.disabled = busy; });
        resolve.disabled = busy || !options.querySelector('input:checked');
        repeat.disabled = busy || active(item) || (item.options || []).length < 2;
        repeat.title = active(item) ? `Finish the current ${label(item).toLowerCase()} first.` : '';
    }
    function summaryRoute() {
        const match = /^#(polls|predictions)-summary(?:=([A-Za-z0-9_-]{1,100}))?$/.exec(window.location.hash);
        return match ? {kind: match[1], id: match[2]} : null;
    }
    async function openSummary(record, updateHash = true) {
        if (busy) return;
        if (!dialog.open) {
            const previousReturn = window.history.state?.engagementSummaryReturn;
            summaryReturn = !updateHash && previousReturn !== undefined ? previousReturn
                : creator?.open ? creator.querySelector('[data-engagement-tab][aria-selected="true"]')?.dataset.engagementTab : null;
            if (!['polls', 'predictions'].includes(summaryReturn)) summaryReturn = null;
            summaryOpener = summaryReturn ? document.activeElement : record.card;
        }
        const hash = `#${record.item.kind}-summary=${record.item.id}`;
        const historyState = {...window.history.state, engagementSummaryReturn: summaryReturn};
        if (updateHash && window.location.hash !== hash) window.history.pushState(historyState, '', hash);
        else window.history.replaceState(historyState, '', window.location.href);
        creator?.close();
        current = record; resetConfirmation(); message(''); renderSummary();
        if (!dialog.open) dialog.showModal();
        try {
            await read(record);
        } catch (error) { if (current === record && dialog.open) message(error.message, true); }
    }
    function closeSummary() {
        if (busy) return;
        dialog.close();
        if (summaryReturn) {
            document.querySelector(`[data-engagement-open="${summaryReturn}"]`)?.click();
            if (creator?.open && summaryOpener?.isConnected && creator.contains(summaryOpener))
                summaryOpener.focus({preventScroll: true});
        }
    }
    function syncSummaryHash() {
        const route = summaryRoute();
        if (!route) { if (dialog.open) dialog.close(); return; }
        if (busy) return;
        const record = records.get(route.kind);
        openSummary(record && (!route.id || record.item.id === route.id) ? record : {item: {
            ...route, id: route.id || 'latest', title: `${label(route)} summary`, status: '', options: []
        }}, false);
    }
    async function act(action, outcome = '') {
        if (busy || !current) return;
        const record = current;
        const actionHash = window.location.hash;
        record.readRevision = (record.readRevision || 0) + 1;
        record.reading = null;
        for (const [url, request] of requests) if (url.startsWith(`/channel/api/engagement/${record.item.kind}/`)) {
            requests.delete(url); request.controller.abort();
        }
        busy = true; resetConfirmation(); renderSummary(); message('Updating…');
        for (const item of records.values()) updateCard(item);
        try {
            const body = new URLSearchParams({action, csrf_token: host.dataset.csrfToken || '', winning_outcome_id: outcome});
            const response = await fetch(`/channel/api/engagement/${record.item.kind}/${encodeURIComponent(record.item.id)}/action`,
                {method: 'POST', body, headers: {Accept: 'application/json'}});
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || 'Could not confirm the change. Refresh before retrying.');
            record.item = payload.item; record.error = ''; record.unavailable = false;
            document.dispatchEvent(new CustomEvent('dashboard-engagement-updated', {detail: {kind: record.item.kind}}));
            if (payload.dismissed) {
                record.card?.remove();
                if (records.get(record.item.kind) === record) records.delete(record.item.kind);
                remember(); dialog.close();
            } else { updateCard(record); message('Updated.'); }
        } catch (error) { record.error = error.message; message(error.message, true); }
        finally {
            busy = false;
            for (const item of records.values()) updateCard(item);
            if (dialog.open) renderSummary();
            if (window.location.hash !== actionHash) syncSummaryHash();
        }
    }
    function confirm(action) {
        if (busy || !current) return;
        const item = current.item, outcome = options.querySelector('input:checked')?.value || '';
        if (action === 'resolve' && !outcome) return;
        pendingAction = {action, outcome};
        const text = action === 'resolve'
            ? `Choose “${item.options.find(option => option.id === outcome)?.title}” as the winner? This awards Channel Points and cannot be undone.`
            : item.kind === 'polls' ? 'Delete this poll? It will end and be archived on Twitch.'
                    : 'Delete this prediction? It will be cancelled and all Channel Points refunded.';
        dialog.querySelector('[data-engagement-summary-confirm-text]').textContent = text;
        confirmation.hidden = false;
        dialog.querySelector('[data-engagement-summary-confirm-yes]').focus();
    }
    function animateIntoChat(detail, record) {
        const flyer = detail.flyer, from = detail.sourceRect;
        if (!flyer || !from) {
            requestAnimationFrame(() => { if (record.card.isConnected && !creator?.open && !dialog.open) record.card.focus({preventScroll: true}); });
            return;
        }
        requestAnimationFrame(() => requestAnimationFrame(() => {
            record.card.scrollIntoView({block: 'nearest', behavior: 'instant'});
            const to = record.card.getBoundingClientRect();
            if (!from.width || !from.height || !to.width || !to.height || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
                flyer.remove(); record.card.focus({preventScroll: true}); return;
            }
            const frame = document.createElement('div'); frame.className = 'engagement-flight'; frame.inert = true; frame.setAttribute('aria-hidden', 'true');
            Object.assign(frame.style, {left: `${from.left}px`, top: `${from.top}px`, width: `${from.width}px`, height: `${from.height}px`,
                border: '1px solid var(--border)', borderRadius: '10px', background: 'var(--background)'});
            Object.assign(flyer.style, {width: `${from.width}px`, height: `${from.height}px`, transformOrigin: 'top left'});
            frame.append(flyer); document.body.append(frame); flyer.scrollTop = detail.sourceScrollTop || 0; record.card.style.opacity = '0';
            const scale = Math.min(to.width / from.width, to.height / from.height);
            const settings = {duration: 650, easing: 'cubic-bezier(.22,1,.36,1)', fill: 'forwards'};
            const content = flyer.animate([{transform: 'scale(1)', opacity: 1}, {transform: `scale(${scale})`, opacity: 0}], settings);
            content.finished.catch(() => {});
            const animation = frame.animate([{transform: 'translate(0,0)', width: `${from.width}px`, height: `${from.height}px`, opacity: 1},
                {transform: `translate(${to.left - from.left}px,${to.top - from.top}px)`, width: `${to.width}px`, height: `${to.height}px`, borderRadius: '8px', borderColor: 'var(--accent)', opacity: 0}], settings);
            const finish = () => { content.cancel(); frame.remove(); record.card.style.opacity = ''; record.card.focus({preventScroll: true}); };
            animation.finished.then(finish, finish);
        }));
    }
    document.addEventListener('dashboard-engagement-started', event => {
        if (!valid(event.detail?.item)) return;
        const record = rememberItem(event.detail.item);
        creator?.close(); animateIntoChat(event.detail, record);
    });
    lock.addEventListener('click', () => act('close'));
    options.addEventListener('change', event => {
        if (!event.target.matches('input[name="engagement-winning-outcome"]')) return;
        resetConfirmation(); resolve.disabled = busy || !options.querySelector('input:checked');
    });
    resolve.addEventListener('click', () => confirm('resolve'));
    remove.addEventListener('click', () => confirm('delete'));
    dialog.querySelector('[data-engagement-summary-confirm-yes]').addEventListener('click', () => { if (pendingAction) act(pendingAction.action, pendingAction.outcome); });
    dialog.querySelector('[data-engagement-summary-confirm-no]').addEventListener('click', resetConfirmation);
    createNew.addEventListener('click', event => { if (busy) event.preventDefault(); });
    repeat.addEventListener('click', () => {
        if (repeat.disabled || !current) return;
        const item = current.item;
        dialog.close();
        document.dispatchEvent(new CustomEvent('dashboard-engagement-repeat', {detail: {
            kind: item.kind, title: item.title, duration: item.duration, choices: item.options.map(option => option.title),
            ...(item.kind === 'polls' ? {channel_points_voting_enabled: item.channel_points_voting_enabled === true,
                channel_points_per_vote: item.channel_points_per_vote} : {})
        }}));
    });
    dialog.querySelector('[data-engagement-summary-close]').addEventListener('click', closeSummary);
    dialog.addEventListener('cancel', event => {
        event.preventDefault();
        if (busy || pendingAction) resetConfirmation(); else closeSummary();
    });
    dialog.addEventListener('pointerdown', event => {
        const rect = dialog.getBoundingClientRect();
        backdropPress = event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom);
    });
    dialog.addEventListener('pointercancel', () => { backdropPress = false; });
    dialog.addEventListener('click', event => {
        const rect = dialog.getBoundingClientRect();
        if (!busy && backdropPress && event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) closeSummary();
        backdropPress = false;
    });
    dialog.addEventListener('close', () => {
        if (dialog.open) return;
        resetConfirmation(); backdropPress = false;
        const route = summaryRoute();
        if (route && route.kind === current?.item.kind && (!route.id || route.id === current.item.id))
            window.history.replaceState(null, '', window.location.pathname + window.location.search);
        if (['#polls', '#predictions'].includes(window.location.hash)) return;
        const target = current?.card?.isConnected ? current.card : document.querySelector(`[data-engagement-open="${current?.item.kind}"]`);
        target?.focus({preventScroll: true});
    });
    function refreshVisible() {
        if (document.visibilityState !== 'visible' || busy) return;
        const targets = new Set(records.values());
        if (dialog.open && current) targets.add(current);
        for (const record of targets) if (((dialog.open && current === record) || (active(record.item) && !record.unavailable)) &&
            (record.expanded || (dialog.open && current === record) || Date.now() - (record.lastRead || 0) >= 15000)) read(record).catch(error => {
            if (dialog.open && current === record) message(error.message, true);
        });
    }
    function tickClock() {
        if (document.visibilityState !== 'visible') return;
        for (const record of records.values()) if (active(record.item)) updateCardDescription(record);
        if (dialog.open && current) setText(state, summaryDescription(current.item));
    }
    let clock = null, polling = null;
    function startTimers() {
        if (clock === null) clock = setInterval(tickClock, 1000);
        if (polling === null) polling = setInterval(refreshVisible, 5000);
    }
    startTimers();
    document.addEventListener('visibilitychange', refreshVisible);
    window.addEventListener('pagehide', () => {
        clearInterval(clock); clearInterval(polling);
        clock = null; polling = null;
        requests.forEach(request => request.controller.abort());
        requests.clear();
        const targets = new Set(records.values());
        if (current) targets.add(current);
        targets.forEach(record => { record.readRevision = (record.readRevision || 0) + 1; record.reading = null; });
    });
    window.addEventListener('pageshow', event => { if (event.persisted) { startTimers(); refreshVisible(); } });
    try {
        const stored = JSON.parse(localStorage.getItem(storageKey) || '[]');
        if (Array.isArray(stored)) for (const item of stored.filter(valid).slice(0, 2)) {
            const record = rememberItem({...item, title: `${label(item)} summary`, status: 'ACTIVE', options: []});
            read(record).catch(error => { record.card.querySelector('span').textContent = `${error.message} · Click to retry`; });
        }
    } catch (_) {}
    window.addEventListener('hashchange', syncSummaryHash);
    window.addEventListener('popstate', syncSummaryHash);
    syncSummaryHash();
})();
