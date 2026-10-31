(() => {
    'use strict';
    const book = document.querySelector('[data-settings-book]');
    const menu = book?.querySelector('.settings-menu');
    if (!menu) return;
    const indicator = document.createElement('span');
    indicator.className = 'settings-menu-indicator';
    indicator.setAttribute('aria-hidden', 'true');
    indicator.hidden = true;
    menu.prepend(indicator);
    menu.classList.add('has-sliding-highlight');
    const locations = [...menu.querySelectorAll('[data-settings-location]')].map(button => ({button, target: document.getElementById(button.dataset.settingsLocation)}));
    let frame;
    let initialized = false;
    let scrollIntent = null;
    let hoverIntent = null;
    let pointerActive = false;
    let currentLocation;
    let releaseTimer;
    function update() {
        frame = null;
        const link = menu.querySelector('[data-settings-tab][aria-current="page"]');
        const page = book.querySelector('[data-settings-page]:not([hidden])');
        if (!link || !page) { indicator.hidden = true; return; }
        const bar = matchMedia('(max-width: 768px)').matches ? document.querySelector('[data-channel-sidebar]')?.getBoundingClientRect().bottom || 0 : 0;
        let active;
        locations.forEach(item => {
            const section = item.target.closest('.settings-group, .settings-command-cluster, .profile-settings-panel, .settings-timer-manager>.panel') || item.target;
            if (page.contains(item.target) && section.getBoundingClientRect().top <= bar + 1) active = item;
        });
        if (scrollIntent) active = scrollIntent.location;
        if (hoverIntent && (!scrollIntent || pointerActive)) active = hoverIntent.location;
        if (active?.target !== currentLocation) {
            currentLocation = active?.target;
            book.dispatchEvent(new CustomEvent('settings-location-changed', {detail: currentLocation}));
        }
        locations.forEach(item => {
            if (item === active) item.button.setAttribute('aria-current', 'location');
            else item.button.removeAttribute('aria-current');
        });
        const row = active?.button.closest('.settings-menu-section')?.open ? active.button : link.closest('summary');
        const bounds = row.getBoundingClientRect();
        const parent = menu.getBoundingClientRect();
        if (!bounds.width || !bounds.height || !menu.offsetWidth) { indicator.hidden = true; return; }
        indicator.hidden = false;
        indicator.style.width = `${bounds.width}px`;
        indicator.style.height = `${bounds.height}px`;
        indicator.style.transform = `translate(${bounds.left - parent.left}px, ${bounds.top - parent.top}px)`;
        if (!initialized) {
            // Position the first highlight without sliding in from the corner.
            void indicator.offsetWidth;
            menu.classList.add('highlight-ready');
            initialized = true;
        }
    }
    function schedule() { if (!frame) frame = requestAnimationFrame(update); }
    function locationFor(target) {
        const group = target.closest('.settings-group') || target.closest('.settings-command-cluster, .profile-settings-panel, .settings-timer-manager>.panel');
        return locations.find(item => item.target === target) || locations.find(item => group?.contains(item.target));
    }
    function releaseIntent() {
        clearTimeout(releaseTimer);
        scrollIntent = null;
        schedule();
    }
    function finishScroll() {
        if (scrollIntent && !pointerActive) hoverIntent = scrollIntent;
        releaseIntent();
    }
    const observer = new ResizeObserver(schedule);
    observer.observe(menu);
    book.addEventListener('settings-section-changed', () => { hoverIntent = null; pointerActive = false; releaseIntent(); });
    book.addEventListener('settings-hover', event => {
        pointerActive = true;
        hoverIntent = {location: locationFor(event.detail)};
        cancelAnimationFrame(frame);
        update();
    });
    book.addEventListener('settings-hover-end', () => { pointerActive = false; });
    book.addEventListener('settings-reference-focused', event => {
        pointerActive = false;
        hoverIntent = {location: locationFor(event.detail)};
        releaseIntent();
        cancelAnimationFrame(frame);
        update();
    });
    book.addEventListener('settings-context-scroll', event => {
        pointerActive = Boolean(event.detail.hovered);
        const target = event.detail.hovered || event.detail.target;
        if (target) hoverIntent = {location: locationFor(target)};
        schedule();
    });
    book.addEventListener('settings-scroll-start', event => {
        const target = event.detail;
        const location = locationFor(target);
        hoverIntent = null;
        scrollIntent = {location};
        clearTimeout(releaseTimer);
        releaseTimer = setTimeout(finishScroll, 1200);
        cancelAnimationFrame(frame);
        update();
    });
    book.addEventListener('toggle', schedule, true);
    window.addEventListener('scroll', () => {
        if (scrollIntent) {
            clearTimeout(releaseTimer);
            releaseTimer = setTimeout(finishScroll, 150);
        }
        schedule();
    }, {passive: true});
    window.addEventListener('wheel', releaseIntent, {passive: true});
    window.addEventListener('touchstart', releaseIntent, {passive: true});
    window.addEventListener('resize', schedule, {passive: true});
    window.addEventListener('pagehide', () => { observer.disconnect(); cancelAnimationFrame(frame); clearTimeout(releaseTimer); }, {once: true});
    schedule();
})();
