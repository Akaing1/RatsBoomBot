(() => {
    const dialog = document.querySelector('[data-engagement]');
    if (!dialog) return;
    const form = dialog.querySelector('[data-engagement-form]');
    const title = form.elements.title, duration = form.elements.duration;
    const durationSlider = dialog.querySelector('[data-engagement-duration-slider]');
    const durationHint = dialog.querySelector('[data-engagement-duration-hint]');
    const pollOptions = dialog.querySelector('[data-engagement-poll-options]');
    const additionalVotes = dialog.querySelector('[data-engagement-additional-votes]');
    const voteCost = form.elements.channel_points_per_vote;
    const voteCostLabel = dialog.querySelector('[data-engagement-vote-cost]');
    // Equal track segments represent increasingly larger time intervals.
    const durationSnaps = [15, 30, 60, 120, 300, 600, 1200, 1800];
    const durationMarks = dialog.querySelector('#engagement-duration-marks');
    const durationLabels = dialog.querySelector('[data-engagement-duration-labels]');
    let durationPoints = [];
    const choices = dialog.querySelector('[data-engagement-choices]');
    const excludedMark = dialog.querySelector('[data-engagement-excluded-mark]');
    const choiceWarning = dialog.querySelector('[data-engagement-choice-warning]');
    const tabs = [...dialog.querySelectorAll('[data-engagement-tab]')];
    const tabStrip = dialog.querySelector('.engagement-tabs');
    const save = dialog.querySelector('[data-engagement-save]');
    const add = dialog.querySelector('[data-engagement-add]');
    const addControl = dialog.querySelector('[data-engagement-add-control]');
    const start = dialog.querySelector('[data-engagement-start]');
    const status = dialog.querySelector('[data-engagement-status]');
    const historyStatus = dialog.querySelector('[data-engagement-history-status]');
    const refresh = dialog.querySelector('[data-engagement-refresh]');
    const storageKey = `dashboard-engagement:${dialog.dataset.channelId}:v1`;
    const starIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 2 3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2Z"/></svg>';
    let mode = 'predictions', busy = false, opener = null, historyController = null, backdropPress = false;
    const recent = new Map();
    let saved = [];
    let deleteRow = null;
    let dismissedDeletePress = false;
    const removingSaved = new Set();
    function validTemplate(item) {
        return item && typeof item.title === 'string' && item.title.length <= 60 &&
            Array.isArray(item.choices) && item.choices.length >= 2 && item.choices.length <= 10 &&
            item.choices.every(choice => typeof choice === 'string' && choice.length <= 25) &&
            Number.isInteger(item.duration) && item.duration >= 15 && item.duration <= 1800 &&
            ['polls', 'predictions'].includes(item.kind) &&
            (item.kind !== 'polls' || item.channel_points_voting_enabled !== true ||
                (Number.isInteger(item.channel_points_per_vote) && item.channel_points_per_vote >= 1 && item.channel_points_per_vote <= 1_000_000));
    }
    try {
        const stored = JSON.parse(localStorage.getItem(storageKey) || '[]');
        if (Array.isArray(stored)) saved = stored.filter(validTemplate).slice(0, 100);
    } catch (_) { /* Storage may be unavailable or contain an older format. */ }
    function message(text, error = false) {
        status.textContent = text;
        status.style.color = error ? 'var(--danger)' : '';
    }
    function draft() {
        return {kind: mode, title: title.value.trim(), duration: parseDuration(duration.value),
            ...(mode === 'polls' ? {channel_points_voting_enabled: additionalVotes.checked,
                ...(additionalVotes.checked ? {channel_points_per_vote: voteCost.valueAsNumber} : {})} : {}),
            choices: [...choices.querySelectorAll('input')].slice(0, mode === 'polls' ? 5 : Infinity).map(input => input.value.trim())};
    }
    function key(item) { return JSON.stringify([item.kind, item.title, item.choices, item.duration,
        ...(item.kind === 'polls' ? [item.channel_points_voting_enabled === true,
            item.channel_points_voting_enabled === true ? item.channel_points_per_vote : null] : [])]); }
    function syncTemplateMatches() {
        const currentKey = key(draft());
        dialog.querySelectorAll('.engagement-library-row').forEach(row => {
            const matches = row.dataset.templateKey === currentKey;
            row.classList.toggle('is-matching', matches);
            row.querySelector('.engagement-load').setAttribute('aria-pressed', String(matches));
        });
    }
    function durationText(seconds) {
        const minutes = Math.floor(seconds / 60), remainder = seconds % 60;
        return [minutes ? `${minutes} minute${minutes === 1 ? '' : 's'}` : '', remainder ? `${remainder} second${remainder === 1 ? '' : 's'}` : ''].filter(Boolean).join(' ') || '0 seconds';
    }
    function parseDuration(text) {
        const value = text.trim().toLowerCase();
        if (/^\d+$/.test(value)) return Number(value);
        const match = /^(?:(\d+(?:\.\d+)?)\s*m(?:in(?:ute)?s?)?\s*)?(?:(\d+)\s*s(?:ec(?:ond)?s?)?)?$/.exec(value);
        if (!match || (!match[1] && !match[2])) return NaN;
        const seconds = Number(match[1] || 0) * 60 + Number(match[2] || 0);
        return Number.isSafeInteger(seconds) ? seconds : NaN;
    }
    function formatDuration(seconds) { return `${Math.floor(seconds / 60)}m${seconds % 60}s`; }
    function durationStep(seconds) { return seconds < 60 ? 5 : seconds < 120 ? 10 : seconds < 600 ? 30 : 60; }
    function durationPosition(seconds) {
        const upper = durationPoints.findIndex(point => point >= seconds);
        if (upper <= 0) return upper === 0 ? 0 : durationPoints.length - 1;
        const lower = durationPoints[upper - 1];
        return upper - 1 + (seconds - lower) / (durationPoints[upper] - lower);
    }
    function durationSeconds(position) {
        const lower = Math.min(Math.floor(position), durationPoints.length - 2);
        return Math.round(durationPoints[lower] + (position - lower) * (durationPoints[lower + 1] - durationPoints[lower]));
    }
    function layoutDurationLabels() {
        const spacing = (durationSlider.clientWidth - 16) / (durationPoints.length - 1);
        const rows = spacing > 0 ? Math.max(1, Math.ceil(40 / spacing)) : 1;
        [...durationLabels.children].forEach((label, index) => {
            label.style.left = `${index / (durationPoints.length - 1) * 100}%`;
            label.style.top = `${index % rows * 16}px`;
        });
        durationSlider.closest('.engagement-duration-row').style.setProperty('--duration-label-height', `${rows * 16 + 8}px`);
    }
    function syncDuration(normalize = false) {
        const minimum = mode === 'polls' ? 15 : 30;
        if (durationPoints[0] !== minimum) {
            durationPoints = durationSnaps.filter(point => point >= minimum);
            durationSlider.max = String(durationPoints.length - 1);
            durationMarks.replaceChildren(...durationPoints.map((seconds, index) => {
                const option = document.createElement('option');
                option.value = String(index); option.dataset.seconds = String(seconds);
                return option;
            }));
            durationLabels.replaceChildren(...durationPoints.map(seconds => {
                const label = document.createElement('span');
                label.textContent = seconds < 60 ? `${seconds}s` : seconds % 60 ? formatDuration(seconds) : `${seconds / 60}m`;
                label.title = durationText(seconds);
                return label;
            }));
            layoutDurationLabels();
        }
        const value = parseDuration(duration.value);
        const valid = Number.isInteger(value) && value >= minimum && value <= 1800;
        duration.setCustomValidity(valid ? '' : `Enter ${minimum}s–30m, for example 2m15s, 2m or 90s.`);
        if (valid) {
            durationSlider.value = String(durationPosition(value));
            if (normalize) duration.value = formatDuration(value);
        }
        const seconds = durationSeconds(Number(durationSlider.value));
        durationSlider.setAttribute('aria-valuemin', String(minimum));
        durationSlider.setAttribute('aria-valuemax', '1800');
        durationSlider.setAttribute('aria-valuenow', String(seconds));
        durationSlider.setAttribute('aria-valuetext', durationText(seconds));
        durationHint.textContent = `${minimum}s–30m · Enter 2m15s, 2m or 90s`;
        syncTemplateMatches();
    }
    durationSlider.addEventListener('keydown', event => {
        const changes = {ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1, PageDown: -60, PageUp: 60};
        if (!(event.key in changes) && !['Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const minimum = durationPoints[0], current = durationSeconds(Number(durationSlider.value));
        const change = changes[event.key];
        // Moving left at a boundary uses the finer interval immediately below it.
        const step = durationStep(current + (change < 0 ? -1 : 0));
        const value = event.key === 'Home' ? minimum : event.key === 'End' ? 1800 :
            (change > 0 ? Math.floor(current / step) : Math.ceil(current / step)) * step + (Math.abs(change) === 1 ? change * step : change);
        duration.value = formatDuration(Math.max(minimum, Math.min(1800, value))); syncDuration();
    });
    durationSlider.addEventListener('input', () => {
        const seconds = durationSeconds(Number(durationSlider.value)), step = durationStep(seconds);
        const value = Math.max(durationPoints[0], Math.round(seconds / step) * step);
        duration.value = formatDuration(value); syncDuration();
    });
    duration.addEventListener('input', () => syncDuration());
    duration.addEventListener('blur', () => syncDuration(true));
    function updateIndicator() {
        const selected = tabs.find(tab => tab.dataset.engagementTab === mode);
        tabStrip.style.setProperty('--engagement-tab-x', `${selected.offsetLeft}px`);
        tabStrip.style.setProperty('--engagement-tab-width', `${selected.offsetWidth}px`);
    }
    function validate(item) {
        const limit = mode === 'polls' ? 60 : 45, max = mode === 'polls' ? 5 : 10;
        if (!item.title || Array.from(item.title).length > limit) return `Enter a title of 1–${limit} characters.`;
        if (item.choices.length > max) return `${mode === 'polls' ? 'Polls' : 'Predictions'} allow up to ${max} choices. Your draft has been kept.`;
        if (item.choices.some(choice => !choice || Array.from(choice).length > 25)) return 'Enter 1–25 characters for each choice.';
        if (new Set(item.choices.map(choice => choice.toLowerCase())).size !== item.choices.length) return 'Each choice must be different.';
        if (!Number.isInteger(item.duration) || item.duration < (mode === 'polls' ? 15 : 30) || item.duration > 1800) return `Enter a duration from ${mode === 'polls' ? '15s' : '30s'} to 30m, such as 2m15s.`;
        if (item.channel_points_voting_enabled && (!Number.isInteger(item.channel_points_per_vote) || item.channel_points_per_vote < 1 || item.channel_points_per_vote > 1_000_000)) return 'Set a cost of 1–1,000,000 Channel Points per additional vote.';
        return '';
    }
    function updateExcludedMark() {
        const excluded = [...choices.querySelectorAll('.is-excluded input')];
        excludedMark.hidden = !excluded.length || !dialog.open;
        if (excludedMark.hidden) return;
        const area = choices.parentElement.getBoundingClientRect();
        const first = excluded[0].getBoundingClientRect(), last = excluded.at(-1).getBoundingClientRect();
        Object.assign(excludedMark.style, {left: `${first.left - area.left}px`, top: `${first.top - area.top}px`,
            width: `${first.width}px`, height: `${last.bottom - first.top}px`});
    }
    function updateControls() {
        pollOptions.hidden = mode !== 'polls';
        additionalVotes.disabled = busy || mode !== 'polls';
        voteCostLabel.hidden = !additionalVotes.checked;
        voteCost.disabled = busy || mode !== 'polls' || !additionalVotes.checked;
        voteCost.required = mode === 'polls' && additionalVotes.checked;
        const inputs = [...choices.querySelectorAll('input')];
        [...choices.children].forEach((row, index) => {
            const excluded = mode === 'polls' && index >= 5;
            row.classList.toggle('is-excluded', excluded);
            row.querySelector('.engagement-choice-number').textContent = index + 1;
            inputs[index].setAttribute('aria-label', `Choice ${index + 1}`);
            inputs[index].disabled = busy || excluded;
            inputs[index].required = !excluded;
            if (excluded) inputs[index].setAttribute('aria-describedby', choiceWarning.id);
            else inputs[index].removeAttribute('aria-describedby');
            const remove = row.querySelector('button');
            remove.disabled = busy || inputs.length <= 2;
            remove.setAttribute('aria-label', `Remove choice ${index + 1}`);
        });
        choiceWarning.hidden = mode !== 'polls' || inputs.length <= 5;
        updateExcludedMark();
        const maximum = mode === 'polls' ? 5 : 10;
        add.disabled = busy || inputs.length >= maximum;
        const addReason = inputs.length >= maximum
            ? `The maximum number of choices you can add to a ${mode === 'polls' ? 'poll' : 'prediction'} is ${maximum}.`
            : busy ? 'Wait for the current request to finish.' : '';
        add.title = addReason;
        addControl.title = addReason;
        start.disabled = busy;
        save.disabled = busy;
        const singular = mode === 'polls' ? 'poll' : 'prediction';
        start.textContent = busy ? 'Starting…' : `Start ${singular}`;
        save.textContent = `Save this ${singular}`;
        syncTemplateMatches();
    }
    function addChoice(value = '') {
        const row = document.createElement('div'); row.className = 'engagement-choice';
        const number = document.createElement('span'); number.className = 'engagement-choice-number'; number.setAttribute('aria-hidden', 'true');
        const label = document.createElement('label');
        const input = document.createElement('input'); input.type = 'text'; input.maxLength = 25; input.required = true;
        input.placeholder = 'Enter a choice'; input.value = value;
        label.append(input);
        const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'engagement-remove'; remove.textContent = '×';
        remove.addEventListener('click', () => {
            if (busy || choices.children.length <= 2) return;
            const next = row.nextElementSibling || row.previousElementSibling;
            row.remove(); updateControls(); next.querySelector('input').focus();
        });
        row.append(number, label, remove); choices.append(row); updateControls();
        return input;
    }
    function persist(next) {
        try {
            localStorage.setItem(storageKey, JSON.stringify(next)); saved = next; return true;
        } catch (_) { message('Could not save in this browser. Check available storage.', true); return false; }
    }
    function clearDeleteConfirmation() {
        if (!deleteRow) return;
        deleteRow.classList.remove('is-delete-pending');
        const confirm = deleteRow.querySelector('.engagement-delete');
        confirm.disabled = true; confirm.tabIndex = -1; confirm.setAttribute('aria-hidden', 'true');
        deleteRow.querySelector('.engagement-star').setAttribute('aria-expanded', 'false');
        deleteRow = null;
    }
    function animateSavedRow(row, removing = false) {
        if (!row || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return null;
        const expanded = {height: `${row.getBoundingClientRect().height}px`, opacity: 1, transform: 'translateY(0)', marginBottom: '0px'};
        const collapsed = {height: '0px', opacity: 0, transform: 'translateY(-14px)', marginBottom: '-8px'};
        return row.animate(removing ? [expanded, collapsed] : [collapsed, expanded],
            {duration: 240, easing: 'cubic-bezier(.22,1,.36,1)', fill: removing ? 'forwards' : 'none'});
    }
    async function deleteSaved(item) {
        const itemKey = key(item);
        if (busy || removingSaved.has(itemKey)) return;
        removingSaved.add(itemKey);
        clearDeleteConfirmation();
        const savedList = dialog.querySelector('[data-engagement-saved]');
        const row = [...savedList.children].find(node => node.dataset.templateKey === itemKey);
        if (row) {
            row.classList.add('is-removing');
            row.querySelectorAll('button').forEach(button => { button.disabled = true; });
        }
        const animation = animateSavedRow(row, true);
        if (animation) await animation.finished.catch(() => {});
        const removed = persist(saved.filter(value => key(value) !== itemKey));
        animation?.cancel();
        row?.classList.remove('is-removing');
        removingSaved.delete(itemKey);
        renderLibrary();
        if (removed) { message('Removed from saved.'); save.focus({preventScroll: true}); }
    }
    function toggleSaved(item, row) {
        const itemKey = key(item), exists = saved.some(value => key(value) === itemKey);
        if (busy || removingSaved.has(itemKey)) return;
        if (exists) {
            const alreadyPending = deleteRow === row;
            clearDeleteConfirmation();
            if (alreadyPending) return;
            deleteRow = row; row.classList.add('is-delete-pending');
            const confirm = row.querySelector('.engagement-delete');
            confirm.disabled = false; confirm.tabIndex = 0; confirm.setAttribute('aria-hidden', 'false');
            row.querySelector('.engagement-star').setAttribute('aria-expanded', 'true');
            return;
        }
        if (saved.length >= 100) { message('You can save up to 100 templates. Remove one first.', true); return; }
        clearDeleteConfirmation();
        if (persist([item, ...saved])) {
            renderLibrary(itemKey); message('Saved.');
        }
    }
    function loadTemplate(item) {
        if (busy) return;
        title.value = item.title;
        duration.value = formatDuration(item.duration);
        if (item.kind === 'polls') {
            additionalVotes.checked = item.channel_points_voting_enabled === true;
            voteCost.value = String(Number.isInteger(item.channel_points_per_vote) && item.channel_points_per_vote > 0 ? item.channel_points_per_vote : 100);
        }
        syncDuration();
        choices.replaceChildren(); item.choices.forEach(addChoice); updateControls();
        message('Loaded.'); title.focus();
    }
    function renderList(container, items, empty, animateKey = '') {
        const previous = new Map([...container.children].filter(node => node.dataset.templateKey).map(row => [row.dataset.templateKey, row]));
        const nextKeys = new Set(items.map(key));
        for (const node of [...container.children]) {
            if (!nextKeys.has(node.dataset.templateKey)) {
                if (deleteRow === node) clearDeleteConfirmation();
                node.remove();
            }
        }
        if (!items.length) { const note = document.createElement('p'); note.textContent = empty; container.append(note); return; }
        items.forEach((item, index) => {
            const itemKey = key(item), existing = previous.get(itemKey);
            const row = existing || document.createElement('div');
            row.dataset.templateKey = itemKey;
            if (!existing) {
                row.className = 'engagement-library-row';
                const content = document.createElement('div'); content.className = 'engagement-library-content';
                const load = document.createElement('button'); load.type = 'button'; load.className = 'engagement-load'; load.disabled = busy;
                const heading = document.createElement('strong'); heading.textContent = item.title;
                const detail = document.createElement('small'); detail.textContent = item.choices.join(' · ');
                load.append(heading, detail); load.addEventListener('click', () => { clearDeleteConfirmation(); loadTemplate(item); });
                const star = document.createElement('button'); star.type = 'button'; star.className = 'engagement-star'; star.innerHTML = starIcon; star.disabled = busy;
                star.addEventListener('click', () => toggleSaved(item, row));
                star.setAttribute('aria-expanded', 'false');
                const confirm = document.createElement('button'); confirm.type = 'button'; confirm.className = 'engagement-delete';
                confirm.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>';
                confirm.title = 'Are you sure you want to delete it?';
                confirm.setAttribute('aria-label', `Delete saved ${item.kind === 'polls' ? 'poll' : 'prediction'}: ${item.title}`);
                confirm.setAttribute('aria-hidden', 'true'); confirm.tabIndex = -1; confirm.disabled = true;
                confirm.addEventListener('click', () => deleteSaved(item));
                content.append(load, star); row.append(confirm, content);
            }
            const star = row.querySelector('.engagement-star');
            const isSaved = saved.some(value => key(value) === key(item));
            if ((!isSaved || busy) && deleteRow === row) clearDeleteConfirmation();
            star.setAttribute('aria-pressed', String(isSaved));
            star.setAttribute('aria-label', `${isSaved ? 'Unsave' : 'Save'} ${item.title}`); star.title = isSaved ? 'Unsave' : 'Save';
            row.querySelectorAll('.engagement-load, .engagement-star').forEach(button => { button.disabled = busy || removingSaved.has(itemKey); });
            if (container.children[index] !== row) container.insertBefore(row, container.children[index] || null);
            if (!existing && itemKey === animateKey) animateSavedRow(row);
        });
    }
    function renderLibrary(animateKey = '') {
        renderList(dialog.querySelector('[data-engagement-saved]'), saved.filter(item => item.kind === mode), `No saved ${mode} yet.`, animateKey);
        renderList(dialog.querySelector('[data-engagement-recent]'), recent.get(mode)?.items || [], `No recent ${mode}.`);
        syncTemplateMatches();
    }
    async function loadRecent(force = false) {
        historyController?.abort();
        const cached = recent.get(mode);
        renderLibrary();
        if (!force && cached && Date.now() - cached.loaded < 30_000) { historyStatus.textContent = ''; return; }
        const request = new AbortController(), requestedMode = mode;
        historyController = request; historyStatus.textContent = 'Loading…';
        try {
            const response = await fetch(`/channel/api/engagement/${requestedMode}`, {signal: request.signal, cache: 'no-store', headers: {Accept: 'application/json'}});
            const payload = await response.json();
            if (request.signal.aborted || !dialog.open || mode !== requestedMode) return;
            if (!response.ok) throw new Error(payload.detail || 'Recent items could not be loaded.');
            const items = (payload.items || []).map(item => ({...item, kind: requestedMode})).filter(validTemplate);
            recent.set(requestedMode, {items, loaded: Date.now()}); renderLibrary(); historyStatus.textContent = '';
        } catch (error) { if (!request.signal.aborted) historyStatus.textContent = error.message; }
    }
    function setMode(next, updateHash = true) {
        if (busy) return;
        clearDeleteConfirmation();
        mode = next;
        tabs.forEach(tab => { const selected = tab.dataset.engagementTab === mode; tab.setAttribute('aria-selected', String(selected)); tab.tabIndex = selected ? 0 : -1; });
        dialog.querySelector('#engagement-editor').setAttribute('aria-labelledby', `engagement-${mode}-tab`);
        dialog.querySelector('[data-engagement-saved-label]').textContent = `Saved ${mode}`;
        dialog.querySelector('[data-engagement-recent-label]').textContent = `Recent ${mode}`;
        dialog.querySelector('[data-engagement-hint]').textContent = mode === 'polls' ? 'Up to 5 choices · 60-character title' : 'Up to 10 choices · 45-character title';
        syncDuration(); updateControls(); updateIndicator(); message('');
        if (dialog.open) {
            if (updateHash) window.history.replaceState(null, '', `#${mode}`);
            loadRecent();
        }
    }
    tabs.forEach(tab => {
        tab.addEventListener('click', () => setMode(tab.dataset.engagementTab));
        tab.addEventListener('keydown', event => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key) || busy) return;
            event.preventDefault();
            const target = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs[1] : tabs.find(item => item !== tab);
            setMode(target.dataset.engagementTab); target.focus();
        });
    });
    add.addEventListener('click', () => { if (!add.disabled) addChoice().focus(); });
    additionalVotes.addEventListener('change', updateControls);
    form.addEventListener('input', syncTemplateMatches);
    form.addEventListener('change', syncTemplateMatches);
    save.addEventListener('click', () => {
        const item = draft(), error = validate(item);
        if (error) { message(error, true); return; }
        if (saved.some(value => key(value) === key(item))) { message('Already saved.'); return; }
        toggleSaved(item);
    });
    refresh.addEventListener('click', () => loadRecent(true));
    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (busy) return;
        const item = draft(), error = validate(item);
        if (error) { message(error, true); return; }
        busy = true; updateControls(); renderLibrary();
        tabs.forEach(tab => { tab.disabled = true; });
        [...form.querySelectorAll('input,select')].forEach(input => { input.disabled = true; });
        message(`Starting ${mode === 'polls' ? 'poll' : 'prediction'}…`);
        try {
            const body = new URLSearchParams({title: item.title, choices: JSON.stringify(item.choices), duration: String(item.duration), csrf_token: dialog.dataset.csrfToken});
            if (item.kind === 'polls') {
                body.set('channel_points_voting_enabled', String(item.channel_points_voting_enabled));
                if (item.channel_points_voting_enabled) body.set('channel_points_per_vote', String(item.channel_points_per_vote));
            }
            const response = await fetch(`/channel/api/engagement/${item.kind}`, {method: 'POST', body, headers: {Accept: 'application/json'}});
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || 'Could not confirm creation. Check Twitch before trying again.');
            if (item.kind === 'polls') [...choices.children].slice(5).forEach(row => row.remove());
            recent.delete(item.kind);
            message(`${item.kind === 'polls' ? 'Poll' : 'Prediction'} started.`);
            const source = dialog.querySelector('.engagement-editor');
            const flyer = source.cloneNode(true);
            for (const node of [flyer, ...flyer.querySelectorAll('*')]) node.removeAttribute('id');
            document.dispatchEvent(new CustomEvent('dashboard-engagement-started', {detail: {
                item: {...item, ...payload.item, kind: item.kind}, sourceRect: source.getBoundingClientRect(), sourceScrollTop: source.scrollTop, flyer
            }}));
            if (dialog.open) loadRecent(true);
        } catch (error) { message(error.message || 'Could not confirm creation. Check Twitch before trying again.', true); }
        finally {
            busy = false; tabs.forEach(tab => { tab.disabled = false; });
            [...form.querySelectorAll('input,select')].forEach(input => { input.disabled = false; });
            updateControls(); renderLibrary();
        }
    });
    function engagementRoute() {
        return ['#polls', '#predictions'].includes(window.location.hash) ? window.location.hash.slice(1) : null;
    }
    function openEngagement(next) {
        if (dialog.open) { if (mode !== next) setMode(next, false); return; }
        opener = document.querySelector(`[data-engagement-open="${next}"]`);
        dialog.showModal(); document.documentElement.classList.add('engagement-open');
        setMode(next, false); title.focus();
    }
    function syncEngagementHash() {
        const next = engagementRoute();
        if (next) openEngagement(next);
        else if (dialog.open) dialog.close();
    }
    document.querySelectorAll('[data-engagement-open]').forEach(button => button.addEventListener('click', () => {
        if (busy) return;
        const next = button.dataset.engagementOpen;
        if (window.location.hash !== `#${next}`) window.history.pushState(null, '', `#${next}`);
        openEngagement(next);
    }));
    dialog.querySelector('[data-engagement-close]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('pointerdown', event => {
        dismissedDeletePress = false;
        if (deleteRow && !deleteRow.querySelector('.engagement-delete').contains(event.target)) {
            dismissedDeletePress = true;
            clearDeleteConfirmation();
        }
    });
    dialog.addEventListener('click', event => {
        if (dismissedDeletePress || (deleteRow && !deleteRow.querySelector('.engagement-delete').contains(event.target))) {
            clearDeleteConfirmation(); dismissedDeletePress = false; backdropPress = false;
            event.preventDefault(); event.stopImmediatePropagation();
        }
    }, true);
    dialog.addEventListener('cancel', event => {
        if (!deleteRow) return;
        event.preventDefault();
        const star = deleteRow.querySelector('.engagement-star');
        clearDeleteConfirmation(); star.focus();
    });
    dialog.addEventListener('pointerdown', event => { backdropPress = event.target === dialog && outside(event); });
    function outside(event) { const rect = dialog.getBoundingClientRect(); return event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom; }
    dialog.addEventListener('pointercancel', () => { backdropPress = false; });
    dialog.addEventListener('click', event => { if (backdropPress && event.target === dialog && outside(event)) dialog.close(); backdropPress = false; });
    dialog.addEventListener('close', () => {
        if (dialog.open) return; // A newer history navigation may already have reopened it.
        clearDeleteConfirmation(); dismissedDeletePress = false; historyController?.abort(); backdropPress = false;
        document.documentElement.classList.remove('engagement-open');
        if (engagementRoute()) window.history.replaceState(null, '', window.location.pathname + window.location.search);
        opener?.focus({preventScroll: true});
    });
    new ResizeObserver(updateIndicator).observe(tabStrip);
    new ResizeObserver(updateExcludedMark).observe(choices);
    new ResizeObserver(layoutDurationLabels).observe(durationSlider);
    document.addEventListener('dashboard-engagement-updated', event => {
        recent.delete(event.detail.kind);
        if (dialog.open && mode === event.detail.kind) loadRecent(true);
    });
    addChoice(); addChoice(); setMode(mode);
    window.addEventListener('hashchange', syncEngagementHash);
    window.addEventListener('popstate', syncEngagementHash);
    syncEngagementHash();
})();
