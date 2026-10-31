(() => {
    const form = document.querySelector('[data-timer-manager]');
    if (!form) return;
    const book = form.closest('[data-settings-book]');
    const list = form.querySelector('[data-timer-list]');
    const template = document.getElementById('settings-timer-row-template');
    const draft = form.querySelector('[data-new-message]');
    const saved = new Map();
    const selectors = ['[data-timer-message]', '[data-timer-kind]', '[data-timer-color]', '[data-timer-enabled]', '[data-timer-interval]', '[data-timer-require-chat]', '[data-timer-minimum-messages]'];
    let operation;
    let submitted;
    let confirming;
    const rows = () => [...list.querySelectorAll('.settings-timer-row')];
    function renderSwitch(button, enabled, short = false) {
        button.setAttribute('aria-checked', String(enabled));
        button.classList.toggle('live', enabled);
        button.querySelector('.queue-state-current').textContent = short ? enabled ? 'On' : 'Off' : enabled ? 'Enabled' : 'Disabled';
        button.querySelector('.queue-state-alternate').textContent = short ? enabled ? 'Off' : 'On' : enabled ? 'Disable' : 'Enable';
    }
    function read(row) {
        return selectors.map((selector, index) => {
            const input = row.querySelector(selector);
            if (input.type === 'checkbox') return input.checked;
            if (input.type === 'number') return Number(input.value);
            return index === 0 ? input.value.trim() : input.value;
        });
    }
    function restore(row, value) {
        selectors.forEach((selector, index) => {
            const input = row.querySelector(selector);
            if (input.type === 'checkbox') input.checked = value[index]; else input.value = value[index];
            input.setCustomValidity('');
        });
        row.querySelector('[data-timer-message]').dispatchEvent(new Event('input', {bubbles: true}));
    }
    function sync() {
        const values = rows().map((row, index) => {
            const value = read(row);
            row.querySelector('[data-timer-color-label]').hidden = value[1] !== 'announcement';
            row.querySelector('[data-timer-message]').setAttribute('aria-label', `Timer message ${index + 1}`);
            const toggle = row.querySelector('[data-toggle-timer]');
            toggle.setAttribute('aria-label', `Enable timer ${index + 1}`);
            renderSwitch(toggle, value[3]);
            renderSwitch(row.querySelector('[data-toggle-timer-chat]'), value[5], true);
            const baseline = saved.get(row);
            // Enabled changes save immediately and should not reveal draft actions.
            const dirty = !baseline || value.some((entry, index) => index !== 3 && entry !== baseline[index]);
            const actions = row.querySelector('[data-timer-edit-actions]');
            actions.classList.toggle('is-visible', dirty);
            actions.inert = !dirty;
            actions.setAttribute('aria-hidden', String(!dirty));
            if (!actions.classList.contains('is-ready')) { void actions.offsetHeight; actions.classList.add('is-ready'); }
            return value;
        });
        form.querySelector('[data-timer-value]').value = JSON.stringify(values);
        form.querySelector('[data-timer-empty]').hidden = values.length > 0;
        form.querySelector('[data-new-color-label]').hidden = form.querySelector('[data-new-kind]').value !== 'announcement';
        renderSwitch(form.querySelector('[data-toggle-new-chat]'), form.querySelector('[data-new-require-chat]').checked, true);
    }
    function changed() { sync(); form.dispatchEvent(new Event('input', {bubbles: true})); }
    function valid(row) {
        const message = row.querySelector('[data-timer-message]');
        message.setCustomValidity(message.value.trim() ? '' : 'Enter a timer message.');
        return [...row.querySelectorAll('input, textarea, select')].every(input => input.reportValidity());
    }
    function persist(next) {
        if (form.getAttribute('aria-busy') === 'true') return;
        operation = next;
        changed();
        form.requestSubmit();
    }
    function closeConfirmation() {
        if (!confirming) return;
        confirming.classList.remove('is-delete-pending');
        const confirm = confirming.querySelector('[data-confirm-remove-timer]');
        confirm.disabled = true; confirm.tabIndex = -1; confirm.setAttribute('aria-hidden', 'true');
        confirming.querySelector('[data-remove-timer]').setAttribute('aria-expanded', 'false');
        confirming = null;
    }
    form.addEventListener('input', event => {
        if (event.target.matches('textarea')) {
            event.target.value = event.target.value.replace(/[\r\n]+/g, ' ');
            event.target.setCustomValidity('');
        }
        sync();
    });
    form.addEventListener('change', sync);
    form.addEventListener('click', event => {
        if (event.target.closest('[data-toggle-new-chat]')) {
            const input = form.querySelector('[data-new-require-chat]');
            input.checked = !input.checked; sync(); return;
        }
        const row = event.target.closest('.settings-timer-row');
        if (!row) return;
        if (event.target.closest('[data-save-timer]')) {
            if (valid(row)) persist({kind: 'save', row, value: read(row)});
        } else if (event.target.closest('[data-cancel-timer]')) {
            if (saved.has(row)) restore(row, saved.get(row)); else row.remove();
            changed();
        } else if (event.target.closest('[data-toggle-timer-chat]')) {
            const input = row.querySelector('[data-timer-require-chat]');
            input.checked = !input.checked; changed();
        } else if (event.target.closest('[data-toggle-timer]')) {
            const input = row.querySelector('[data-timer-enabled]');
            if (!saved.has(row) && !valid(row)) return;
            input.checked = !input.checked;
            const value = [...(saved.get(row) || read(row))];
            value[3] = input.checked;
            persist({kind: 'toggle', row, value});
        } else if (event.target.closest('[data-confirm-remove-timer]')) {
            closeConfirmation();
            if (saved.has(row)) persist({kind: 'delete', row}); else { row.remove(); changed(); }
        } else if (event.target.closest('[data-remove-timer]')) {
            closeConfirmation(); confirming = row;
            row.classList.add('is-delete-pending');
            row.querySelector('[data-remove-timer]').setAttribute('aria-expanded', 'true');
            const confirm = row.querySelector('[data-confirm-remove-timer]');
            confirm.disabled = false; confirm.tabIndex = 0; confirm.setAttribute('aria-hidden', 'false');
        }
    });
    document.addEventListener('click', event => {
        if (!confirming || event.target.closest('[data-confirm-remove-timer]')) return;
        const same = event.target.closest('[data-remove-timer]')?.closest('.settings-timer-row') === confirming;
        closeConfirmation();
        if (same) { event.preventDefault(); event.stopPropagation(); }
    }, true);
    document.addEventListener('keydown', event => { if (event.key === 'Escape') closeConfirmation(); });
    form.querySelector('[data-create-timer]').addEventListener('click', () => {
        draft.setCustomValidity(draft.value.trim() ? '' : 'Enter a timer message.');
        if (!draft.reportValidity() || ![...form.querySelectorAll('[data-new-interval], [data-new-minimum-messages]')].every(input => input.value && input.reportValidity())) return;
        const row = template.content.firstElementChild.cloneNode(true);
        const value = [draft.value.trim(), form.querySelector('[data-new-kind]').value, form.querySelector('[data-new-color]').value, true,
            Number(form.querySelector('[data-new-interval]').value), form.querySelector('[data-new-require-chat]').checked, Number(form.querySelector('[data-new-minimum-messages]').value)];
        list.append(row); restore(row, value); draft.value = '';
        persist({kind: 'save', row, value});
    });
    form.addEventListener('submit', event => { sync(); if (!operation) event.preventDefault(); });
    book.addEventListener('settings-build-save', event => {
        if (event.detail.form !== form || !operation) return;
        submitted = operation; operation = null;
        const values = rows().flatMap(row => row === submitted.row ? submitted.kind === 'delete' ? [] : [submitted.value] : saved.has(row) ? [saved.get(row)] : []);
        event.detail.data.set('value', JSON.stringify(values));
    });
    book.addEventListener('settings-saved', event => {
        if (event.detail.form !== form || !submitted) return;
        if (submitted.kind === 'delete') { saved.delete(submitted.row); submitted.row.remove(); }
        else saved.set(submitted.row, submitted.value);
        submitted = null; changed();
    });
    book.addEventListener('settings-save-failed', event => {
        if (event.detail.form !== form || !submitted) return;
        if (submitted.kind === 'toggle' && saved.has(submitted.row)) submitted.row.querySelector('[data-timer-enabled]').checked = saved.get(submitted.row)[3];
        submitted = null; changed();
    });
    rows().forEach(row => saved.set(row, read(row)));
    sync();
})();
