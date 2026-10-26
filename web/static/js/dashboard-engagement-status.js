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
    const confirmation = dialog.querySelector('[data-engagement-summary-confirm]');
    const records = new Map();
    const storageKey = `dashboard-engagement-active:${host.dataset.channelId}:v1`;
    let current = null, pendingAction = null, busy = false, backdropPress = false;
    const valid = item => ['polls', 'predictions'].includes(item?.kind) && /^[A-Za-z0-9_-]{1,100}$/.test(item?.id || '');
    const label = item => item.kind === 'polls' ? 'Poll' : 'Prediction';
    const active = item => ['ACTIVE', 'LOCKED'].includes(item.status);
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
        record.card.querySelector('strong').textContent = record.item.title || label(record.item);
        record.card.querySelector('span').textContent = `${label(record.item)} · ${record.error || description(record.item)}`;
        record.card.querySelectorAll('button').forEach(button => { button.disabled = busy; });
        renderMiniChart(record);
        renderQuickPreview(record);
    }
    function resultTotals(item) {
        return (item.options || []).reduce((total, option) => ({votes: total.votes + (option.votes || 0), points: total.points + (option.points || 0)}), {votes: 0, points: 0});
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
            record = {item, card, reading: null}; records.set(item.kind, record); host.append(card);
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
    async function read(record) {
        if (record.reading) return record.reading;
        record.reading = (async () => {
            const {kind, id} = record.item;
            record.lastRead = Date.now();
            const response = await fetch(`/channel/api/engagement/${kind}/${encodeURIComponent(id)}`, {cache: 'no-store', headers: {Accept: 'application/json'}});
            const payload = await response.json();
            if (!response.ok) {
                record.unavailable = [401, 403, 404].includes(response.status);
                record.error = payload.detail || 'Could not refresh the summary.'; updateCard(record);
                throw new Error(record.error);
            }
            if (records.get(kind) !== record || record.item.id !== id) return;
            const previousStatus = record.item.status;
            record.item = payload.item; record.error = ''; record.unavailable = false; updateCard(record);
            if (current === record && previousStatus !== record.item.status) resetConfirmation();
            if (current === record && dialog.open) renderSummary();
        })();
        try { await record.reading; } finally { record.reading = null; }
    }
    function resetConfirmation() { pendingAction = null; confirmation.hidden = true; }
    function renderSummary() {
        if (!current) return;
        const item = current.item;
        const selected = options.querySelector('input:checked')?.value;
        const focused = options.contains(document.activeElement) ? document.activeElement.value : null;
        title.textContent = item.title;
        dialog.querySelector('[data-engagement-summary-heading]').textContent = `${label(item)} summary`;
        state.textContent = summaryDescription(item);
        const seconds = Number(item.duration);
        const details = Number.isFinite(seconds) ? [`Voting duration: ${Math.floor(seconds / 60)}m${seconds % 60}s`] : [];
        for (const [field, text] of [['created_at', 'Started'], ['locked_at', 'Locked'], ['ended_at', 'Ended']]) {
            const timestamp = Date.parse(item[field]);
            if (Number.isFinite(timestamp)) details.push(`${text}: ${new Date(timestamp).toLocaleString()}`);
        }
        dialog.querySelector('[data-engagement-summary-details]').textContent = details.join(' · ');
        options.replaceChildren();
        for (const option of item.options || []) {
            const row = document.createElement('label'); row.className = 'engagement-summary-option';
            if (item.kind === 'predictions' && active(item) && option.id) {
                const radio = document.createElement('input'); radio.type = 'radio'; radio.name = 'engagement-winning-outcome';
                radio.value = option.id; radio.checked = selected === option.id; radio.disabled = busy;
                radio.addEventListener('change', () => { resetConfirmation(); resolve.disabled = busy || !options.querySelector('input:checked'); });
                row.append(radio);
            }
            const text = document.createElement('span'); text.textContent = option.title;
            const totals = document.createElement('small');
            totals.textContent = `${resultShare(item, option)}% · ` + (item.kind === 'polls' ? `${option.votes || 0} votes` : `${option.votes || 0} viewers · ${(option.points || 0).toLocaleString()} points`);
            if (item.winning_outcome_id === option.id) { row.classList.add('is-winner'); text.textContent += ' · Winner'; }
            row.append(text, totals); options.append(row);
        }
        lock.hidden = item.status !== 'ACTIVE'; lock.textContent = item.kind === 'polls' ? 'Close poll' : 'Lock voting';
        resolve.hidden = item.kind !== 'predictions' || !active(item);
        remove.textContent = active(item) ? 'Delete' : 'Remove summary';
        dialog.querySelectorAll('.engagement-summary-header button, .engagement-summary-actions button, .engagement-summary-confirm button').forEach(button => { button.disabled = busy; });
        resolve.disabled = busy || !options.querySelector('input:checked');
        if (focused) [...options.querySelectorAll('input')].find(input => input.value === focused)?.focus({preventScroll: true});
    }
    async function openSummary(record) {
        if (busy) return;
        current = record; resetConfirmation(); message(''); renderSummary();
        if (!dialog.open) dialog.showModal();
        try {
            await read(record);
        } catch (error) { if (current === record && dialog.open) message(error.message, true); }
    }
    async function act(action, outcome = '') {
        if (busy || !current) return;
        const record = current;
        busy = true; resetConfirmation(); renderSummary(); message('Updating…');
        for (const item of records.values()) updateCard(item);
        try {
            const body = new URLSearchParams({action, csrf_token: host.dataset.csrfToken || '', winning_outcome_id: outcome});
            const response = await fetch(`/channel/api/engagement/${record.item.kind}/${encodeURIComponent(record.item.id)}/action`,
                {method: 'POST', body, headers: {Accept: 'application/json'}});
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || 'Could not confirm the change. Refresh before retrying.');
            // An older read cannot overwrite the confirmed action below.
            if (record.reading) await record.reading.catch(() => {});
            record.item = payload.item; record.error = ''; record.unavailable = false;
            document.dispatchEvent(new CustomEvent('dashboard-engagement-updated', {detail: {kind: record.item.kind}}));
            if (payload.dismissed) {
                record.card.remove(); records.delete(record.item.kind); remember(); dialog.close();
            } else { updateCard(record); message('Updated.'); }
        } catch (error) { record.error = error.message; message(error.message, true); }
        finally {
            busy = false;
            for (const item of records.values()) updateCard(item);
            if (dialog.open) renderSummary();
        }
    }
    function confirm(action) {
        if (busy || !current) return;
        const item = current.item, outcome = options.querySelector('input:checked')?.value || '';
        if (action === 'resolve' && !outcome) return;
        pendingAction = {action, outcome};
        const text = action === 'resolve'
            ? `Choose “${item.options.find(option => option.id === outcome)?.title}” as the winner? This awards Channel Points and cannot be undone.`
            : !active(item) ? 'Remove this summary from the dashboard? Twitch history will be kept.'
                : item.kind === 'polls' ? 'Delete this poll? It will end and be archived on Twitch.'
                    : 'Delete this prediction? It will be cancelled and all Channel Points refunded.';
        dialog.querySelector('[data-engagement-summary-confirm-text]').textContent = text;
        confirmation.hidden = false;
        dialog.querySelector('[data-engagement-summary-confirm-yes]').focus();
    }
    function animateIntoChat(detail, record) {
        const flyer = detail.flyer, from = detail.sourceRect;
        if (!flyer || !from) return;
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
    resolve.addEventListener('click', () => confirm('resolve'));
    remove.addEventListener('click', () => confirm('delete'));
    dialog.querySelector('[data-engagement-summary-confirm-yes]').addEventListener('click', () => { if (pendingAction) act(pendingAction.action, pendingAction.outcome); });
    dialog.querySelector('[data-engagement-summary-confirm-no]').addEventListener('click', resetConfirmation);
    dialog.querySelector('[data-engagement-summary-refresh]').addEventListener('click', () => { if (!busy) openSummary(current); });
    dialog.querySelector('[data-engagement-summary-close]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('cancel', event => { if (busy || pendingAction) { event.preventDefault(); resetConfirmation(); } });
    dialog.addEventListener('pointerdown', event => {
        const rect = dialog.getBoundingClientRect();
        backdropPress = event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom);
    });
    dialog.addEventListener('pointercancel', () => { backdropPress = false; });
    dialog.addEventListener('click', event => {
        const rect = dialog.getBoundingClientRect();
        if (!busy && backdropPress && event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
        backdropPress = false;
    });
    dialog.addEventListener('close', () => {
        resetConfirmation(); backdropPress = false;
        const target = current?.card.isConnected ? current.card : document.querySelector(`[data-engagement-open="${current?.item.kind}"]`);
        target?.focus({preventScroll: true});
    });
    function refreshVisible() {
        if (document.visibilityState !== 'visible' || busy) return;
        for (const record of records.values()) if (active(record.item) && !record.unavailable &&
            (record.expanded || (dialog.open && current === record) || Date.now() - (record.lastRead || 0) >= 15000)) read(record).catch(error => {
            if (dialog.open && current === record) message(error.message, true);
        });
    }
    const clock = setInterval(() => {
        for (const record of records.values()) updateCard(record);
        if (dialog.open && current) state.textContent = summaryDescription(current.item);
    }, 1000);
    const polling = setInterval(refreshVisible, 5000);
    document.addEventListener('visibilitychange', refreshVisible);
    window.addEventListener('pagehide', () => { clearInterval(clock); clearInterval(polling); });
    try {
        const stored = JSON.parse(localStorage.getItem(storageKey) || '[]');
        if (Array.isArray(stored)) for (const item of stored.filter(valid).slice(0, 2)) {
            const record = rememberItem({...item, title: `${label(item)} summary`, status: 'ACTIVE', options: []});
            read(record).catch(error => { record.card.querySelector('span').textContent = `${error.message} · Click to retry`; });
        }
    } catch (_) {}
})();
