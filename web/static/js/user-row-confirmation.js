(() => {
    let active = null;
    const approved = new WeakSet();
    function close(focus = false) {
        if (!active) return;
        const {wrapper, button, confirm, content, title, label} = active;
        wrapper.classList.remove('is-confirming');
        button.replaceChildren(...content);
        button.setAttribute('aria-expanded', 'false');
        if (label === null) button.removeAttribute('aria-label'); else button.setAttribute('aria-label', label);
        if (title === null) button.removeAttribute('title'); else button.title = title;
        confirm.disabled = true; confirm.tabIndex = -1; confirm.setAttribute('aria-hidden', 'true');
        active = null;
        if (focus && button.isConnected) button.focus({preventScroll: true});
    }
    function open(button) {
        const row = button.closest('.user-list-row');
        if (!row) return;
        let wrapper = button.closest('.user-row-remove-action');
        if (!wrapper) {
            wrapper = document.createElement('span'); wrapper.className = 'user-row-remove-action';
            wrapper.style.setProperty('--remove-action-width', `${Math.ceil(button.getBoundingClientRect().width)}px`);
            button.before(wrapper); wrapper.append(button);
            const confirm = document.createElement('button');
            confirm.type = 'button'; confirm.className = 'user-row-remove-confirm';
            confirm.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';
            confirm.dataset.userRowConfirm = '';
            confirm.title = 'Are you sure you want to remove this user?';
            confirm.setAttribute('aria-label', 'Confirm removal'); wrapper.append(confirm);
        }
        const confirm = wrapper.querySelector('[data-user-row-confirm]');
        active = {wrapper, button, confirm, content: [...button.childNodes], title: button.getAttribute('title'), label: button.getAttribute('aria-label')};
        button.setAttribute('aria-expanded', 'true');
        confirm.disabled = false; confirm.tabIndex = 0; confirm.setAttribute('aria-hidden', 'false');
        // Establish the closed layout before the first opening transition.
        void wrapper.offsetWidth;
        wrapper.classList.add('is-confirming');
    }
    document.addEventListener('click', event => {
        const button = event.target.closest('[data-user-row-remove]');
        if (button && approved.has(button)) return;
        const confirm = event.target.closest('[data-user-row-confirm]');
        if (confirm && active?.confirm === confirm) {
            event.preventDefault(); event.stopImmediatePropagation();
            const original = active.button;
            close(); approved.add(original);
            try { original.click(); } finally { approved.delete(original); }
            return;
        }
        const same = button && active?.button === button;
        close();
        if (!button || button.disabled) return;
        event.preventDefault(); event.stopImmediatePropagation();
        if (!same) open(button);
    }, true);
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && active) { event.preventDefault(); close(true); }
    });
    window.addEventListener('pagehide', () => close(), {once: true});
})();
