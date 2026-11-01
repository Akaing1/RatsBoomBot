(() => {
    'use strict';
    const book = document.querySelector('[data-settings-book]');
    const finder = book?.querySelector('[data-settings-finder]');
    if (!finder) return;
    const search = finder.querySelector('input');
    const results = finder.querySelector('[data-settings-results]');
    const count = finder.querySelector('[data-settings-result-count]');
    const popup = document.createElement('div');
    popup.className = 'settings-search-popup';
    popup.setAttribute('popover', 'auto');
    popup.setAttribute('aria-label', 'Settings search results');
    popup.setAttribute('data-overlay-scrollbars', 'off');
    popup.append(count, results);
    finder.append(popup);
    results.id ||= 'settings-search-results';
    results.setAttribute('role', 'listbox');
    results.setAttribute('aria-label', 'Matching settings');
    search.setAttribute('role', 'combobox');
    search.setAttribute('aria-autocomplete', 'list');
    search.setAttribute('aria-controls', results.id);
    search.setAttribute('aria-expanded', 'false');
    let resultButtons = [];
    let activeIndex = -1;
    function selectResult(index) {
        if (activeIndex >= 0) {
            resultButtons[activeIndex]?.classList.remove('is-selected');
            resultButtons[activeIndex]?.setAttribute('aria-selected', 'false');
        }
        activeIndex = index;
        const button = resultButtons[index];
        if (button) {
            button.classList.add('is-selected');
            button.setAttribute('aria-selected', 'true');
            search.setAttribute('aria-activedescendant', button.id);
        } else search.removeAttribute('aria-activedescendant');
    }
    function positionPopup() {
        const rect = search.getBoundingClientRect();
        const width = Math.min(Math.max(rect.width, 300), innerWidth - 24);
        const below = innerHeight - rect.bottom - 20;
        const above = rect.top - 20;
        const upwards = below < 160 && above > below;
        Object.assign(popup.style, {
            width: `${width}px`, left: `${Math.max(12, Math.min(rect.left, innerWidth - width - 12))}px`,
            top: upwards ? 'auto' : `${rect.bottom + 8}px`,
            bottom: upwards ? `${innerHeight - rect.top + 8}px` : 'auto',
            maxHeight: `${Math.max(0, Math.min(440, upwards ? above : below))}px`,
        });
    }
    function openResults() {
        if (!normalize(search.value)) return;
        positionPopup();
        if (!popup.matches(':popover-open')) popup.showPopover();
        search.setAttribute('aria-expanded', 'true');
    }
    function closeResults() {
        if (popup.matches(':popover-open')) popup.hidePopover();
        search.setAttribute('aria-expanded', 'false');
        selectResult(-1);
    }
    popup.addEventListener('toggle', event => {
        search.setAttribute('aria-expanded', String(event.newState === 'open'));
        if (event.newState === 'closed') selectResult(-1);
    });
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
            const group = target.closest('.settings-group, .settings-command-cluster, .profile-settings-panel');
            const category = group?.querySelector(':scope>.settings-group-heading h4, :scope>h4, :scope>.panel-header h3, :scope>h3')?.textContent || '';
            const name = normalize(title);
            entries.push({target, section, tabLabel, title, name, nameWords: [...new Set(name.split(/[^\p{L}\p{N}]+/u).filter(Boolean))],
                category: normalize(`${tabLabel} ${category}`),
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
        button.addEventListener('click', () => { closeResults(); navigate(entry); }); return button;
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
    function similarity(a, b) {
        if (a === b) return 1;
        if (!a || !b || Math.min(a.length, b.length) / Math.max(a.length, b.length) < 0.72) return 0;
        const row = Array.from({length: b.length + 1}, (_, index) => index);
        for (let i = 1; i <= a.length; i++) {
            let previous = row[0]; row[0] = i;
            for (let j = 1; j <= b.length; j++) {
                const old = row[j];
                row[j] = Math.min(row[j] + 1, row[j - 1] + 1, previous + (a[i - 1] === b[j - 1] ? 0 : 1));
                previous = old;
            }
        }
        return 1 - row[b.length] / Math.max(a.length, b.length);
    }
    function matchRank(entry, query, words) {
        if (entry.name === query) return [0, 1];
        if (entry.name.startsWith(query)) return [1, query.length / entry.name.length];
        if (words.every(word => entry.name.includes(word))) return [2, query.length / entry.name.length];
        if (query.length >= 3) {
            const fullScore = similarity(query, entry.name);
            const scores = words.map(word => Math.max(0, ...entry.nameWords.map(name => word.length < 3 ? Number(name === word) : similarity(word, name))));
            const score = Math.max(fullScore, scores.every(value => value >= 0.72) ? scores.reduce((sum, value) => sum + value, 0) / scores.length : 0);
            if (score >= 0.75) return [3, score];
        }
        if (words.every(word => entry.name.includes(word) || entry.category.includes(word))) return [4, 0];
        return null;
    }
    function updateResults() {
        const query = normalize(search.value);
        const words = query.split(' ').filter(Boolean);
        const ranked = [];
        if (words.length) for (const entry of entries) {
            const rank = matchRank(entry, query, words);
            if (rank) ranked.push({entry, rank});
        }
        ranked.sort((a, b) => a.rank[0] - b.rank[0] || b.rank[1] - a.rank[1]);
        selectResult(-1);
        resultButtons = ranked.slice(0, 30).map(({entry}, index) => {
            const button = link(entry, true);
            button.id = `settings-search-result-${index}`;
            button.setAttribute('role', 'option');
            button.setAttribute('aria-selected', 'false');
            return button;
        });
        results.replaceChildren(...resultButtons);
        count.textContent = !words.length ? '' : !ranked.length ? 'No settings found. Try another word.'
            : `${ranked.length} result${ranked.length === 1 ? '' : 's'}${ranked.length > 30 ? ' · showing the first 30' : ''}`;
        results.hidden = !words.length;
        if (words.length) openResults();
        else closeResults();
    }
    search.addEventListener('input', updateResults);
    search.addEventListener('focus', openResults);
    search.addEventListener('keydown', event => {
        if (event.isComposing) return;
        if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && resultButtons.length) {
            event.preventDefault();
            openResults();
            selectResult(activeIndex < 0 ? event.key === 'ArrowDown' ? 0 : resultButtons.length - 1
                : (activeIndex + (event.key === 'ArrowDown' ? 1 : -1) + resultButtons.length) % resultButtons.length);
            resultButtons[activeIndex].scrollIntoView({block: 'nearest'});
        } else if (event.key === 'Enter' && activeIndex >= 0 && popup.matches(':popover-open')) {
            event.preventDefault();
            if (!event.repeat) resultButtons[activeIndex].click();
        } else if (event.key === 'Escape' && popup.matches(':popover-open')) {
            event.preventDefault(); event.stopPropagation(); closeResults();
        }
    });
    function reposition(event) {
        if (!popup.matches(':popover-open') || (event.type === 'scroll' && popup.contains(event.target))) return;
        positionPopup();
    }
    window.addEventListener('resize', reposition, {passive: true});
    document.addEventListener('scroll', reposition, {capture: true, passive: true});
    finder.hidden = false; updateResults();
    if (location.hash && !navigateToHash(location.hash, 'replace')) {
        book.dispatchEvent(new CustomEvent('settings-location-changed', {detail: null}));
    }
})();
