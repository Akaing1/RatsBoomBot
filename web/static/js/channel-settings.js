(() => {
    'use strict';
    const book = document.querySelector('[data-settings-book]');
    if (!book) return;
    const tabs = [...book.querySelectorAll('[data-settings-tab]')];
    const pages = [...book.querySelectorAll('[data-settings-page]')];
    const scroller = book.querySelector('.settings-pages');
    const scrollPositions = new Map();
    let activeSection = book.dataset.selected;
    const tablist = book.querySelector('.settings-tabs');
    const storageKey = `ratsboombot-settings:${book.dataset.channel}`;
    tablist.setAttribute('aria-orientation', 'horizontal');
    function select(key, updateURL = true) {
        if (!tabs.some(tab => tab.dataset.settingsTab === key)) return;
        scrollPositions.set(activeSection, scroller.scrollTop);
        activeSection = key;
        tabs.forEach(tab => {
            const active = tab.dataset.settingsTab === key;
            tab.setAttribute('aria-selected', String(active));
            tab.tabIndex = active ? 0 : -1;
        });
        pages.forEach(page => { page.hidden = page.dataset.settingsPage !== key; });
        scroller.scrollTop = scrollPositions.get(key) || 0;
        try { sessionStorage.setItem(storageKey, key); } catch { /* Storage may be disabled. */ }
        if (updateURL) {
            const url = new URL(window.location.href);
            url.pathname = '/channel/settings'; url.searchParams.set('section', key);
            history.replaceState(null, '', url);
        }
    }
    tabs.forEach((tab, index) => {
        tab.addEventListener('click', event => {
            if (event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            event.preventDefault(); select(tab.dataset.settingsTab);
            if (book.getBoundingClientRect().top < 0) book.scrollIntoView({block: 'start'});
        });
        tab.addEventListener('keydown', event => {
            const previous = 'ArrowLeft';
            const next = 'ArrowRight';
            if (![previous, next, 'Home', 'End'].includes(event.key)) return;
            event.preventDefault();
            const target = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs.at(-1) : tabs[(index + (event.key === next ? 1 : tabs.length - 1)) % tabs.length];
            select(target.dataset.settingsTab); target.focus();
            target.scrollIntoView({block: 'nearest', inline: 'nearest'});
        });
    });
    const url = new URL(window.location.href);
    let selected = book.dataset.selected;
    const explicit = url.searchParams.has('section') || url.searchParams.has('social_tab') || url.searchParams.has('command_tab') || url.hash || url.searchParams.has('youtube_result') || url.searchParams.has('identity_result') || url.searchParams.has('protected_result');
    if (!explicit) { try { selected = sessionStorage.getItem(storageKey) || selected; } catch { /* Use server default. */ } }
    select(selected);
    try {
        const saved = JSON.parse(sessionStorage.getItem(`${storageKey}:scroll`) || 'null');
        sessionStorage.removeItem(`${storageKey}:scroll`);
        if (saved && saved.section === selected && Number.isFinite(saved.y)) requestAnimationFrame(() => { window.scrollTo(0, saved.y); scroller.scrollTop = saved.panelY || 0; });
    } catch { /* Scroll restoration is optional. */ }
    // Sections stay mounted, so moving between tabs never discards form drafts.
    const dirtyForms = new Set();
    const forms = [...book.querySelectorAll('form[method="post"]')];
    const snapshot = form => JSON.stringify([...new FormData(form)]);
    const originals = new Map(forms.map(form => [form, snapshot(form)]));
    function mark(form, force = false) {
        if (force || snapshot(form) !== originals.get(form)) dirtyForms.add(form); else dirtyForms.delete(form);
        pages.forEach(page => {
            const dirty = [...dirtyForms].some(item => page.contains(item));
            const tab = tabs.find(item => item.dataset.settingsTab === page.dataset.settingsPage);
            tab.querySelector('.settings-dirty-dot').hidden = !dirty;
        });
    }
    forms.forEach(form => {
        form.addEventListener('input', () => mark(form));
        form.addEventListener('change', () => mark(form));
        form.addEventListener('click', event => {
            if (event.target.closest('[data-add-timer], [data-remove-timer]')) mark(form, true);
        });
        // Warn when a normal server submission would discard another form's draft.
        form.addEventListener('submit', event => {
            if (event.defaultPrevented) return;
            if ([...dirtyForms].some(item => item !== form) && !window.confirm('Saving this form will reload settings and discard your other unsaved changes. Continue?')) {
                event.preventDefault(); return;
            }
            if (!event.defaultPrevented) {
                try { sessionStorage.setItem(`${storageKey}:scroll`, JSON.stringify({section: tabs.find(tab => tab.getAttribute('aria-selected') === 'true').dataset.settingsTab, y: window.scrollY, panelY: scroller.scrollTop})); } catch { /* Storage may be disabled. */ }
                dirtyForms.clear();
            }
        });
    });
    window.addEventListener('beforeunload', event => {
        if (dirtyForms.size) { event.preventDefault(); event.returnValue = ''; }
    });
})();
