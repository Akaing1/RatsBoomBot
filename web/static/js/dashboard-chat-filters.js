(() => {
    const axes = {users: ['vips', 'mods', 'subs', 'non_subs', 'bots'], types: ['commands', 'redeems', 'messages']};

    function dropdownPosition(anchor, size, viewport) {
        const minTop = viewport.top + 8;
        const minLeft = viewport.left + 8;
        return {
            top: Math.max(minTop, Math.min(anchor.bottom + 6, viewport.top + viewport.height - size.height - 8)),
            left: Math.max(minLeft, Math.min(anchor.right - size.width, viewport.left + viewport.width - size.width - 8))
        };
    }

    function category(message) {
        const type = message.is_redeem || ['redeem', 'redemption'].includes(message.kind)
            ? 'redeems' : message.kind === 'command' ? 'commands' : 'messages';
        const badges = new Set((message.badges || []).map(badge =>
            String(typeof badge === 'string' ? badge : badge.name || '').toLowerCase()));
        const user = message.is_bot ? 'bots'
            : badges.has('moderator') || message.accent === 'moderator' ? 'mods'
            : badges.has('vip') || message.accent === 'vip' ? 'vips'
            : badges.has('subscriber') || badges.has('founder') || message.accent === 'subscriber' ? 'subs'
            : 'non_subs';
        return {user, type};
    }

    function attach(element, onChange) {
        const control = element.closest('.live-chat-panel')?.querySelector('[data-chat-filter]');
        if (!control) return null;
        const button = control.querySelector('[data-chat-filter-toggle]');
        const options = control.querySelector('[data-chat-filter-options]');
        const countLabel = control.querySelector('[data-chat-filter-count]');
        const inputs = [...control.querySelectorAll('[data-chat-filter-option]')];
        const clearButtons = [...control.querySelectorAll('[data-chat-filter-clear]')];
        const storageKey = `ratsboombot:chat-filters:${control.dataset.channelId}`;
        const enabled = {users: new Set(axes.users), types: new Set(axes.types)};
        try {
            let saved = JSON.parse(window.localStorage.getItem(storageKey) || 'null');
            // Migrate the earlier flat selection without losing saved preferences.
            if (Array.isArray(saved)) {
                const renamed = saved.map(key => key === 'normal' ? 'non_subs' : key === 'other' ? 'messages' : key);
                saved = Object.fromEntries(Object.entries(axes).map(([axis, keys]) => [axis, renamed.filter(key => keys.includes(key))]));
            }
            for (const axis of Object.keys(axes)) {
                if (Array.isArray(saved?.[axis])) {
                    const keys = saved[axis].filter(key => axes[axis].includes(key));
                    // An empty section always means all options are enabled.
                    enabled[axis] = new Set(keys.length ? keys : axes[axis]);
                }
            }
        } catch (_) { /* Default to showing everything when storage is unavailable. */ }

        function positionDropdown() {
            if (options.hidden) return;
            const previousScrollTop = options.scrollTop;
            const viewport = window.visualViewport;
            const bounds = {
                top: viewport?.offsetTop || 0, left: viewport?.offsetLeft || 0,
                width: viewport?.width || window.innerWidth, height: viewport?.height || window.innerHeight
            };
            // Measure the natural height so resizing can remove the scroll limit again.
            options.style.maxHeight = 'none';
            options.style.overflowY = 'visible';
            const size = options.getBoundingClientRect();
            const availableHeight = Math.max(0, bounds.height - 16);
            if (size.height > availableHeight) {
                options.style.maxHeight = `${availableHeight}px`;
                options.style.overflowY = 'auto';
            }
            const position = dropdownPosition(button.getBoundingClientRect(), {
                width: size.width, height: Math.min(size.height, availableHeight)
            }, bounds);
            options.style.top = `${position.top}px`;
            options.style.left = `${position.left}px`;
            options.scrollTop = previousScrollTop;
        }
        window.addEventListener('resize', positionDropdown);
        document.addEventListener('scroll', event => {
            if (event.target !== options && !options.contains(event.target)) positionDropdown();
        }, true);
        window.visualViewport?.addEventListener('resize', positionDropdown);
        window.visualViewport?.addEventListener('scroll', positionDropdown);
        if ('ResizeObserver' in window) {
            const observer = new ResizeObserver(positionDropdown);
            observer.observe(button);
            observer.observe(options);
        }

        function sync() {
            const count = enabled.users.size + enabled.types.size;
            if (countLabel) countLabel.textContent = `| ${count}`;
            button.classList.toggle('has-filter-count', count < axes.users.length + axes.types.length);
            button.setAttribute('aria-label', `Filter chat, ${count} options enabled`);
            inputs.forEach(input => {
                const selection = enabled[input.dataset.chatFilterAxis];
                input.checked = selection.has(input.dataset.chatFilterOption);
                input.indeterminate = false;
            });
            clearButtons.forEach(clear => {
                const axis = clear.dataset.chatFilterClear;
                clear.hidden = axis === 'all'
                    ? enabled.users.size === axes.users.length && enabled.types.size === axes.types.length
                    : enabled[axis].size === axes[axis].length;
            });
            const filtered = Object.keys(axes).some(axis => enabled[axis].size < axes[axis].length);
            button.classList.toggle('is-filtered', filtered);
            button.title = filtered ? 'Filter chat (user and message-type filters active)' : 'Filter chat (all messages shown)';
        }
        function close(returnFocus = false) {
            options.hidePopover?.();
            options.hidden = true;
            button.setAttribute('aria-expanded', 'false');
            if (returnFocus) button.focus();
            else if (document.activeElement === button) button.blur();
        }
        button.addEventListener('click', () => {
            if (!options.hidden) { close(); return; }
            options.hidden = false;
            // Top-layer rendering avoids clipping by the mobile chat panel.
            options.showPopover?.();
            positionDropdown();
            button.setAttribute('aria-expanded', 'true');
        });
        control.addEventListener('keydown', event => {
            if (event.key === 'Escape' && !options.hidden) {
                event.preventDefault(); event.stopPropagation(); close(true);
            }
        });
        document.addEventListener('click', event => { if (!control.contains(event.target)) close(); });
        document.addEventListener('dashboard-carousel-card-changed', () => close());
        function applySelection() {
            for (const axis of Object.keys(axes)) {
                if (enabled[axis].size === 0) enabled[axis] = new Set(axes[axis]);
            }
            try {
                window.localStorage.setItem(storageKey, JSON.stringify({version: 2, users: [...enabled.users], types: [...enabled.types]}));
            } catch (_) {}
            sync(); onChange();
        }
        clearButtons.forEach(clear => clear.addEventListener('click', () => {
            const target = clear.dataset.chatFilterClear;
            const targets = target === 'all' ? Object.keys(axes) : [target];
            targets.forEach(axis => { enabled[axis] = new Set(axes[axis]); });
            applySelection();
        }));
        function solo(axis, keys) {
            const selection = enabled[axis];
            const alreadySoloed = selection.size === keys.length && keys.every(key => selection.has(key));
            enabled[axis] = alreadySoloed ? new Set(axes[axis]) : new Set(keys);
            applySelection();
        }
        control.addEventListener('contextmenu', event => {
            const row = event.target.closest('.chat-filter-row');
            const input = row?.querySelector('[data-chat-filter-option]');
            if (input && inputs.includes(input)) {
                event.preventDefault(); solo(input.dataset.chatFilterAxis, [input.dataset.chatFilterOption]);
            }
        });
        inputs.forEach(input => input.addEventListener('change', () => {
            const selection = enabled[input.dataset.chatFilterAxis];
            const key = input.dataset.chatFilterOption;
            if (input.checked) selection.add(key); else selection.delete(key);
            applySelection();
        }));
        sync();
        return {allows: ({user, type}) =>
            enabled.users.has(user) && enabled.types.has(type)};
    }
    window.dashboardChatFilters = {category, attach, dropdownPosition};
})();
