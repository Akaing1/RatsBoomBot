(() => {
    'use strict';
    const book = document.querySelector('[data-settings-book]');
    const finder = book?.querySelector('[data-settings-finder]');
    if (!finder) return;
    const search = finder.querySelector('input');
    const results = finder.querySelector('[data-settings-results]');
    const count = finder.querySelector('[data-settings-result-count]');
    const pages = [...book.querySelectorAll('[data-settings-page]')];
    const entries = [];
    let highlighted = null;
    const highlightTimers = new Map();
    function fadeHighlight(target) {
        clearTimeout(highlightTimers.get(target));
        target.classList.add('settings-highlight-fading');
        highlightTimers.set(target, setTimeout(() => {
            target.classList.remove('settings-search-highlight', 'settings-highlight-fading');
            highlightTimers.delete(target);
            if (highlighted === target) highlighted = null;
        }, 250));
    }
    function highlight(target) {
        if (highlighted && highlighted !== target) fadeHighlight(highlighted);
        highlighted = target;
        clearTimeout(highlightTimers.get(target));
        if (!target.classList.contains('settings-search-highlight')) {
            target.classList.add('settings-search-highlight', 'settings-highlight-fading');
            // Establish the normal background before transitioning to the tint.
            void target.offsetWidth;
        }
        target.classList.remove('settings-highlight-fading');
        highlightTimers.set(target, setTimeout(() => fadeHighlight(target), 1000));
    }
    const normalize = value => value.toLocaleLowerCase().replace(/[_.]+/g, ' ').replace(/\s+/g, ' ').trim();
    const slug = value => value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    pages.forEach(page => {
        const section = page.dataset.settingsPage;
        const tabLabel = page.querySelector('.settings-page-heading h3').textContent.trim();
        const hashes = new Set();
        const targets = page.querySelectorAll('.profile-setting-card, .settings-switch-row, .settings-group-heading, .settings-command-cluster > h4, .panel > .panel-header, .panel > h3');
        targets.forEach(target => {
            // Collapsible group headings already provide the panel shortcut.
            if (target.matches('.panel-header') && target.closest('.settings-group')) return;
            const heading = target.querySelector('h4, h3, .settings-group-title') || target.querySelector('span');
            const title = (heading || target).textContent.trim().replace(/\s+/g, ' ');
            if (!title) return;
            const key = target.dataset.settingKey || target.querySelector('[name="setting_name"]')?.value || '';
            const control = target.querySelector('[id^="settings-control-"]')?.id.replace('settings-control-', '');
            if (!target.id) {
                const group = target.matches('.settings-group-heading') ? target.closest('.settings-group') : null;
                const base = group?.id ? `${group.id}-heading` : `settings-${section}-${slug(key || control || title)}`;
                let id = base;
                let suffix = 2;
                while (document.getElementById(id)) id = `${base}-${suffix++}`;
                target.id = id;
            }
            let hash = slug(title);
            if (hashes.has(hash)) hash = slug(key || control || `${title}-setting`);
            const baseHash = hash;
            let suffix = 2;
            while (hashes.has(hash)) hash = `${baseHash}-${suffix++}`;
            hashes.add(hash);
            target.dataset.settingsHash = hash;
            const description = target.querySelector('.toggle-card-heading p, .settings-toggle-description')?.textContent || '';
            const switches = [...target.querySelectorAll('[role="switch"]')].map(button => button.getAttribute('aria-label') || '').join(' ');
            const members = target.querySelector('.settings-command-members')?.textContent || '';
            entries.push({target, section, tabLabel, title, search: normalize([title, description, switches, members, key, tabLabel].join(' ')),
                shortcut: target.matches('.settings-group-heading, h4, h3, .panel-header')});
        });
    });
    function navigate(entry, historyMode = 'push') {
        book.dispatchEvent(new CustomEvent('settings-navigate', {detail: {section: entry.section, target: entry.target, historyMode}}));
        let parent = entry.target.closest('details');
        while (parent) { book.dispatchEvent(new CustomEvent('settings-expand', {detail: parent})); parent = parent.parentElement.closest('details'); }
        highlight(entry.target.closest('.profile-setting-card, .settings-switch-row, .settings-group, .settings-command-cluster, .panel') || entry.target);
        entry.target.querySelectorAll('.settings-field-editor').forEach(editor => { book.dispatchEvent(new CustomEvent('settings-expand', {detail: editor})); });
        const focus = entry.target.matches('summary') ? entry.target
            : entry.target.querySelector('textarea, input:not([type="hidden"]), select, button:not([disabled]), a') || entry.target;
        if (!focus.matches('input, textarea, select, button, a, summary')) focus.tabIndex = -1;
        focus.focus({preventScroll: true});
        book.dispatchEvent(new CustomEvent('settings-scroll', {detail: entry.target}));
    }
    function link(entry, showTab) {
        const button = document.createElement('button'); button.type = 'button';
        if (!showTab) {
            button.dataset.settingsLocation = entry.target.id;
        }
        const title = document.createElement('span'); title.textContent = entry.title; button.append(title);
        if (showTab) { const label = document.createElement('small'); label.textContent = entry.tabLabel; button.append(label); }
        button.addEventListener('click', () => navigate(entry)); return button;
    }
    book.querySelectorAll('[data-settings-links]').forEach(menu => {
        menu.replaceChildren(...entries.filter(entry => entry.section === menu.dataset.settingsLinks && entry.shortcut).map(entry => link(entry, false)));
    });
    function navigateToHash(hash, historyMode = 'push', section = new URL(location.href).searchParams.get('section')) {
        if (!hash) {
            const page = pages.find(node => node.dataset.settingsPage === section);
            if (!page) return false;
            navigate({target: page, section}, historyMode);
            return true;
        }
        let id;
        try { id = decodeURIComponent(hash.slice(1)); } catch { return false; }
        const target = entries.find(entry => entry.section === section && entry.target.dataset.settingsHash === id)?.target;
        const page = target?.closest('[data-settings-page]');
        if (!page || !book.contains(page)) return false;
        navigate({target: target.closest('.settings-switch-row, .profile-setting-card') || target, section: page.dataset.settingsPage}, historyMode);
        return true;
    }
    book.addEventListener('click', event => {
        const anchor = event.target.closest('a[data-settings-link]');
        if (!anchor || event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        const url = new URL(anchor.href);
        if (url.origin !== location.origin || !navigateToHash(url.hash, 'push', url.searchParams.get('section'))) return;
        event.preventDefault();
    });
    function updateResults() {
        const words = normalize(search.value).split(' ').filter(Boolean);
        const matches = words.length ? entries.filter(entry => words.every(word => entry.search.includes(word))) : [];
        results.replaceChildren(...matches.slice(0, 30).map(entry => link(entry, true)));
        count.textContent = !words.length ? '' : !matches.length ? 'No settings found. Try another word.'
            : `${matches.length} result${matches.length === 1 ? '' : 's'}${matches.length > 30 ? ' · showing the first 30' : ''}`;
        results.hidden = !words.length;
    }
    search.addEventListener('input', updateResults);
    finder.hidden = false; updateResults();
    if (location.hash && !navigateToHash(location.hash, 'replace')) {
        book.dispatchEvent(new CustomEvent('settings-location-changed', {detail: null}));
    }
})();
