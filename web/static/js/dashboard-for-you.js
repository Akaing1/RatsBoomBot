(() => {
    'use strict';
    const remaining = (due, now) => Math.max(0, Math.ceil(due - now));
    const formatTime = seconds => {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const rest = String(seconds % 60).padStart(2, '0');
        return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${rest}` : `${minutes}:${rest}`;
    };
    if (typeof module !== 'undefined') module.exports = { remaining, formatTime };
    if (typeof document === 'undefined') return;
    const root = document.querySelector('[data-for-you]');
    if (!root) return;
    const find = selector => root.querySelector(selector);
    const notes = find('[data-fy-notes]');
    const save = find('[data-fy-save]');
    const saveStatus = find('[data-fy-save-status]');
    const error = find('[data-fy-error]');
    const form = find('[data-fy-timer-form]');
    const dialog = document.querySelector('[data-fy-dialog]');
    const alertLabel = dialog.querySelector('[data-fy-alert-label]');
    const alertError = dialog.querySelector('[data-fy-alert-error]');
    const dismiss = dialog.querySelector('[data-fy-dismiss]');
    let state = null, dirty = false, notesRevision = 0, busy = false, pulling = false;
    let generation = 0, offset = 0, popupId = null, nextDueCheck = 0, mutationError = "";

    root.querySelectorAll('[data-fy-flip]').forEach(button => button.addEventListener('click', () => {
        const back = root.classList.toggle('is-flipped');
        find('[data-fy-front]').inert = back;
        find('[data-fy-front]').setAttribute('aria-hidden', String(back));
        find('[data-fy-back]').inert = !back;
        find('[data-fy-back]').setAttribute('aria-hidden', String(!back));
        find(back ? '[data-fy-back] [data-fy-flip]' : '[data-fy-front] [data-fy-flip]').focus();
    }));
    const tabs = [...root.querySelectorAll('[data-fy-tab]')];
    function selectTab(tab) {
        tabs.forEach(button => {
            const selected = button === tab;
            button.classList.toggle('active', selected);
            button.setAttribute('aria-selected', String(selected));
            button.tabIndex = selected ? 0 : -1;
        });
        root.querySelectorAll('[data-fy-panel]').forEach(panel => { panel.hidden = panel.dataset.fyPanel !== tab.dataset.fyTab; });
    }
    tabs.forEach((tab, index) => {
        tab.addEventListener('click', () => selectTab(tab));
        tab.addEventListener('keydown', event => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
            event.preventDefault();
            const target = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs[tabs.length - 1] : tabs[(index + (event.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
            selectTab(target); target.focus();
        });
    });
    function controls() {
        save.disabled = !state || busy || !dirty;
        notes.disabled = !state;
        [...form.elements].forEach(input => { input.disabled = !state || busy; });
        find('[data-fy-cancel]').disabled = busy;
        dismiss.disabled = busy;
    }
    async function request(data) {
        const response = await fetch('/channel/api/for-you', {
            method: data ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store',
            ...(data ? { body: new URLSearchParams({ csrf_token: root.dataset.csrfToken, ...data }) } : {}),
        });
        let payload;
        try { payload = await response.json(); } catch { throw new Error('Could not reach your workspace. Please try again.'); }
        if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : 'Please check the duration or note length.');
        return payload;
    }
    function adopt(data) {
        state = data;
        offset = data.server_now - Date.now() / 1000;
        if (!dirty) { notes.value = data.notes; notesRevision = data.notes_revision; saveStatus.textContent = 'Saved'; }
        if (popupId && popupId !== data.timer_id) { dialog.close(); popupId = null; }
        controls(); tick(false);
        if (data.timer_id && remaining(data.timer_due_at, data.server_now) === 0 && popupId !== data.timer_id) {
            popupId = data.timer_id;
            alertLabel.textContent = data.timer_label;
            alertError.textContent = '';
            if (!dialog.open) dialog.showModal();
        }
    }
    async function pull() {
        if (pulling || busy) return;
        pulling = true;
        const started = generation;
        try { const data = await request(); if (started === generation) { adopt(data); error.textContent = mutationError; } }
        catch (reason) { if (started === generation) error.textContent = reason.message || 'Workspace unavailable. Retrying…'; }
        finally { pulling = false; }
    }
    async function mutate(data, submittedNotes) {
        if (busy) return false;
        busy = true; generation += 1; controls(); mutationError = ''; error.textContent = '';
        try {
            const result = await request(data);
            if (data.action === 'notes') {
                notesRevision = result.notes_revision;
                dirty = notes.value !== submittedNotes;
                saveStatus.textContent = dirty ? 'Unsaved changes' : 'Saved';
            }
            adopt(result);
            return true;
        } catch (reason) {
            mutationError = reason.message || 'Could not save. Please try again.';
            error.textContent = mutationError;
            if (data.action === 'notes') saveStatus.textContent = 'Not saved';
            return false;
        } finally { busy = false; controls(); }
    }
    notes.addEventListener('input', () => { dirty = true; saveStatus.textContent = 'Unsaved changes'; controls(); });
    save.addEventListener('click', () => {
        if (!state || !dirty || notes.value.length > 20000) return;
        const submitted = notes.value;
        mutate({ action: 'notes', notes: submitted, revision: notesRevision }, submitted);
    });
    root.querySelectorAll('[data-fy-step]').forEach(button => button.addEventListener('click', () => {
        const [name, direction] = button.dataset.fyStep.split(':');
        const input = form.elements.namedItem(name);
        const current = Number(input.value) || 0;
        input.value = String(Math.max(Number(input.min), Math.min(Number(input.max), current + Number(direction))));
        input.dispatchEvent(new Event('input', { bubbles: true }));
    }));
    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (!state || busy || !form.reportValidity()) return;
        const values = new FormData(form);
        const totalSeconds = Number(values.get('minutes')) * 60 + Number(values.get('seconds'));
        if (totalSeconds < 1 || totalSeconds > 604800) {
            error.textContent = 'Set a timer between 1 second and 7 days.';
            return;
        }
        if (state.timer_id && !window.confirm('Replace your current timer?')) return;
        await mutate({ action: 'start', minutes: values.get('minutes'), seconds: values.get('seconds'), timer_id: state.timer_id || '' });
        // Refresh after a conflict so a stale tab can retry against the current timer.
        pull();
    });
    find('[data-fy-cancel]').addEventListener('click', async () => {
        if (state?.timer_id) { await mutate({ action: 'clear', timer_id: state.timer_id }); pull(); }
    });
    async function acknowledge() {
        if (!popupId || busy) return;
        const success = await mutate({ action: 'clear', timer_id: popupId });
        if (!success) { alertError.textContent = error.textContent; pull(); }
    }
    dismiss.addEventListener('click', acknowledge);
    dialog.addEventListener('cancel', event => { event.preventDefault(); acknowledge(); });
    function tick(checkDue = true) {
        const active = Boolean(state?.timer_id);
        find('[data-fy-running]').hidden = !active;
        find('[data-fy-summary]').hidden = !active;
        if (!active) return;
        const seconds = remaining(state.timer_due_at, Date.now() / 1000 + offset);
        find('[data-fy-reminder]').textContent = state.timer_label;
        find('[data-fy-countdown]').textContent = seconds ? formatTime(seconds) : 'Time’s up!';
        find('[data-fy-summary]').textContent = seconds ? `Your timer · ${formatTime(seconds)}` : 'Your timer is ready';
        if (checkDue && seconds === 0 && !popupId && Date.now() >= nextDueCheck) {
            nextDueCheck = Date.now() + 10000;
            pull(); // Confirm the timer was not cancelled elsewhere before opening its popup.
        }
    }
    window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
    window.addEventListener('focus', pull);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) pull(); });
    setInterval(() => tick(), 1000);
    setInterval(() => { if (!document.hidden) pull(); }, 15000);
    pull();
})();
