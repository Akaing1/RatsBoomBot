(() => {
    'use strict';
    const book = document.querySelector('[data-settings-book]');
    if (!book) return;
    const main = book.querySelector('.settings-main');
    const rail = book.querySelector('.settings-commands-rail');
    if (!main || !rail) return;
    const scopes = new Map();
    book.querySelectorAll('[data-settings-command-reference]').forEach(region => {
        const owner = region.closest('.settings-switch-row, .profile-setting-card, .settings-group');
        if (!owner) return;
        const page = owner.closest('[data-settings-page]');
        const scope = ['loyalty', 'connections'].includes(page?.dataset.settingsPage) ? page : owner.closest('.settings-group') || owner.closest('.settings-command-cluster, .profile-settings-panel') || owner;
        if (!scopes.has(scope)) scopes.set(scope, []);
        scopes.get(scope).push({owner, region});
    });
    const references = [...scopes].map(([scope, items]) => {
        const preferred = scope.dataset.settingsPage === 'loyalty' ? items.find(item => item.owner.querySelector('#settings-control-feature-points')) || items[0] : items[0];
        const region = preferred.region;
        const panel = region.querySelector('.settings-command-reference');
        const list = panel.querySelector('ul');
        const commands = new Map();
        // One reference per subsection, without repeating shared commands.
        items.forEach(item => item.region.querySelectorAll('li').forEach(entry => {
            const syntax = entry.querySelector('code').textContent.trim();
            if (!commands.has(syntax)) commands.set(syntax, entry);
        }));
        list.replaceChildren(...commands.values());
        if (scope.matches('.settings-command-cluster') || scope.dataset.settingsPage === 'connections') {
            const title = scope.dataset.settingsPage === 'connections' ? 'Command groups' : scope.querySelector(':scope>h4').textContent;
            panel.querySelector('h4').textContent = title;
            panel.setAttribute('aria-label', title);
        }
        items.forEach(item => { if (item !== preferred) item.region.remove(); });
        rail.append(region);
        region.hidden = true;
        const anchor = [...scope.querySelectorAll(':scope>.settings-group-heading, :scope>.panel-header, :scope>h4, :scope>.settings-page-heading')].find(heading => getComputedStyle(heading).display !== 'none') || scope;
        return {scope, anchor, region};
    });
    if (!references.length) return;
    rail.removeAttribute('aria-hidden');
    const wide = matchMedia('(min-width: 1101px)');
    const mobile = matchMedia('(max-width: 768px)');
    let frame;
    let selected;
    let hovered;
    let layoutState;
    let layoutSnapshot;
    const layoutAnimations = new Map();
    const layoutPanels = [book.querySelector('.settings-tools'), main, rail].filter(Boolean);
    function stopLayoutAnimations() {
        layoutAnimations.forEach(animation => animation.cancel());
        layoutAnimations.clear();
    }
    function updateLayout(shown) {
        if (shown === layoutState && layoutAnimations.size) return;
        const previous = layoutAnimations.size ? new Map(layoutPanels.map(panel => [panel, panel.getBoundingClientRect()])) : layoutSnapshot;
        stopLayoutAnimations();
        const next = new Map(layoutPanels.map(panel => [panel, panel.getBoundingClientRect()]));
        if (previous && shown !== layoutState && matchMedia('(min-width:901px)').matches && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
            next.forEach((bounds, panel) => {
                if (!bounds.width) return;
                const old = previous.get(panel);
                const entering = !old?.width;
                const offset = entering ? 20 : old.left - bounds.left;
                if (!entering && Math.abs(offset) < 1) return;
                const animation = panel.animate([
                    {transform: `translateX(${offset}px)`, opacity: entering ? 0 : 1},
                    {transform: 'translateX(0)', opacity: 1},
                ], {duration: 240, easing: 'ease-in-out'});
                layoutAnimations.set(panel, animation);
                animation.onfinish = () => { layoutAnimations.delete(panel); if (!layoutAnimations.size) schedule(); };
            });
        }
        layoutState = shown;
        layoutSnapshot = next;
    }
    const animations = new Map();
    function stopAnimation(panel) {
        const animation = animations.get(panel);
        if (animation) { animation.onfinish = null; animation.cancel(); animations.delete(panel); }
        panel.style.removeProperty('max-height');
        panel.style.removeProperty('overflow-y');
    }
    function select(target) {
        const match = references.find(item => item.scope.contains(target));
        if (match) changeExpansion(match, hovered);
    }
    function changeExpansion(nextSelected, nextHovered) {
        if (selected === nextSelected && hovered === nextHovered) return;
        const heights = references.filter(item => !item.region.hidden).map(item => {
            const panel = item.region.querySelector('.settings-command-reference');
            return {panel, region: item.region, height: panel.getBoundingClientRect().height, regionHeight: item.region.getBoundingClientRect().height};
        });
        heights.forEach(({panel}) => stopAnimation(panel));
        selected = nextSelected;
        hovered = nextHovered;
        stack();
        cancelAnimationFrame(frame);
        update();
        if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        heights.forEach(({panel, region, height, regionHeight}) => {
            const next = panel.getBoundingClientRect().height;
            if (Math.abs(next - height) < 1) return;
            panel.style.maxHeight = `${innerHeight - 32}px`;
            panel.style.overflowY = 'hidden';
            region.style.height = `${Math.max(regionHeight, region.getBoundingClientRect().height)}px`;
            const animation = panel.animate([{height: `${height}px`}, {height: `${next}px`}], {duration: 220, easing: 'ease-in-out'});
            animations.set(panel, animation);
            animation.onfinish = () => { stopAnimation(panel); schedule(); };
        });
    }
    function stack() {
        references.forEach((item, index) => {
            item.region.style.zIndex = String(item === hovered ? references.length + 2 : item === selected ? references.length + 1 : index + 1);
            item.region.classList.toggle('is-selected', item === selected);
            item.region.classList.toggle('is-hovered', item === hovered);
        });
    }
    references.forEach(item => {
        const panel = item.region.querySelector('.settings-command-reference');
        panel.tabIndex = 0;
        const focus = () => {
            select(item.scope);
            book.dispatchEvent(new CustomEvent('settings-reference-focused', {detail: item.scope}));
        };
        panel.addEventListener('click', focus);
        panel.addEventListener('focus', focus);
    });
    let pointer;
    document.addEventListener('pointermove', event => {
        if (event.pointerType === 'touch' || (pointer?.x === event.clientX && pointer?.y === event.clientY)) return;
        pointer = {x: event.clientX, y: event.clientY};
        const panel = event.target.closest('.settings-command-reference');
        const item = panel ? references.find(reference => reference.region.contains(panel)) : null;
        // Animation can move a panel beneath a stationary pointer. Only real
        // pointer movement changes the temporary expansion target.
        changeExpansion(selected, item);
    }, {passive: true});
    document.addEventListener('pointerleave', () => { pointer = null; changeExpansion(selected, null); });
    function update() {
        frame = null;
        const active = references.filter(({scope}) => !scope.closest('[hidden]'));
        const shown = wide.matches && active.length > 0;
        book.classList.toggle('has-command-references', shown);
        references.forEach(item => { item.region.hidden = !wide.matches || !active.includes(item); });
        if (!shown) { rail.style.removeProperty('height'); updateLayout(shown); return; }
        // Absolute slots keep the editor's height independent of the lists.
        // Only focused or temporarily hovered lists may cover the next panel.
        let railHeight = main.getBoundingClientRect().height;
        const railTop = rail.getBoundingClientRect().top;
        const slots = active.map(item => ({item, top: item.anchor.getBoundingClientRect().top, bottom: item.scope.getBoundingClientRect().bottom}));
        slots.forEach(({item, top, bottom}, index) => {
            const next = slots[index + 1];
            item.region.style.setProperty('--settings-command-space', `${next ? Math.max(0, next.top - top - 16) : innerHeight - 32}px`);
            const end = Math.min(bottom, slots[index + 1]?.top ?? bottom);
            const panel = item.region.querySelector('.settings-command-reference');
            const border = panel.offsetHeight - panel.clientHeight;
            // Reserve its expanded footprint even while collapsed, so reaching
            // the page bottom cannot turn expansion into a scroll/hover loop.
            const expandedHeight = Math.min(innerHeight - 32, panel.scrollHeight + border);
            railHeight = Math.max(railHeight, top - railTop + expandedHeight);
            const height = Math.max(0, end - top, panel.getBoundingClientRect().height);
            item.region.style.top = `${top - railTop}px`;
            item.region.style.height = `${height}px`;
        });
        rail.style.height = `${railHeight}px`;
        stack();
        updateLayout(shown);
    }
    function schedule() { if (!frame) frame = requestAnimationFrame(update); }
    function resize() {
        book.querySelectorAll('.settings-command-members').forEach(details => { details.open = !mobile.matches && !wide.matches; });
        schedule();
    }
    const observer = new ResizeObserver(schedule);
    observer.observe(main);
    wide.addEventListener('change', resize);
    mobile.addEventListener('change', resize);
    book.addEventListener('settings-section-changed', () => { [...animations.keys()].forEach(stopAnimation); selected = null; hovered = null; update(); });
    book.addEventListener('settings-hover', event => select(event.detail));
    book.addEventListener('settings-context-scroll', event => {
        const target = event.detail.hovered || event.detail.target;
        if (target) select(target);
    });
    book.addEventListener('settings-scroll-start', event => select(event.detail));
    window.addEventListener('resize', schedule, {passive: true});
    window.addEventListener('pagehide', () => { observer.disconnect(); cancelAnimationFrame(frame); [...animations.keys()].forEach(stopAnimation); stopLayoutAnimations(); }, {once: true});
    resize();
})();
