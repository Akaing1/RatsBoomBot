(() => {
    'use strict';
    const book = document.querySelector('[data-settings-book]');
    if (!book) return;
    const main = book.querySelector('.settings-main');
    const rail = book.querySelector('.settings-commands-rail');
    if (!main || !rail) return;
    rail.setAttribute('data-overlay-scrollbars', 'off');
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
        panel.setAttribute('data-overlay-scrollbars', 'off');
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
        const more = document.createElement('button');
        more.type = 'button';
        more.className = 'settings-command-expand';
        more.setAttribute('aria-label', 'Show more commands');
        more.hidden = true;
        more.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';
        panel.append(more);
        const endScope = scope.querySelector('#settings-control-feature-raid_bosses')
            ? scope.closest('[data-settings-page]') : scope;
        return {scope, endScope, anchor, region, panel, more};
    });
    if (!references.length) return;
    rail.removeAttribute('aria-hidden');
    const wide = matchMedia('(min-width: 1101px)');
    const mobile = matchMedia('(max-width: 768px)');
    const desktop = matchMedia('(min-width: 901px)');
    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
    const panels = new Map(references.map(item => [item.panel, item]));
    function setStyle(element, name, value) {
        if (element.style.getPropertyValue(name) !== value) element.style.setProperty(name, value);
    }
    let frame;
    let overlapFrame;
    const fadedPanels = new Set();
    let selected;
    let hovered;
    let layoutState;
    let layoutSnapshot;
    let layoutDirty = true;
    const layoutAnimations = new Map();
    const layoutPanels = [book.querySelector('.settings-tools'), main, rail].filter(Boolean);
    function stopLayoutAnimations() {
        layoutAnimations.forEach(animation => animation.cancel());
        layoutAnimations.clear();
    }
    function updateLayout(shown) {
        if (shown === layoutState && layoutAnimations.size) return;
        if (shown === layoutState && !layoutDirty) return;
        const previous = layoutAnimations.size ? new Map(layoutPanels.map(panel => [panel, panel.getBoundingClientRect()])) : layoutSnapshot;
        stopLayoutAnimations();
        const next = new Map(layoutPanels.map(panel => [panel, panel.getBoundingClientRect()]));
        if (previous && shown !== layoutState && desktop.matches && !reducedMotion.matches) {
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
        layoutDirty = false;
    }
    const animations = new Map();
    const closing = new Set();
    function stopAnimation(panel) {
        const animation = animations.get(panel);
        if (animation) { animation.onfinish = null; animation.cancel(); animations.delete(panel); }
        panel.style.removeProperty('max-height');
        panel.style.removeProperty('overflow-y');
        closing.delete(panel);
    }
    function select(target) {
        const match = selected?.scope.contains(target) ? selected : references.find(item => item.scope.contains(target));
        if (match) changeExpansion(match, null);
    }
    function changeExpansion(nextSelected, nextHovered) {
        if (selected === nextSelected && hovered === nextHovered) return;
        const changed = [...new Set([selected, hovered, nextSelected, nextHovered])].filter(item => item && !item.region.hidden
            && (item === selected || item === hovered) !== (item === nextSelected || item === nextHovered));
        if (!changed.length) {
            selected = nextSelected;
            hovered = nextHovered;
            stack();
            return;
        }
        if (reducedMotion.matches) {
            changed.forEach(item => stopAnimation(item.panel));
            selected = nextSelected;
            hovered = nextHovered;
            stack();
            updateNow();
            return;
        }
        const heights = changed.map(item => {
            const panel = item.panel;
            return {panel, region: item.region, height: panel.getBoundingClientRect().height, regionHeight: item.region.getBoundingClientRect().height,
                closing: item !== nextSelected && item !== nextHovered};
        });
        heights.forEach(({panel}) => stopAnimation(panel));
        heights.forEach(item => { if (item.closing) closing.add(item.panel); });
        selected = nextSelected;
        hovered = nextHovered;
        stack();
        updateNow();
        const targets = heights.map(item => ({...item, next: item.panel.getBoundingClientRect().height,
            nextRegionHeight: item.region.getBoundingClientRect().height}));
        let layersChanged = false;
        targets.forEach(({panel, region, height, regionHeight, next, nextRegionHeight}) => {
            if (Math.abs(next - height) < 1) {
                layersChanged = closing.delete(panel) || layersChanged;
                return;
            }
            panel.style.maxHeight = `${Math.max(height, next)}px`;
            panel.style.overflowY = 'hidden';
            region.style.height = `${Math.max(regionHeight, nextRegionHeight)}px`;
            const animation = panel.animate([{height: `${height}px`}, {height: `${next}px`}], {duration: 220, easing: 'ease-in-out'});
            animations.set(panel, animation);
            animation.onfinish = () => { stopAnimation(panel); stack(); schedule(); };
        });
        if (layersChanged) stack();
    }
    function stack() {
        references.forEach((item, index) => {
            const isClosing = closing.has(item.panel);
            setStyle(item.region, 'z-index', String(isClosing ? references.length + 3 : item === hovered ? references.length + 2 : item === selected ? references.length + 1 : index + 1));
            item.region.classList.toggle('is-closing', isClosing);
            item.region.classList.toggle('is-selected', item === selected);
            item.region.classList.toggle('is-hovered', item === hovered);
        });
        scheduleOverlaps();
    }
    function scheduleOverlaps() {
        if (!overlapFrame) overlapFrame = requestAnimationFrame(updateOverlaps);
    }
    function updateOverlaps() {
        overlapFrame = null;
        const active = references.filter(item => !item.region.hidden);
        if (active.length < 2 || !active.some(item => item === selected || item === hovered || closing.has(item.panel))) {
            fadedPanels.forEach(clearOverlap);
            return;
        }
        const measured = active.map(item => ({item, rect: item.panel.getBoundingClientRect(), layer: Number(item.region.style.zIndex)}));
        const covering = measured.filter(({item}) => item === selected || item === hovered || closing.has(item.panel)).sort((a, b) => b.layer - a.layer);
        const overlapping = new Set();
        for (const {item, rect, layer} of measured) {
            const above = covering.find(candidate => candidate.item !== item && candidate.layer > layer
                && candidate.rect.bottom > rect.top && candidate.rect.top < rect.bottom
                && candidate.rect.right > rect.left && candidate.rect.left < rect.right);
            if (!above) continue;
            overlapping.add(item);
            if (!fadedPanels.has(item)) {
                fadedPanels.add(item);
                item.panel.classList.add('has-command-overlap');
            }
            setStyle(item.panel, '--settings-command-overlap-start', `${Math.max(0, above.rect.top - rect.top)}px`);
            setStyle(item.panel, '--settings-command-overlap-end', `${Math.min(rect.height, above.rect.bottom - rect.top)}px`);
        }
        fadedPanels.forEach(item => { if (!overlapping.has(item)) clearOverlap(item); });
        if (isAnimating(animations) || isAnimating(layoutAnimations)) scheduleOverlaps();
    }
    function isAnimating(collection) {
        for (const animation of collection.values()) if (animation.playState === 'running') return true;
        return false;
    }
    function clearOverlap(item) {
        fadedPanels.delete(item);
        item.panel.classList.remove('has-command-overlap');
        item.panel.style.removeProperty('--settings-command-overlap-start');
        item.panel.style.removeProperty('--settings-command-overlap-end');
    }
    references.forEach(item => {
        const panel = item.panel;
        panel.tabIndex = 0;
        const focus = () => {
            select(item.scope);
            book.dispatchEvent(new CustomEvent('settings-reference-focused', {detail: item.scope}));
        };
        panel.addEventListener('click', focus);
        panel.addEventListener('focus', focus);
        panel.addEventListener('scroll', () => updateOverflow(item), {passive: true});
    });
    function updateOverflow(item) {
        const hidden = item.panel.scrollHeight - item.panel.clientHeight - item.panel.scrollTop <= 1;
        if (item.more.hidden !== hidden) item.more.hidden = hidden;
    }
    let pointer;
    document.addEventListener('pointermove', event => {
        if (event.pointerType === 'touch' || (pointer?.x === event.clientX && pointer?.y === event.clientY)) return;
        pointer = {x: event.clientX, y: event.clientY};
        const panel = event.target.closest('.settings-command-reference');
        const item = panels.get(panel) || null;
        // Animation can move a panel beneath a stationary pointer. Only real
        // pointer movement changes the temporary expansion target.
        changeExpansion(item && item !== selected ? null : selected, item);
    }, {passive: true});
    document.addEventListener('pointerleave', () => { pointer = null; changeExpansion(selected, null); });
    document.addEventListener('click', event => {
        if (!rail.contains(event.target)) changeExpansion(null, null);
    });
    function update() {
        frame = null;
        const active = [];
        references.forEach(item => {
            const visible = wide.matches && !item.scope.closest('[hidden]');
            if (item.region.hidden === visible) item.region.hidden = !visible;
            if (visible) active.push(item);
        });
        const shown = wide.matches && active.length > 0;
        book.classList.toggle('has-command-references', shown);
        if (!shown) { rail.style.removeProperty('height'); updateLayout(shown); return; }
        // Absolute slots keep the editor's height independent of the lists.
        // Only focused or temporarily hovered lists may cover the next panel.
        let railHeight = main.getBoundingClientRect().height;
        const railTop = rail.getBoundingClientRect().top;
        const slots = active.map(item => ({item, top: item.anchor.getBoundingClientRect().top, bottom: item.endScope.getBoundingClientRect().bottom}));
        // Apply constraints together, then read sizes together to avoid a layout
        // recalculation for each commands panel.
        slots.forEach(({item, top}, index) => {
            const next = slots[index + 1];
            setStyle(item.region, '--settings-command-space', next ? `${Math.max(0, next.top - top - 16)}px` : 'none');
        });
        const measured = slots.map(slot => {
            const panel = slot.item.panel;
            return {...slot, panelHeight: panel.getBoundingClientRect().height,
                clientHeight: panel.clientHeight, scrollHeight: panel.scrollHeight,
                border: panel.offsetHeight - panel.clientHeight, scrollTop: panel.scrollTop};
        });
        measured.forEach(({item, top, bottom, panelHeight, clientHeight, scrollHeight, border, scrollTop}, index) => {
            const end = Math.min(bottom, slots[index + 1]?.top ?? bottom);
            // Reserve its expanded footprint even while collapsed, so reaching
            // the page bottom cannot turn expansion into a scroll/hover loop.
            const expandedHeight = scrollHeight + border;
            railHeight = Math.max(railHeight, top - railTop + expandedHeight);
            setStyle(item.region, '--settings-command-top', `${Math.min(16, innerHeight - 16 - panelHeight)}px`);
            const height = Math.max(0, end - top, panelHeight);
            setStyle(item.region, 'top', `${top - railTop}px`);
            setStyle(item.region, 'height', `${height}px`);
            const hidden = scrollHeight - clientHeight - scrollTop <= 1;
            if (item.more.hidden !== hidden) item.more.hidden = hidden;
        });
        setStyle(rail, 'height', `${railHeight}px`);
        updateLayout(shown);
        scheduleOverlaps();
    }
    function schedule() { if (!frame) frame = requestAnimationFrame(update); }
    function updateNow() { cancelAnimationFrame(frame); update(); }
    function resize() {
        book.querySelectorAll('.settings-command-members').forEach(details => { details.open = !mobile.matches && !wide.matches; });
        schedule();
    }
    const widths = new WeakMap();
    const observer = new ResizeObserver(entries => {
        for (const entry of entries) {
            if (widths.get(entry.target) !== entry.contentRect.width) {
                widths.set(entry.target, entry.contentRect.width);
                layoutDirty = true;
            }
        }
        schedule();
    });
    observer.observe(main);
    references.forEach(item => observer.observe(item.panel));
    wide.addEventListener('change', resize);
    mobile.addEventListener('change', resize);
    book.addEventListener('settings-section-changed', () => { [...animations.keys()].forEach(stopAnimation); selected = null; hovered = null; stack(); updateNow(); });
    book.addEventListener('settings-hover', event => select(event.detail));
    book.addEventListener('settings-context-scroll', event => {
        // Viewport tracking may move the menu highlight without dismissing a
        // commands panel the user is reading. A new middle-panel hover wins.
        if (!event.detail.hovered && (selected || hovered)) return;
        const target = event.detail.hovered || event.detail.target;
        if (target) select(target);
    });
    book.addEventListener('settings-scroll-start', event => select(event.detail));
    window.addEventListener('resize', () => { layoutDirty = true; schedule(); }, {passive: true});
    window.addEventListener('scroll', scheduleOverlaps, {passive: true});
    window.addEventListener('pagehide', () => { observer.disconnect(); cancelAnimationFrame(frame); cancelAnimationFrame(overlapFrame); [...animations.keys()].forEach(stopAnimation); stopLayoutAnimations(); }, {once: true});
    stack();
    resize();
})();
