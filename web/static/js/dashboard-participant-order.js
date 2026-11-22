(() => {
    const savedOrders = new WeakMap();

    window.createDashboardParticipantOrder = (container, selector, idOf, onReorder, canDrag) => {
        const events = new AbortController();
        const options = {signal: events.signal};
        const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
        const visibleItems = () => [...container.children].filter(child => !child.hidden && child.matches(selector));
        let drag, landingGhost, landingTimer, moveFrame, suppressClick = false;
        const itemAt = target => {
            const item = target?.closest(selector);
            return item?.parentElement === container && canDrag(item) ? item : null;
        };
        function clearLanding() {
            clearTimeout(landingTimer);
            landingGhost?.remove();
            landingGhost = null;
        }
        function clearDrag() {
            cancelAnimationFrame(moveFrame);
            moveFrame = null;
            if (!drag) return;
            drag.item.classList.remove('participant-drag-source');
            container.classList.remove('is-reordering-participants');
            drag.slots?.forEach(({item}) => {
                item.style.removeProperty('--participant-drag-shift');
            });
            drag.placeholder?.remove();
            drag.ghost?.remove();
            drag = null;
        }
        function position(element, left, top) {
            element.style.left = `${left}px`;
            element.style.top = `${top}px`;
        }
        function beginDrag() {
            const {item} = drag;
            const rect = item.getBoundingClientRect();
            const ghost = item.cloneNode(true);
            ghost.querySelectorAll('.stream-call-player, .stream-call-more').forEach(element => element.remove());
            ghost.removeAttribute('data-channel');
            ghost.removeAttribute('data-user-id');
            ghost.classList.add('participant-drag-ghost');
            ghost.inert = true;
            ghost.setAttribute('aria-hidden', 'true');
            const placeholder = document.createElement('div');
            placeholder.className = 'participant-drop-placeholder';
            placeholder.setAttribute('aria-hidden', 'true');
            const radius = getComputedStyle(item).borderRadius;
            for (const preview of [ghost, placeholder]) {
                preview.style.width = `${rect.width}px`;
                preview.style.height = `${rect.height}px`;
                preview.style.borderRadius = radius;
                position(preview, rect.left, rect.top);
            }
            const overlayHost = container.closest('dialog') || document.body;
            overlayHost.append(placeholder, ghost);
            const slots = visibleItems().filter(canDrag).map(item => ({item, rect: item.getBoundingClientRect()}));
            Object.assign(drag, {
                ghost, placeholder, slots, origin: container.getBoundingClientRect(),
                offsetX: drag.x - rect.left, offsetY: drag.y - rect.top,
                from: slots.findIndex(slot => slot.item === item)
            });
            drag.to = drag.from;
            item.classList.add('participant-drag-source');
            container.classList.add('is-reordering-participants');
            requestAnimationFrame(() => {
                if (drag?.ghost === ghost) ghost.classList.add('is-lifted');
            });
        }
        function movePreview() {
            moveFrame = null;
            const {ghost, placeholder, slots, from, origin, clientX, clientY} = drag;
            const bounds = container.getBoundingClientRect();
            const dx = bounds.left - origin.left, dy = bounds.top - origin.top;
            const x = clientX - dx, y = clientY - dy;
            position(ghost, clientX - drag.offsetX, clientY - drag.offsetY);
            // Hit-test the layout slots so sliding cards cannot change the drop target.
            const target = slots.findIndex(({rect}) => x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom);
            const to = target < 0 ? drag.to : target;
            position(placeholder, slots[to].rect.left + dx, slots[to].rect.top + dy);
            if (to === drag.to) return;
            drag.to = to;
            slots.forEach(({item, rect}, index) => {
                if (index === from) return;
                const slot = index > from && index <= to ? index - 1 : index < from && index >= to ? index + 1 : index;
                const destination = slots[slot].rect;
                item.style.setProperty('--participant-drag-shift', `${destination.left - rect.left}px ${destination.top - rect.top}px`);
            });
        }
        function schedulePreview() {
            if (drag?.ghost && !moveFrame) moveFrame = requestAnimationFrame(movePreview);
        }
        container.addEventListener('pointerdown', event => {
            suppressClick = false;
            if (!event.isPrimary || event.button !== 0 || event.target.closest('.stream-call-more')) return;
            const item = itemAt(event.target);
            if (!item) return;
            clearLanding();
            drag = {item, pointer: event.pointerId, x: event.clientX, y: event.clientY};
        }, options);
        window.addEventListener('pointermove', event => {
            if (!drag || event.pointerId !== drag.pointer) return;
            if (!drag.ghost) {
                if (Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 6) return;
                if (itemAt(drag.item) !== drag.item || !drag.item.getClientRects().length) {
                    clearDrag();
                    return;
                }
                suppressClick = true;
                container.setPointerCapture(event.pointerId);
                beginDrag();
            }
            drag.clientX = event.clientX;
            drag.clientY = event.clientY;
            schedulePreview();
        }, options);
        window.addEventListener('scroll', schedulePreview, {...options, capture: true, passive: true});
        window.addEventListener('resize', clearDrag, options);
        window.addEventListener('pointerup', event => {
            if (!drag || event.pointerId !== drag.pointer) return;
            if (drag.ghost) {
                cancelAnimationFrame(moveFrame);
                drag.clientX = event.clientX;
                drag.clientY = event.clientY;
                movePreview();
            }
            const {item, ghost, slots, from, to} = drag;
            const target = slots?.[to].item;
            drag.ghost = null;
            clearDrag();
            if (!ghost) return;
            const visible = visibleItems();
            const start = visible.indexOf(item), end = visible.indexOf(target);
            if (from !== to && start >= 0 && end >= 0 && canDrag(item) && canDrag(target)) {
                visible.splice(end, 0, ...visible.splice(start, 1));
                savedOrders.set(container, new Map(visible.map((item, index) => [idOf(item), index])));
                onReorder();
            }
            if (reducedMotion.matches || !item.getClientRects().length) {
                ghost.remove();
                return;
            }
            const rect = item.getBoundingClientRect();
            ghost.classList.add('is-dropping');
            position(ghost, rect.left, rect.top);
            landingGhost = ghost;
            landingTimer = setTimeout(clearLanding, 180);
        }, options);
        container.addEventListener('lostpointercapture', clearDrag, options);
        window.addEventListener('pointercancel', clearDrag, options);
        container.addEventListener('click', event => {
            if (!suppressClick || !event.detail) return;
            suppressClick = false;
            event.stopImmediatePropagation();
            event.preventDefault();
        }, {...options, capture: true});
        container.addEventListener('dragstart', event => event.preventDefault(), options);
        return {
            sort(entries, key) {
                const rank = savedOrders.get(container);
                if (!rank) return entries;
                return entries.sort((left, right) => (rank.get(key(left)) ?? Infinity) - (rank.get(key(right)) ?? Infinity));
            },
            destroy() { clearDrag(); clearLanding(); events.abort(); }
        };
    };
})();
