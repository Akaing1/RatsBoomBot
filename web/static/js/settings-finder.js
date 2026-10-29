(() => {
    'use strict';
    const book = document.querySelector('[data-settings-book]');
    const finder = book?.querySelector('[data-settings-finder]');
    if (!finder) return;
    const search = finder.querySelector('input');
    const toggle = book.querySelector('[data-settings-finder-toggle]');
    function setOpen(open, restoreFocus = false) {
        finder.hidden = !open;
        toggle?.setAttribute('aria-expanded', String(open));
        if (open) search.focus({preventScroll: true});
        else if (restoreFocus) toggle?.focus({preventScroll: true});
    }
    if (toggle) {
        toggle.hidden = false;
        toggle.addEventListener('click', () => setOpen(finder.hidden));
        finder.querySelector('[data-settings-finder-close]').addEventListener('click', () => setOpen(false, true));
        book.addEventListener('keydown', event => {
            if (event.key === 'Escape' && !finder.hidden) { event.preventDefault(); setOpen(false, true); }
        });
    }
    const results = finder.querySelector('[data-settings-results]');
    const count = finder.querySelector('[data-settings-result-count]');
    const shortcuts = finder.querySelector('[data-settings-shortcuts]');
    const pages = [...book.querySelectorAll('[data-settings-page]')];
    const tabs = [...book.querySelectorAll('[data-settings-tab]')];
    const entries = [];
    let highlighted = null;
    const normalize = value => value.toLocaleLowerCase().replace(/[_.]+/g, ' ').replace(/\s+/g, ' ').trim();
    pages.forEach(page => {
        const section = page.dataset.settingsPage;
        const tabLabel = page.querySelector('.settings-page-heading h3').textContent.trim();
        const targets = page.querySelectorAll('.profile-setting-card, .settings-switch-row, .settings-group > summary, .settings-command-cluster > h4, .panel > .panel-header, .panel > h3');
        targets.forEach(target => {
            // Collapsible group headings already provide the panel shortcut.
            if (target.matches('.panel-header') && target.closest('.settings-group')) return;
            const heading = target.querySelector('h4, h3, .settings-group-title') || target.querySelector('span');
            const title = (heading || target).textContent.trim().replace(/\s+/g, ' ');
            if (!title) return;
            const description = target.querySelector('.toggle-card-heading p')?.textContent || '';
            const switches = [...target.querySelectorAll('[role="switch"]')].map(button => button.getAttribute('aria-label') || '').join(' ');
            const key = target.dataset.settingKey || target.querySelector('[name="setting_name"]')?.value || '';
            entries.push({target, section, tabLabel, title, search: normalize([title, description, switches, key, tabLabel].join(' ')),
                shortcut: target.matches('summary, h4, h3, .panel-header')});
        });
    });
    function navigate(entry) {
        const tab = tabs.find(tab => tab.dataset.settingsTab === entry.section);
        tab.click(); // Reuse tab navigation and leave all unsaved form drafts mounted.
        let parent = entry.target.closest('details');
        while (parent) { parent.open = true; parent = parent.parentElement.closest('details'); }
        highlighted?.classList.remove('settings-search-highlight');
        highlighted = entry.target;
        highlighted.classList.add('settings-search-highlight');
        if (toggle && matchMedia('(max-width: 900px)').matches) setOpen(false);
        const focus = entry.target.matches('summary') ? entry.target
            : entry.target.querySelector('textarea, input:not([type="hidden"]), select, button, a') || entry.target;
        if (!focus.matches('input, textarea, select, button, a, summary')) focus.tabIndex = -1;
        focus.focus({preventScroll: true});
        entry.target.scrollIntoView({block: 'center', behavior: 'auto'});
    }
    function link(entry, showTab) {
        const button = document.createElement('button'); button.type = 'button';
        const title = document.createElement('span'); title.textContent = entry.title; button.append(title);
        if (showTab) { const label = document.createElement('small'); label.textContent = entry.tabLabel; button.append(label); }
        button.addEventListener('click', () => navigate(entry)); return button;
    }
    function updateShortcuts() {
        const section = tabs.find(tab => tab.getAttribute('aria-selected') === 'true')?.dataset.settingsTab;
        shortcuts.replaceChildren(...entries.filter(entry => entry.section === section && entry.shortcut).map(entry => link(entry, false)));
    }
    function updateResults() {
        const words = normalize(search.value).split(' ').filter(Boolean);
        const matches = words.length ? entries.filter(entry => words.every(word => entry.search.includes(word))) : [];
        results.replaceChildren(...matches.slice(0, 30).map(entry => link(entry, true)));
        count.textContent = !words.length ? '' : !matches.length ? 'No settings found. Try another word.'
            : `${matches.length} result${matches.length === 1 ? '' : 's'}${matches.length > 30 ? ' · showing the first 30' : ''}`;
        results.hidden = !words.length;
    }
    search.addEventListener('input', updateResults);
    book.addEventListener('settings-section-changed', updateShortcuts);
    finder.hidden = Boolean(toggle); updateShortcuts(); updateResults();
})();
