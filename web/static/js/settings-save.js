(() => {
    'use strict';
    const book = document.querySelector('[data-settings-book]');
    if (!book) return;
    const forms = [...book.querySelectorAll('form[method="post"]')].filter(form => {
        const url = new URL(form.getAttribute('action') || location.href, location.href);
        return url.origin === location.origin && /\/(customization|features\/toggles)$/.test(url.pathname);
    });
    forms.forEach(form => { form.dataset.settingsInlineSave = ''; });
    const status = document.createElement('p');
    status.className = 'settings-floating-status';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    status.hidden = true;
    document.body.append(status);
    let fadeTimer;
    let hideTimer;
    function notify(message, severity = 'success') {
        clearTimeout(fadeTimer); clearTimeout(hideTimer);
        status.hidden = false;
        status.classList.remove('is-fading');
        ['success', 'warning', 'error'].forEach(kind => status.classList.toggle(`is-${kind}`, kind === severity));
        status.textContent = message;
        fadeTimer = setTimeout(() => {
            status.classList.add('is-fading');
            hideTimer = setTimeout(() => { status.hidden = true; }, 250);
        }, 5000);
    }
    document.querySelectorAll('.channel-page-settings .toggle-feedback').forEach(feedback => {
        if (feedback.textContent.trim()) notify(feedback.textContent.trim(), feedback.classList.contains('error') ? 'error' : feedback.classList.contains('warning') ? 'warning' : 'success');
        feedback.remove();
    });
    function refreshState(fresh, form) {
        book.querySelectorAll('[id]').forEach(node => {
            const replacement = fresh.getElementById(node.id);
            if (replacement) node.classList.toggle('is-disabled', replacement.classList.contains('is-disabled'));
        });
        book.querySelectorAll('.settings-inline-switch').forEach(wrapper => {
            const id = wrapper.querySelector('button[id]')?.id;
            const replacement = id && fresh.getElementById(id)?.closest('.settings-inline-switch');
            if (!replacement) return;
            wrapper.replaceChildren(...[...replacement.childNodes].map(node => node.cloneNode(true)));
            const row = wrapper.closest('.settings-switch-row');
            if (row) row.classList.toggle('is-disabled', Boolean(replacement.closest('.settings-switch-row')?.classList.contains('is-disabled')));
        });
        const setting = form.querySelector('[name="setting_name"]')?.value;
        const savedForm = setting && [...fresh.querySelectorAll('[name="setting_name"]')].find(input => input.value === setting)?.form;
        // The follow-raid preference submits its value through the switch itself.
        const switchButton = form.querySelector('button[role="switch"][name="value"]');
        const savedButton = savedForm?.querySelector('button[role="switch"][name="value"]');
        if (switchButton && savedButton) {
            switchButton.value = savedButton.value;
            switchButton.className = savedButton.className;
            switchButton.replaceChildren(...[...savedButton.childNodes].map(node => node.cloneNode(true)));
            switchButton.setAttribute('aria-checked', savedButton.getAttribute('aria-checked'));
        }
        book.querySelectorAll('[data-settings-page]').forEach(page => {
            const replacement = [...fresh.querySelectorAll('[data-settings-page]')].find(node => node.dataset.settingsPage === page.dataset.settingsPage);
            const notice = replacement?.querySelector('.settings-blocked-notice');
            page.querySelector('.settings-blocked-notice')?.remove();
            if (notice) page.querySelector('.settings-page-heading')?.after(notice.cloneNode(true));
        });
    }
    const pending = new WeakSet();
    let queue = Promise.resolve();
    book.addEventListener('submit', event => {
        const form = event.target;
        if (event.defaultPrevented || !forms.includes(form)) return;
        event.preventDefault();
        if (pending.has(form)) return;
        const data = new FormData(form);
        book.dispatchEvent(new CustomEvent('settings-build-save', {detail: {form, data}}));
        const snapshot = JSON.stringify([...data]);
        if (event.submitter?.name) data.append(event.submitter.name, event.submitter.value);
        const buttons = [...form.elements].filter(node => node instanceof HTMLButtonElement).map(button => [button, button.disabled]);
        buttons.forEach(([button]) => { button.disabled = true; });
        pending.add(form);
        form.setAttribute('aria-busy', 'true');
        queue = queue.then(async () => {
            try {
                const response = await fetch(form.getAttribute('action'), {method: 'POST', body: data, credentials: 'same-origin'});
                const url = new URL(response.url);
                const result = url.searchParams.get('setting_result') || url.searchParams.get('toggle_result');
                const message = url.searchParams.get('setting_message') || url.searchParams.get('toggle_message');
                if (!response.ok || result === 'error') throw new Error(message || 'Could not save this setting. Try again.');
                const fresh = new DOMParser().parseFromString(await response.text(), 'text/html');
                if (result !== 'success' || !fresh.querySelector('[data-settings-book]')) throw Object.assign(new Error('Could not confirm the save. Reload settings before trying again.'), {severity: 'warning'});
                refreshState(fresh, form);
                book.dispatchEvent(new CustomEvent('settings-saved', {detail: {form, snapshot}}));
                notify(message || 'Saved.');
            } catch (error) {
                book.dispatchEvent(new CustomEvent('settings-save-failed', {detail: {form}}));
                notify(error.message || 'Could not save this setting. Try again.', error.severity || 'error');
            } finally {
                buttons.forEach(([button, disabled]) => { if (button.isConnected) button.disabled = disabled; });
                form.removeAttribute('aria-busy');
                pending.delete(form);
            }
        });
    });
    window.addEventListener('pagehide', () => { clearTimeout(fadeTimer); clearTimeout(hideTimer); }, {once: true});
})();
