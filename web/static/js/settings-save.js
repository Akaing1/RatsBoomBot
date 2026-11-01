(() => {
    'use strict';
    const book = document.querySelector('[data-settings-book]');
    if (!book) return;
    function isInlineForm(form) {
        if (!(form instanceof HTMLFormElement)) return false;
        const url = new URL(form.getAttribute('action') || location.href, location.href);
        return form.method === 'post' && url.origin === location.origin && /\/(customization|features\/toggles|viewer-queue\/blacklist|protected-users\/(add|remove))$/.test(url.pathname);
    }
    book.querySelectorAll('form[method="post"]').forEach(form => {
        if (isInlineForm(form)) form.dataset.settingsInlineSave = '';
    });
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
    // Redirect feedback is a one-time notification, not part of the settings link.
    const cleanURL = new URL(location.href);
    for (const name of ['setting', 'toggle', 'protected', 'identity', 'youtube']) {
        cleanURL.searchParams.delete(`${name}_result`);
        cleanURL.searchParams.delete(`${name}_message`);
    }
    if (cleanURL.href !== location.href) history.replaceState(history.state, '', cleanURL);

    function refreshState(fresh, form) {
        book.querySelectorAll('[id]').forEach(node => {
            const replacement = fresh.getElementById(node.id);
            if (replacement) node.classList.toggle('is-disabled', replacement.classList.contains('is-disabled'));
        });
        book.querySelectorAll('.settings-inline-switch').forEach(wrapper => {
            const id = wrapper.querySelector('button[id]')?.id;
            const replacement = id && fresh.getElementById(id)?.closest('.settings-inline-switch');
            if (!replacement) return;
            if (!wrapper.isEqualNode(replacement)) wrapper.replaceChildren(...[...replacement.childNodes].map(node => node.cloneNode(true)));
            const row = wrapper.closest('.settings-switch-row');
            if (row) row.classList.toggle('is-disabled', Boolean(replacement.closest('.settings-switch-row')?.classList.contains('is-disabled')));
        });
        // The follow-raid preference submits its value through the switch itself.
        const switchButton = form.querySelector('button[role="switch"][name="value"]');
        const setting = switchButton && form.querySelector('[name="setting_name"]')?.value;
        const savedForm = setting && [...fresh.querySelectorAll('[name="setting_name"]')].find(input => input.value === setting)?.form;
        const savedButton = savedForm?.querySelector('button[role="switch"][name="value"]');
        if (switchButton && savedButton) {
            switchButton.value = savedButton.value;
            switchButton.className = savedButton.className;
            switchButton.replaceChildren(...[...savedButton.childNodes].map(node => node.cloneNode(true)));
            switchButton.setAttribute('aria-checked', savedButton.getAttribute('aria-checked'));
        }
        const freshPages = new Map([...fresh.querySelectorAll('[data-settings-page]')].map(page => [page.dataset.settingsPage, page]));
        book.querySelectorAll('[data-settings-page]').forEach(page => {
            const replacement = freshPages.get(page.dataset.settingsPage);
            const notice = replacement?.querySelector('.settings-blocked-notice');
            const current = page.querySelector('.settings-blocked-notice');
            if ((!notice && !current) || (notice && current?.isEqualNode(notice))) return;
            current?.remove();
            if (notice) page.querySelector('.settings-page-heading')?.after(notice.cloneNode(true));
        });
    }
    const pending = new WeakSet();
    let queue = Promise.resolve();
    book.addEventListener('submit', event => {
        const form = event.target;
        if (event.defaultPrevented || !isInlineForm(form)) return;
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
                const result = url.searchParams.get('setting_result') || url.searchParams.get('toggle_result') || url.searchParams.get('protected_result');
                const message = url.searchParams.get('setting_message') || url.searchParams.get('toggle_message') || url.searchParams.get('protected_message');
                if (!response.ok || result === 'error') throw new Error(message || 'Could not save this setting. Try again.');
                const fresh = new DOMParser().parseFromString(await response.text(), 'text/html');
                if (result !== 'success' || !fresh.querySelector('[data-settings-book]')) throw Object.assign(new Error('Could not confirm the save. Reload settings before trying again.'), {severity: 'warning'});
                if (form.hasAttribute('data-settings-immediate-action')) {
                    const selector = form.dataset.settingsImmediateAction === 'protected-users' ? '[data-protected-user-members]' : '[data-queue-blacklist-members]';
                    const current = book.querySelector(selector);
                    const replacement = fresh.querySelector(selector);
                    if (!current || !replacement) throw new Error('Could not update the list. Reload settings to check it.');
                    current.replaceChildren(...[...replacement.childNodes].map(node => node.cloneNode(true)));
                    const username = form.querySelector('input[name="username"]');
                    if (data.get('action') === 'add' && username?.value === data.get('username')) username.value = '';
                }
                if (!form.hasAttribute('data-settings-immediate-action')) refreshState(fresh, form);
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
