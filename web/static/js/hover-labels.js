(() => {
    const interactive = 'button, a[href], input:not([type="hidden"]), select, textarea, [contenteditable], [role="button"], [role="checkbox"], [role="tab"]';
    const values = '[data-queue-count], [data-dashboard-points-lost], [data-ad-status], [data-ad-status-mirror]';
    const generated = new WeakMap();
    const touchTitles = new WeakMap();
    let activeElement = null;
    let originalTitle = '';
    let hoverTimer = null;
    let touchDismissTimer = null;
    let observer = null;
    let touchGesture = null;
    let suppressTouchClick = false;
    let lastPointerType = '';
    const touchMode = () => lastPointerType === 'touch' || window.matchMedia?.('(hover: none)').matches;
    const tooltip = document.createElement('div');
    tooltip.className = 'dashboard-hover-tooltip';
    tooltip.setAttribute('role', 'tooltip');
    tooltip.setAttribute('popover', 'manual');
    tooltip.hidden = true;
    document.body.appendChild(tooltip);

    function hideTooltip() {
        window.clearTimeout(hoverTimer);
        window.clearTimeout(touchDismissTimer);
        observer?.disconnect();
        tooltip.hidePopover?.();
        tooltip.hidden = true;
        if (activeElement && originalTitle && !activeElement.getAttribute('title') && !touchMode()) activeElement.setAttribute('title', originalTitle);
        activeElement = null;
        originalTitle = '';
    }
    function positionTooltip() {
        if (!activeElement) return;
        const rect = activeElement.getBoundingClientRect();
        const size = tooltip.getBoundingClientRect();
        const viewport = window.visualViewport;
        const left = viewport?.offsetLeft || 0;
        const top = viewport?.offsetTop || 0;
        const width = viewport?.width || window.innerWidth;
        const height = viewport?.height || window.innerHeight;
        let textLeft = rect.left;
        let textRight = rect.right;
        if (document.createRange && document.createTreeWalker) {
            const anchor = activeElement.querySelector('.nav-link-label, .sidebar-button-label, .chat-filter-button-label') || activeElement;
            const walker = document.createTreeWalker(anchor, NodeFilter.SHOW_TEXT);
            const bounds = [];
            let node;
            while ((node = walker.nextNode())) {
                if (!node.textContent.trim() || node.parentElement?.closest('[aria-hidden="true"], svg, .nav-link-icon')) continue;
                const range = document.createRange();
                range.selectNodeContents(node);
                for (const part of range.getClientRects()) {
                    const start = Math.max(rect.left, part.left);
                    const end = Math.min(rect.right, part.right);
                    if (end > start && part.bottom > rect.top && part.top < rect.bottom) bounds.push([start, end]);
                }
            }
            if (bounds.length) {
                textLeft = Math.min(...bounds.map(part => part[0]));
                textRight = Math.max(...bounds.map(part => part[1]));
            }
        }
        const centeredLeft = (textLeft + textRight - size.width) / 2;
        tooltip.style.left = `${Math.max(left + 8, Math.min(centeredLeft, left + width - size.width - 8))}px`;
        tooltip.style.top = `${Math.max(top + 8, rect.bottom + size.height + 14 <= top + height ? rect.bottom + 6 : rect.top - size.height - 6)}px`;
    }
    function refreshTooltip() {
        if (!activeElement || tooltip.hidden) return;
        const nativeTitle = activeElement.getAttribute('title');
        if (nativeTitle) {
            originalTitle = nativeTitle;
            activeElement.removeAttribute('title');
        }
        const label = labelFor(activeElement);
        if (tooltip.textContent !== label) tooltip.textContent = label;
        positionTooltip();
    }
    function queueTooltip(element, delay = 150) {
        if (activeElement === element) { refreshTooltip(); return; }
        hideTooltip();
        activeElement = element;
        hoverTimer = window.setTimeout(() => {
            originalTitle = element.getAttribute('title') || '';
            tooltip.hidden = false;
            tooltip.showPopover?.();
            refreshTooltip();
            if (touchGesture) suppressTouchClick = true;
            if ('MutationObserver' in window) {
                observer = new MutationObserver(refreshTooltip);
                observer.observe(element, {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['title', 'aria-label']});
            }
        }, delay);
    }

    function text(value) { return String(value || '').replace(/\s+/g, ' ').trim(); }
    function labelFor(element) {
        const navigationLabel = element.querySelector('.nav-link-label, .sidebar-button-label');
        if (navigationLabel) return text(navigationLabel.textContent);
        if (element.matches('.chat-filter-row')) return text(element.textContent);
        if (element.matches(values)) return text(element.textContent);
        if (element.dataset.channelField) return text(element.textContent);
        if (element.dataset.dashboardStat !== undefined) {
            const label = text(element.querySelector('span')?.textContent);
            const value = text(element.querySelector('[data-dashboard-stat-value]')?.textContent);
            return `${label}: ${value}`;
        }
        const explicit = element.getAttribute('title') || touchTitles.get(element) || (element === activeElement ? originalTitle : '');
        // Keep descriptions supplied by individual controls; refresh only our own titles.
        if (explicit && explicit !== generated.get(element)) return explicit;
        const aria = text(element.getAttribute('aria-label'));
        if (aria) return aria;
        const labelledBy = element.getAttribute('aria-labelledby');
        if (labelledBy) {
            const label = text(labelledBy.split(/\s+/).map(id => document.getElementById(id)?.textContent || '').join(' '));
            if (label) return label;
        }
        const labels = text([...element.labels || []].map(label => label.textContent).join(' '));
        if (labels) return labels;
        const parentLabel = text(element.closest('label')?.textContent);
        if (parentLabel) return parentLabel;
        const placeholder = text(element.getAttribute('placeholder'));
        if (placeholder) return placeholder;
        const alt = text(element.getAttribute('alt') || element.querySelector('img[alt]')?.getAttribute('alt'));
        const caption = text(element.textContent);
        if (element.matches('input, select, textarea')) return alt;
        return caption || alt || touchTitles.get(element) || '';
    }

    function update(event) {
        const target = event.target;
        if (!(target instanceof Element)) return;
        if (target.closest('.dashboard-video-frame, #dashboard-twitch-player, iframe, video')) {
            hideTooltip();
            return;
        }
        const attachedLabel = target.closest('label');
        const attachedCheckbox = attachedLabel?.querySelector('input[type="checkbox"], input[type="radio"]');
        // Treat the checkbox and its text as one hover target.
        if (attachedCheckbox) attachedCheckbox.removeAttribute('title');
        const element = target.closest(values)
            || (attachedCheckbox ? attachedLabel : null)
            || target.closest(interactive) || target.closest('img[alt], [title]');
        if (!element || element.matches('h1, h2, h3, h4, h5, h6')
            || (element.getAttribute('aria-hidden') === 'true' && !element.matches(values))) return;
        const label = labelFor(element);
        if (!label) return;
        const previous = element.getAttribute('title');
        if (element.matches(values) || element.matches('.chat-filter-row')
            || element.dataset.channelField || element.dataset.dashboardStat !== undefined
            || !previous || previous === generated.get(element)) {
            element.setAttribute('title', label);
            generated.set(element, label);
        }
        if (touchMode() || event.pointerType === 'touch') {
            touchTitles.set(element, element.getAttribute('title') || label);
            element.removeAttribute('title');
            if (event.type === 'touch-hold') queueTooltip(element, 550);
            else refreshTooltip();
        } else if (event.type !== 'input') queueTooltip(element);
        else refreshTooltip();
    }

    // Delegation includes newly loaded chat actions, emotes, queue entries, and settings.
    document.addEventListener('pointerover', event => {
        if (event.pointerType) lastPointerType = event.pointerType;
        update(event);
    });
    document.addEventListener('focusin', update);
    document.addEventListener('input', update);
    document.addEventListener('pointerout', event => {
        if (!activeElement || activeElement.contains(event.relatedTarget)) return;
        // Replacing a live counter's text can emit pointerout without the pointer moving.
        const rect = activeElement.getBoundingClientRect();
        if (event.clientX >= rect.left && event.clientX <= rect.right
            && event.clientY >= rect.top && event.clientY <= rect.bottom) return;
        hideTooltip();
    });
    document.addEventListener('focusout', event => {
        if (!activeElement?.contains(event.relatedTarget)) hideTooltip();
    });
    document.addEventListener('pointerdown', event => {
        hideTooltip();
        if (event.pointerType) lastPointerType = event.pointerType;
        touchGesture = null;
        suppressTouchClick = false;
        if (event.pointerType !== 'touch') return;
        touchGesture = {x: event.clientX, y: event.clientY, id: event.pointerId};
        update({target: event.target, type: 'touch-hold', pointerType: 'touch'});
    });
    document.addEventListener('pointermove', event => {
        if (!touchGesture || event.pointerId !== touchGesture.id) return;
        if (Math.hypot(event.clientX - touchGesture.x, event.clientY - touchGesture.y) > 10) {
            touchGesture = null;
            suppressTouchClick = false;
            hideTooltip();
        }
    }, {passive: true});
    document.addEventListener('pointerup', event => {
        if (!touchGesture || event.pointerId !== touchGesture.id) return;
        touchGesture = null;
        if (tooltip.hidden) hideTooltip();
        else touchDismissTimer = window.setTimeout(() => { hideTooltip(); suppressTouchClick = false; }, 1500);
    });
    document.addEventListener('pointercancel', () => {
        touchGesture = null;
        suppressTouchClick = false;
        hideTooltip();
    });
    document.addEventListener('click', event => {
        if (!suppressTouchClick) return;
        suppressTouchClick = false;
        event.preventDefault();
        event.stopImmediatePropagation();
    }, true);
    document.addEventListener('scroll', event => {
        // Content updates can produce internal scroll events; these are not page navigation.
        if (event.target !== tooltip && !tooltip.contains(event.target)
            && event.target !== activeElement && !activeElement?.contains(event.target)) hideTooltip();
    }, true);
    document.addEventListener('keydown', event => { if (event.key === 'Escape') hideTooltip(); });
    document.addEventListener('dashboard-carousel-card-changed', hideTooltip);
    window.addEventListener('resize', hideTooltip);
})();
