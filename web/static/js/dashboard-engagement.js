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
    const showArchived = dialog.querySelector('[data-engagement-show-archived]');
    const add = dialog.querySelector('[data-engagement-add]');
    const addControl = dialog.querySelector('[data-engagement-add-control]');
    const start = dialog.querySelector('[data-engagement-start]');
    const status = dialog.querySelector('[data-engagement-status]');
    const historyStatus = dialog.querySelector('[data-engagement-history-status]');
    const refresh = dialog.querySelector('[data-engagement-refresh]');
    const storageKey = `dashboard-engagement:${dialog.dataset.channelId}:v1`;
    const archiveStorageKey = `dashboard-engagement-archived:${dialog.dataset.channelId}:v1`;
    let archived = new Set(), includeArchived = false;
    try {
        const stored = JSON.parse(localStorage.getItem(archiveStorageKey) || '[]');
        if (Array.isArray(stored)) archived = new Set(stored.filter(value => typeof value === 'string' && /^(polls|predictions):[A-Za-z0-9_-]{1,100}$/.test(value)));
    } catch (_) {}
    const starIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 2 3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2Z"/></svg>';
    let mode = 'predictions', busy = false, opener = null, historyRequest = null, backdropPress = false;
    const recent = new Map();
    let saved = [];
    let deleteRow = null;
    let dismissedDeletePress = false;
    const removingSaved = new Set();
    const archiving = new Set();
    const libraryItems = new WeakMap();
    let lastDraftKey = null;
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
    function syncTemplateMatches(force = false) {
        const currentKey = key(draft());
        if (force !== true && currentKey === lastDraftKey) return;
        lastDraftKey = currentKey;
        dialog.querySelectorAll('.engagement-library-row').forEach(row => {
            const matches = row.dataset.templateKey === currentKey;
            row.classList.toggle('is-matching', matches);
            const load = row.querySelector('.engagement-load');
            if (load.getAttribute('aria-pressed') !== String(matches)) load.setAttribute('aria-pressed', String(matches));
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
        showArchived.disabled = busy;
        const singular = mode === 'polls' ? 'poll' : 'prediction';
        start.textContent = busy ? 'Starting…' : `Start ${singular}`;
        save.textContent = `Save this ${singular}`;
        syncTemplateMatches();
    }
    function addChoice(value = '', update = true) {
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
        row.append(number, label, remove); choices.append(row);
        if (update) updateControls();
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
    function animateLibraryRow(row, removing = false, sideways = false) {
        if (!row || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return null;
        const expanded = {height: `${row.getBoundingClientRect().height}px`, opacity: 1, transform: sideways ? 'translateX(0)' : 'translateY(0)', marginBottom: '0px'};
        const collapsed = sideways ? {...expanded, transform: 'translateX(-100%)'}
            : {height: '0px', opacity: 0, transform: 'translateY(-14px)', marginBottom: '-8px'};
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
        const animation = animateLibraryRow(row, true);
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
        choices.replaceChildren(); item.choices.forEach(value => addChoice(value, false)); updateControls();
        message('Loaded.'); title.focus();
    }
    async function toggleArchive(item, row) {
        const id = `${item.kind}:${item.id}`;
        if (busy || archiving.has(id)) return;
        const next = new Set(archived);
        if (next.has(id)) next.delete(id); else next.add(id);
        try { localStorage.setItem(archiveStorageKey, JSON.stringify([...next])); }
        catch (_) { message('Could not update archived items in this browser.', true); return; }
        archived = next;
        archiving.add(id);
        const hadFocus = row.contains(document.activeElement);
        clearDeleteConfirmation();
        row.classList.add('is-removing');
        row.querySelectorAll('button').forEach(button => { button.disabled = true; });
        row.querySelectorAll('a').forEach(link => { link.tabIndex = -1; link.setAttribute('aria-disabled', 'true'); });
        const animation = animateLibraryRow(row, true, true);
        if (animation) await animation.finished.catch(() => {});
        animation?.cancel();
        archiving.delete(id);
        row.classList.remove('is-removing');
        renderLibrary();
        if (hadFocus && dialog.open && mode === item.kind) showArchived.focus({preventScroll: true});
    }
    function renderList(container, items, empty, savedKeys, animateKey = '') {
        if (!items.length) {
            if (container.children.length === 1 && container.firstChild.tagName === 'P' && container.firstChild.textContent === empty) return;
            if (deleteRow && container.contains(deleteRow)) clearDeleteConfirmation();
            const note = document.createElement('p'); note.textContent = empty; container.replaceChildren(note); return;
        }
        const isRecent = container.hasAttribute('data-engagement-recent');
        const entryKey = item => isRecent && /^[A-Za-z0-9_-]{1,100}$/.test(item.id || '') ? `${item.kind}:${item.id}` : key(item);
        const previous = new Map([...container.children].filter(node => node.dataset.entryKey).map(row => [row.dataset.entryKey, row]));
        const nextKeys = new Set(items.map(entryKey));
        for (const node of [...container.children]) {
            if (!nextKeys.has(node.dataset.entryKey)) {
                if (deleteRow === node) clearDeleteConfirmation();
                node.remove();
            }
        }
        items.forEach((item, index) => {
            const itemKey = key(item), rowKey = entryKey(item), existing = previous.get(rowKey);
            const row = existing || document.createElement('div');
            const changed = row.dataset.templateKey !== itemKey;
            libraryItems.set(row, item);
            row.dataset.templateKey = itemKey;
            row.dataset.entryKey = rowKey;
            if (!existing) {
                row.className = 'engagement-library-row';
                const content = document.createElement('div'); content.className = 'engagement-library-content';
                const load = document.createElement('button'); load.type = 'button'; load.className = 'engagement-load'; load.disabled = busy;
                const heading = document.createElement('strong'); heading.textContent = item.title;
                const detail = document.createElement('small'); detail.textContent = item.choices.join(' · ');
                load.append(heading, detail);
                const star = document.createElement('button'); star.type = 'button'; star.className = 'engagement-star'; star.innerHTML = starIcon; star.disabled = busy;
                star.setAttribute('aria-expanded', 'false');
                const confirm = document.createElement('button'); confirm.type = 'button'; confirm.className = 'engagement-delete';
                confirm.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>';
                confirm.title = 'Are you sure you want to delete it?';
                confirm.setAttribute('aria-label', `Delete saved ${item.kind === 'polls' ? 'poll' : 'prediction'}: ${item.title}`);
                confirm.setAttribute('aria-hidden', 'true'); confirm.tabIndex = -1; confirm.disabled = true;
                content.append(load, star); row.append(confirm, content);
                if (isRecent && /^[A-Za-z0-9_-]{1,100}$/.test(item.id || '')) {
                    const archive = document.createElement('button'); archive.type = 'button'; archive.className = 'engagement-archive';
                    content.append(archive);
                    const results = document.createElement('a'); results.className = 'engagement-library-results';
                    results.textContent = 'See results'; results.href = `#${item.kind}-summary=${item.id}`;
                    results.setAttribute('aria-label', `See results: ${item.title}`);
                    content.insertBefore(results, star);
                }
            }
            if (existing && changed) {
                row.querySelector('.engagement-load strong').textContent = item.title;
                row.querySelector('.engagement-load small').textContent = item.choices.join(' · ');
                row.querySelector('.engagement-delete').setAttribute('aria-label', `Delete saved ${item.kind === 'polls' ? 'poll' : 'prediction'}: ${item.title}`);
                row.querySelector('.engagement-library-results')?.setAttribute('aria-label', `See results: ${item.title}`);
            }
            const star = row.querySelector('.engagement-star');
            const isSaved = savedKeys.has(itemKey);
            if ((!isSaved || busy) && deleteRow === row) clearDeleteConfirmation();
            star.setAttribute('aria-pressed', String(isSaved));
            star.setAttribute('aria-label', `${isSaved ? 'Unsave' : 'Save'} ${item.title}`); star.title = isSaved ? 'Unsave' : 'Save';
            row.querySelectorAll('.engagement-load, .engagement-star').forEach(button => { button.disabled = busy || removingSaved.has(itemKey); });
            const results = row.querySelector('.engagement-library-results');
            if (results) { results.setAttribute('aria-disabled', String(busy)); results.tabIndex = busy ? -1 : 0; }
            const archive = row.querySelector('.engagement-archive');
            if (archive) {
                const isArchived = archived.has(rowKey);
                row.classList.toggle('is-archived', isArchived);
                if (archive.dataset.archived !== String(isArchived)) {
                    archive.dataset.archived = String(isArchived);
                    archive.innerHTML = isArchived
                        ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 4-5 5 5 5M3 9h11a7 7 0 0 1 0 14"/></svg>'
                        : '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>';
                }
                archive.title = isArchived ? 'Restore' : 'Archive';
                archive.setAttribute('aria-label', `${isArchived ? 'Restore' : 'Archive'} ${item.kind === 'polls' ? 'poll' : 'prediction'}: ${item.title}`);
                archive.disabled = busy;
            }
            if (container.children[index] !== row) container.insertBefore(row, container.children[index] || null);
            if (!existing && itemKey === animateKey) animateLibraryRow(row);
        });
    }
    function renderLibrary(animateKey = '') {
        const savedKeys = new Set(saved.map(key));
        renderList(dialog.querySelector('[data-engagement-saved]'), saved.filter(item => item.kind === mode), `No saved ${mode} yet.`, savedKeys, animateKey);
        const items = recent.get(mode)?.items || [];
        renderList(dialog.querySelector('[data-engagement-recent]'), items.filter(item => archived.has(`${item.kind}:${item.id}`) === includeArchived), includeArchived ? `No archived ${mode}.` : `No recent ${mode}.`, savedKeys);
        dialog.querySelector('[data-engagement-recent-label]').textContent = `${includeArchived ? 'Archived' : 'Recent'} ${mode}`;
        syncTemplateMatches(true);
    }
    function loadRecent(force = false, invalidate = false) {
        const cached = recent.get(mode);
        renderLibrary();
        if (!invalidate && historyRequest?.mode === mode && !historyRequest.controller.signal.aborted) return historyRequest.promise;
        historyRequest?.controller.abort();
        if (!force && cached && Date.now() - cached.loaded < 30_000) { historyStatus.textContent = ''; return; }
        const request = {controller: new AbortController(), mode, promise: null};
        historyRequest = request; historyStatus.textContent = 'Loading…';
        request.promise = (async () => {
            try {
                const response = await fetch(`/channel/api/engagement/${request.mode}`, {signal: request.controller.signal, cache: 'no-store', headers: {Accept: 'application/json'}});
                const payload = await response.json();
                if (request.controller.signal.aborted || !dialog.open || mode !== request.mode) return;
                if (!response.ok) throw new Error(payload.detail || 'Recent items could not be loaded.');
                const items = (payload.items || []).map(item => ({...item, kind: request.mode})).filter(validTemplate);
                recent.set(request.mode, {items, loaded: Date.now()}); renderLibrary(); historyStatus.textContent = '';
            } catch (error) { if (!request.controller.signal.aborted) historyStatus.textContent = error.message; }
            finally { if (historyRequest === request) historyRequest = null; }
        })();
        return request.promise;
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
    dialog.addEventListener('click', event => {
        const row = event.target.closest('.engagement-library-row');
        const item = row && libraryItems.get(row);
        if (!item) return;
        if (busy || row.classList.contains('is-removing')) { event.preventDefault(); return; }
        if (event.target.closest('.engagement-load')) { clearDeleteConfirmation(); loadTemplate(item); }
        else if (event.target.closest('.engagement-star')) toggleSaved(item, row);
        else if (event.target.closest('.engagement-delete')) deleteSaved(item);
        else if (event.target.closest('.engagement-archive')) toggleArchive(item, row);
    });
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
    showArchived.addEventListener('click', () => {
        if (busy) return;
        includeArchived = !includeArchived;
        showArchived.setAttribute('aria-pressed', String(includeArchived));
        showArchived.title = includeArchived ? 'Hide archived' : 'Show archived';
        showArchived.setAttribute('aria-label', showArchived.title);
        clearDeleteConfirmation(); renderLibrary();
    });
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
            const detail = {item: {...item, ...payload.item, kind: item.kind}};
            if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
                const source = dialog.querySelector('.engagement-editor'), flyer = source.cloneNode(true);
                for (const node of [flyer, ...flyer.querySelectorAll('*')]) node.removeAttribute('id');
                Object.assign(detail, {sourceRect: source.getBoundingClientRect(), sourceScrollTop: source.scrollTop, flyer});
            }
            document.dispatchEvent(new CustomEvent('dashboard-engagement-started', {detail}));
            if (dialog.open) loadRecent(true, true);
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
        clearDeleteConfirmation(); dismissedDeletePress = false; historyRequest?.controller.abort(); backdropPress = false;
        document.documentElement.classList.remove('engagement-open');
        if (engagementRoute()) window.history.replaceState(null, '', window.location.pathname + window.location.search);
        opener?.focus({preventScroll: true});
    });
    const resizeObservers = [[updateIndicator, tabStrip], [updateExcludedMark, choices], [layoutDurationLabels, durationSlider]]
        .map(([callback, element]) => ({observer: new ResizeObserver(callback), element}));
    function observeLayout() { resizeObservers.forEach(({observer, element}) => observer.observe(element)); }
    observeLayout();
    window.addEventListener('pagehide', () => {
        historyRequest?.controller.abort();
        resizeObservers.forEach(({observer}) => observer.disconnect());
    });
    window.addEventListener('pageshow', event => { if (event.persisted) observeLayout(); });
    document.addEventListener('dashboard-engagement-updated', event => {
        recent.delete(event.detail.kind);
        if (dialog.open && mode === event.detail.kind) loadRecent(true, true);
    });
    document.addEventListener('dashboard-engagement-repeat', event => {
        const item = event.detail;
        if (busy || !validTemplate(item)) return;
        window.history.pushState(null, '', `#${item.kind}`);
        openEngagement(item.kind);
        loadTemplate(item);
        form.requestSubmit();
    });
    addChoice(); addChoice(); setMode(mode);
    window.addEventListener('hashchange', syncEngagementHash);
    window.addEventListener('popstate', syncEngagementHash);
    syncEngagementHash();
})();
