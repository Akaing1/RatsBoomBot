(() => {
    'use strict';
    const book = document.querySelector('[data-settings-book]');
    if (!book) return;
    const tabs = [...book.querySelectorAll('[data-settings-tab]')];
    const pages = [...book.querySelectorAll('[data-settings-page]')];
    const scroller = book.querySelector('.settings-pages');
    const main = book.querySelector('.settings-main');
    let hoveredSetting;
    let pointer;
    function settingAt(element) {
        if (!element || !main?.contains(element)) return null;
        let target = element.closest('.settings-switch-row, .profile-setting-card, .settings-timer-manager>.panel');
        if (!target) {
            const copy = element.closest('.settings-page-heading, .settings-group-heading, .settings-command-cluster>h4, .panel-header, .panel>h3, .settings-toggle-description, .settings-related-links');
            target = copy?.closest('.settings-group, .settings-command-cluster, .profile-settings-panel');
            if (copy?.matches('.settings-page-heading')) target = copy.closest('[data-settings-page]');
            if (!target) {
                const panel = element.closest('.settings-page>.panel');
                if (panel && !panel.querySelector('.profile-settings-grid, .settings-switch-list')) target = panel;
            }
        }
        return target?.closest('.settings-command-cluster') || target || null;
    }
    function setHover(target) {
        if (target === hoveredSetting) return;
        hoveredSetting = target;
        book.dispatchEvent(new CustomEvent(target ? 'settings-hover' : 'settings-hover-end', {detail: target}));
    }
    main?.addEventListener('pointerover', event => {
        if (event.pointerType === 'touch' || !matchMedia('(hover: hover)').matches) return;
        pointer = {x: event.clientX, y: event.clientY};
        setHover(settingAt(event.target));
    });
    main?.addEventListener('pointerleave', () => setHover(null));
    document.addEventListener('pointermove', event => {
        if (event.pointerType !== 'touch') pointer = {x: event.clientX, y: event.clientY};
    }, {passive: true});
    window.addEventListener('scroll', () => {
        if (!main) return;
        const bounds = main.getBoundingClientRect();
        const edge = matchMedia('(max-width:768px)').matches ? document.querySelector('[data-channel-sidebar]')?.getBoundingClientRect().bottom || 0 : 0;
        const element = document.elementFromPoint(bounds.left + bounds.width / 2, edge + 1);
        const target = settingAt(element) || (main.contains(element) ? element.closest('.settings-group, .settings-command-cluster, .profile-settings-panel, .settings-timer-manager>.panel, [data-settings-page]') : null);
        if (pointer && matchMedia('(hover:hover)').matches) setHover(settingAt(document.elementFromPoint(pointer.x, pointer.y)));
        book.dispatchEvent(new CustomEvent('settings-context-scroll', {detail: {hovered: hoveredSetting, target}}));
    }, {passive: true});
    book.addEventListener('settings-section-changed', () => { hoveredSetting = null; });
    let activeSection = book.dataset.selected;
    const disclosures = new WeakMap();
    const menuToggle = document.querySelector('[data-settings-menu-toggle]');
    const menu = book.querySelector('.settings-tools');
    const mobile = matchMedia('(max-width: 768px)');
    let menuAnimation;
    function showMenu(open, animate = true) {
        if (!menuToggle || !menu) return;
        menuAnimation?.cancel();
        menuToggle.setAttribute('aria-expanded', String(open));
        menu.inert = mobile.matches && !open;
        if (!animate || matchMedia('(prefers-reduced-motion: reduce)').matches) {
            menu.classList.toggle('is-open', open); return;
        }
        menu.classList.add('is-open');
        const frames = [{opacity: 0, clipPath: 'inset(0 0 100% 0)'}, {opacity: 1, clipPath: 'inset(0 0 0 0)'}];
        menuAnimation = menu.animate(open ? frames : [...frames].reverse(), {duration: 180, easing: 'ease-out'});
        menuAnimation.onfinish = () => { menu.classList.toggle('is-open', open); menuAnimation = null; };
    }
    menuToggle?.addEventListener('click', () => {
        if (mobile.matches && !document.querySelector('[data-dashboard-shell]')?.classList.contains('sidebar-collapsed')) document.querySelector('[data-sidebar-mobile-back]')?.click();
        showMenu(menuToggle.getAttribute('aria-expanded') !== 'true');
    });
    mobile.addEventListener('change', () => {
        showMenu(false, false);
        const group = tabs.find(tab => tab.dataset.settingsTab === activeSection)?.closest('.settings-menu-section');
        if (mobile.matches && group) expand(group, true);
    });
    showMenu(false, false);
    document.addEventListener('click', event => {
        if (mobile.matches && menuToggle?.getAttribute('aria-expanded') === 'true' && !menu.contains(event.target) && !menuToggle.contains(event.target)) showMenu(false);
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && menuToggle?.getAttribute('aria-expanded') === 'true') {
            showMenu(false); menuToggle.focus();
        }
    });
    function scrollToSetting(target) {
        if (!target?.isConnected || target.closest('[hidden]')) return;
        book.dispatchEvent(new CustomEvent('settings-scroll-start', {detail: target}));
        const behavior = matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth';
        if (mobile.matches) {
            const bar = document.querySelector('[data-channel-sidebar]');
            const offset = bar ? Math.max(0, bar.getBoundingClientRect().bottom) : 0;
            window.scrollTo({top: Math.max(0, window.scrollY + target.getBoundingClientRect().top - offset - 16), behavior});
        } else {
            target.scrollIntoView({block: 'start', behavior});
        }
    }
    function expand(details, open) {
        if (open && mobile.matches && details.matches('.settings-menu-section')) {
            book.querySelectorAll('.settings-menu-section').forEach(other => { if (other !== details) expand(other, false); });
        }
        const previous = disclosures.get(details);
        if (previous?.open === open || (!previous && details.open === open)) return;
        const start = details.getBoundingClientRect().height;
        const overflow = previous?.overflow ?? details.style.overflow;
        const boxSizing = previous?.boxSizing ?? details.style.boxSizing;
        if (previous) { previous.animation.onfinish = null; previous.animation.cancel(); }
        if (matchMedia('(prefers-reduced-motion: reduce)').matches || !details.animate) {
            details.open = open; details.style.overflow = overflow; details.style.boxSizing = boxSizing;
            disclosures.delete(details); return;
        }
        details.open = open;
        const end = details.getBoundingClientRect().height;
        details.open = true;
        details.style.overflow = 'hidden'; details.style.boxSizing = 'border-box';
        const animation = details.animate([{height: `${start}px`}, {height: `${end}px`}], {duration: 220, easing: 'ease-in-out'});
        disclosures.set(details, {animation, open, overflow, boxSizing});
        animation.onfinish = () => {
            details.open = open; details.style.overflow = overflow; details.style.boxSizing = boxSizing;
            disclosures.delete(details);
        };
    }
    book.addEventListener('click', event => {
        const summary = event.target.closest('summary');
        if (event.defaultPrevented || !summary || event.target.closest('a, button, input, select, textarea, label')) return;
        const details = summary.parentElement;
        if (!details.matches('details')) return;
        event.preventDefault();
        expand(details, !(disclosures.get(details)?.open ?? details.open));
    });
    book.addEventListener('settings-expand', event => expand(event.detail, true));
    book.addEventListener('dblclick', event => {
        const group = event.target.closest('summary')?.parentElement;
        if (mobile.matches || !group?.matches('.settings-menu-section') || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        book.querySelectorAll('.settings-menu-section').forEach(section => expand(section, section === group));
    });
    function writeLocation(key, target, mode = 'push') {
        const url = new URL(location.href);
        url.pathname = (document.body.dataset.channelRoot || '/channel') + '/settings';
        url.searchParams.set('section', key);
        const anchor = target?.matches('[data-settings-hash]') ? target : target?.querySelector(':scope>.settings-group-heading[data-settings-hash],:scope>h3[data-settings-hash],:scope>h4[data-settings-hash],:scope>.panel-header[data-settings-hash]');
        url.hash = target?.matches('[data-settings-page]') ? '' : anchor?.dataset.settingsHash || '';
        if (url.href !== location.href) {
            history[mode === 'replace' ? 'replaceState' : 'pushState'](history.state, '', url);
        }
    }
    book.addEventListener('settings-navigate', event => {
        const detail = event.detail;
        if (typeof detail === 'string') select(detail);
        else {
            select(detail.section, false);
            writeLocation(detail.section, detail.target, detail.historyMode);
        }
    });
    book.addEventListener('settings-location-changed', event => writeLocation(activeSection, event.detail, 'replace'));
    book.addEventListener('settings-scroll', event => {
        if (mobile.matches && menuToggle?.getAttribute('aria-expanded') === 'true') showMenu(false);
        scrollToSetting(event.detail);
    });
    function select(key, updateURL = true) {
        if (!tabs.some(tab => tab.dataset.settingsTab === key)) return;
        activeSection = key;
        tabs.forEach(tab => {
            const active = tab.dataset.settingsTab === key;
            if (active) tab.setAttribute('aria-current', 'page'); else tab.removeAttribute('aria-current');
            if (active) {
                const group = tab.closest('.settings-menu-section');
                if (group) expand(group, true);
            }
        });
        pages.forEach(page => { page.hidden = page.dataset.settingsPage !== key; });
        scroller.scrollTop = 0;
        book.dispatchEvent(new CustomEvent('settings-section-changed', {detail: {key}}));
        if (updateURL) writeLocation(key);
    }
    tabs.forEach((tab, index) => {
        tab.addEventListener('click', event => {
            if (event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            if (mobile.matches && menuToggle?.getAttribute('aria-expanded') === 'true') showMenu(false);
            event.preventDefault(); select(tab.dataset.settingsTab);
            scrollToSetting(pages.find(page => page.dataset.settingsPage === tab.dataset.settingsTab));
        });
        tab.addEventListener('keydown', event => {
            const previous = 'ArrowUp';
            const next = 'ArrowDown';
            if (![previous, next, 'Home', 'End'].includes(event.key)) return;
            event.preventDefault();
            const target = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs.at(-1) : tabs[(index + (event.key === next ? 1 : tabs.length - 1)) % tabs.length];
            select(target.dataset.settingsTab); target.focus();
            target.scrollIntoView({block: 'nearest', inline: 'nearest'});
        });
    });
    const url = new URL(window.location.href);
    let selected = url.searchParams.get('section') || book.dataset.selected;
    if (!tabs.some(tab => tab.dataset.settingsTab === selected)) selected = book.dataset.selected;
    select(selected, false);
    url.searchParams.set('section', selected);
    history.replaceState(history.state, '', url);
    window.addEventListener('popstate', () => {
        const key = new URL(location.href).searchParams.get('section') || book.dataset.selected;
        if (!tabs.some(tab => tab.dataset.settingsTab === key)) return;
        select(key, false);
        let target;
        const page = pages.find(item => item.dataset.settingsPage === key);
        try {
            const hash = decodeURIComponent(location.hash.slice(1));
            target = [...page.querySelectorAll('[data-settings-hash]')].find(node => node.dataset.settingsHash === hash);
        } catch { /* Ignore malformed anchors. */ }
        scrollToSetting(page.contains(target) ? target : page);
        if (location.hash && !target) writeLocation(key, null, 'replace');
    });
    // Sections stay mounted, so navigating never discards form drafts.
    const dirtyForms = new Set();
    const forms = [...book.querySelectorAll('form[method="post"]')];
    const snapshot = form => JSON.stringify([...new FormData(form)]);
    const originals = new Map(forms.map(form => [form, snapshot(form)]));
    const saveActions = new Map();
    function resetForm(form) {
        const values = new Map(JSON.parse(originals.get(form)));
        [...form.elements].forEach(input => {
            if (!input.name || input instanceof HTMLButtonElement) return;
            if (input.type === 'checkbox' || input.type === 'radio') input.checked = values.get(input.name) === input.value;
            else input.value = values.get(input.name) ?? '';
            input.setCustomValidity?.('');
        });
        form.querySelectorAll('[data-settings-list]').forEach(editor => editor.dispatchEvent(new Event('settings-reset-list')));
        form.querySelectorAll('textarea[data-settings-grow]').forEach(input => input.dispatchEvent(new Event('input', {bubbles: true})));
        form.dispatchEvent(new Event('input', {bubbles: true}));
        form.querySelector('input:not([type="hidden"]),textarea:not([hidden]),select')?.focus({preventScroll: true});
    }
    forms.forEach(form => {
        const actions = [];
        [...form.elements].filter(node => node.matches('button[name="action"][value="save"], button[data-settings-save]') && node.getAttribute('role') !== 'switch').forEach(button => {
            button.dataset.settingsSave = '';
            button.hidden = false;
            let wrapper = button.closest('.profile-setting-actions');
            if (!wrapper) {
                wrapper = document.createElement('div');
                wrapper.className = 'profile-setting-actions';
                button.before(wrapper); wrapper.append(button);
            }
            if (actions.includes(wrapper)) return;
            const inner = document.createElement('div'); inner.className = 'settings-save-inner';
            inner.append(...wrapper.childNodes); wrapper.append(inner);
            if (form.querySelector('input[name="value"],textarea[name="value"],select[name="value"]')) {
                const cancel = document.createElement('button');
                cancel.type = 'button'; cancel.className = 'button secondary'; cancel.textContent = 'Cancel';
                cancel.dataset.settingsCancel = '';
                cancel.addEventListener('click', () => resetForm(form));
                inner.append(cancel);
            }
            wrapper.hidden = false;
            wrapper.classList.add('settings-save-reveal');
            wrapper.style.setProperty('--settings-actions-gap', `${parseFloat(getComputedStyle(wrapper.parentElement).rowGap) || 0}px`);
            actions.push(wrapper);
        });
        saveActions.set(form, actions);
    });
    function mark(form) {
        const dirty = snapshot(form) !== originals.get(form);
        if (dirty) dirtyForms.add(form); else dirtyForms.delete(form);
        saveActions.get(form).forEach(actions => {
            actions.classList.toggle('is-visible', dirty);
            actions.inert = !dirty;
            actions.setAttribute('aria-hidden', String(!dirty));
        });
        pages.forEach(page => {
            const dirty = [...dirtyForms].some(item => page.contains(item));
            const tab = tabs.find(item => item.dataset.settingsTab === page.dataset.settingsPage);
            tab.closest('.settings-menu-section').querySelector('.settings-dirty-dot').hidden = !dirty;
        });
    }
    forms.forEach(form => {
        mark(form);
        saveActions.get(form).forEach(actions => { void actions.offsetHeight; actions.classList.add('is-ready'); });
        form.addEventListener('input', () => mark(form));
        form.addEventListener('change', () => mark(form));
        form.addEventListener('click', event => {
            if (event.target.closest('[data-add-timer], [data-remove-timer]')) queueMicrotask(() => mark(form));
        });
        // Warn when a normal server submission would discard another form's draft.
        form.addEventListener('submit', event => {
            if (event.defaultPrevented) return;
            if (form.hasAttribute('data-settings-inline-save')) return;
            if ([...dirtyForms].some(item => item !== form) && !window.confirm('Saving this form will reload settings and discard your other unsaved changes. Continue?')) {
                event.preventDefault(); return;
            }
            if (!event.defaultPrevented) {
                dirtyForms.clear();
            }
        });
    });
    book.addEventListener('settings-saved', event => {
        originals.set(event.detail.form, event.detail.snapshot);
        mark(event.detail.form);
    });
    window.addEventListener('beforeunload', event => {
        if (dirtyForms.size) { event.preventDefault(); event.returnValue = ''; }
    });
})();
