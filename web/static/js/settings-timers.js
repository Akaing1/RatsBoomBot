(() => {
    const form = document.querySelector('[data-timer-manager]');
    if (!form) return;
    const list = form.querySelector('[data-timer-list]');
    const template = document.getElementById('settings-timer-row-template');
    const draft = form.querySelector('[data-new-message]');
    function sync() {
        const rows = [...list.querySelectorAll('.settings-timer-row')];
        form.querySelector('[data-timer-value]').value = JSON.stringify(rows.map((row, index) => {
            const input = row.querySelector('[data-timer-message]');
            const kind = row.querySelector('[data-timer-kind]').value;
            const enabled = row.querySelector('[data-timer-enabled]').checked;
            const button = row.querySelector('[data-toggle-timer]');
            row.querySelector('[data-timer-preview]').textContent = input.value.trim() || 'Empty timer';
            row.querySelector('[data-timer-color-label]').hidden = kind !== 'announcement';
            input.setAttribute('aria-label', `Timer message ${index + 1}`);
            button.setAttribute('aria-label', `Enable timer ${index + 1}`);
            button.setAttribute('aria-checked', String(enabled));
            button.textContent = enabled ? 'Enabled' : 'Disabled';
            button.classList.toggle('enabled', enabled); button.classList.toggle('disabled', !enabled);
            return [input.value.trim(), kind, row.querySelector('[data-timer-color]').value, enabled];
        }));
        form.querySelector('[data-timer-empty]').hidden = rows.length > 0;
        form.querySelector('[data-new-color-label]').hidden = form.querySelector('[data-new-kind]').value !== 'announcement';
    }
    form.addEventListener('input', event => {
        if (event.target.matches('textarea')) event.target.value = event.target.value.replace(/[\r\n]+/g, ' ');
        sync();
    });
    form.addEventListener('change', sync);
    form.addEventListener('click', event => {
        const toggle = event.target.closest('[data-toggle-timer]');
        const remove = event.target.closest('[data-remove-timer]');
        if (toggle) {
            const input = toggle.closest('.settings-timer-row').querySelector('[data-timer-enabled]');
            input.checked = !input.checked; sync(); form.requestSubmit();
        } else if (remove) {
            remove.closest('.settings-timer-row').remove(); sync();
            form.dispatchEvent(new Event('input', {bubbles: true}));
        }
    });
    form.querySelector('[data-create-timer]').addEventListener('click', () => {
        draft.setCustomValidity(draft.value.trim() ? '' : 'Enter a timer message.');
        if (!draft.reportValidity()) return;
        const row = template.content.firstElementChild.cloneNode(true);
        row.querySelector('[data-timer-message]').value = draft.value.trim();
        row.querySelector('[data-timer-kind]').value = form.querySelector('[data-new-kind]').value;
        row.querySelector('[data-timer-color]').value = form.querySelector('[data-new-color]').value;
        list.append(row); draft.value = ''; sync(); form.requestSubmit();
    });
    draft.addEventListener('input', () => draft.setCustomValidity(''));
    form.addEventListener('submit', sync);
    sync();
})();
