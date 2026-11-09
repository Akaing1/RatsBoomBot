(() => {
    const platforms = {twitch: ['vips', 'mods', 'subs', 'non_subs', 'bots'],
        youtube: ['youtube_mods', 'youtube_members', 'youtube_non_members', 'youtube_bots']};
    const messageTypes = ['commands', 'redeems', 'messages', 'gifs', 'bits', 'watch_streaks', 'gigantified_emotes'];
    function migrateTypes(types, version = 0) {
        const keys = [...types];
        if (version < 7 && keys.includes('messages')) keys.push('gifs');
        if (version < 8) {
            if (keys.includes('messages')) keys.push('bits', 'gigantified_emotes');
            if (keys.includes('redeems')) keys.push('watch_streaks');
        }
        return [...new Set(keys)];
    }

    function dropdownPosition(anchor, size, viewport) {
        const minTop = viewport.top + 8;
        const minLeft = viewport.left + 8;
        return {
            top: Math.max(minTop, Math.min(anchor.bottom + 6, viewport.top + viewport.height - size.height - 8)),
            left: Math.max(minLeft, Math.min(anchor.right - size.width, viewport.left + viewport.width - size.width - 8))
        };
    }

    function category(message) {
        const isNotice = Boolean(message.notice_type);
        const source = {origin: message.is_shared ? 'shared' : 'local', channel: message.is_shared ? String(message.source_channel_id || '') : 'local',
            ...(message.gigantified_emote ? {gigantified: true} : {})};
        const type = message.notice_type === 'watch_streak' ? 'watch_streaks' : message.bits > 0 ? 'bits'
            : (message.segments || []).some(segment => segment.type === 'gif') ? 'gifs' : message.is_redeem || isNotice || message.kind === 'redeem' || message.kind === 'redemption'
            ? 'redeems' : message.kind === 'command' ? 'commands' : 'messages';
        if (message.is_bot || isNotice) {
            return {user: message.platform === 'youtube' ? 'youtube_bots' : 'bots', type, ...source};
        }
        const badges = new Set((message.badges || []).map(badge =>
            String(typeof badge === 'string' ? badge : badge.name || '').toLowerCase()));
        const user = message.platform === 'youtube'
            ? (badges.has('mod') || badges.has('moderator') ? 'youtube_mods'
                : badges.has('member') ? 'youtube_members' : 'youtube_non_members')
            : badges.has('moderator') || message.accent === 'moderator' ? 'mods'
            : badges.has('vip') || message.accent === 'vip' ? 'vips'
            : badges.has('subscriber') || badges.has('founder') || message.accent === 'subscriber' ? 'subs'
            : 'non_subs';
        return {user, type, ...source};
    }

    function attach(element, onChange) {
        const control = element.closest('.live-chat-panel')?.querySelector('[data-chat-filter]');
        if (!control) return null;
        const button = control.querySelector('[data-chat-filter-toggle]');
        const options = control.querySelector('[data-chat-filter-options]');
        const countLabel = control.querySelector('[data-chat-filter-count]');
        const inputs = [...control.querySelectorAll('[data-chat-filter-option]')];
        const platformToggles = [...control.querySelectorAll('[data-chat-filter-platform]')];
        const connectionBadges = [...control.querySelectorAll('[data-chat-filter-connection]')];
        const connectedPlatforms = platformToggles.filter(input => !input.disabled)
            .map(input => input.dataset.chatFilterPlatform);
        const axes = {users: connectedPlatforms.flatMap(platform => platforms[platform]), types: messageTypes};
        const channelList = control.querySelector('[data-chat-filter-channels]');
        const channelInputs = new Map();
        let channels = {};
        let origin = 'all';
        let connectionBadgesShown = false;
        const clearButtons = [...control.querySelectorAll('[data-chat-filter-clear]')];
        const storageKey = `ratsboombot:chat-filters:${control.dataset.channelId}${window.dashboardChatDebug?.active ? ':test' : ''}`;
        const enabled = {users: new Set(axes.users), types: new Set(axes.types)};
        function restore(saved) {
            origin = ['all', 'local', 'shared'].includes(saved?.origin) ? saved.origin : 'all';
            channels = {...saved?.channels};
            delete channels.local;
            if (origin === 'shared') origin = 'all';
            // Migrate the earlier flat selection without losing saved preferences.
            if (Array.isArray(saved)) {
                const renamed = saved.map(key => key === 'normal' ? 'non_subs' : key === 'other' ? 'messages' : key);
                saved = Object.fromEntries(Object.entries(axes).map(([axis, keys]) => [axis, renamed.filter(key => keys.includes(key))]));
            }
            for (const axis of Object.keys(axes)) {
                if (Array.isArray(saved?.[axis])) {
                    const keys = (axis === 'types' ? migrateTypes(saved[axis], saved.version) : saved[axis]).filter(key => axes[axis].includes(key));
                    if (axis === 'users') {
                        if (!saved.version || saved.version < 3) {
                            keys.push(...platforms.youtube.filter(key => axes.users.includes(key)));
                        }
                        if (Array.isArray(saved.connectedPlatforms)) {
                            connectedPlatforms.filter(platform => !saved.connectedPlatforms.includes(platform))
                                .forEach(platform => keys.push(...platforms[platform]));
                        }
                    }
                    // An empty section always means all options are enabled.
                    enabled[axis] = new Set(keys.length ? keys : axes[axis]);
                }
            }
        }
        try { restore(JSON.parse(window.localStorage.getItem(storageKey) || 'null')); }
        catch (_) { /* Default to showing everything when storage is unavailable. */ }

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
            channelInputs.forEach((input, id) => {
                if (id === 'shared') {
                    const selections = [origin !== 'local', ...Object.entries(channels).map(([, checked]) => checked)];
                    input.checked = selections.every(Boolean);
                    input.indeterminate = selections.some(Boolean) && !input.checked;
                } else { input.checked = allowsChannel({origin: 'shared', channel: id}); }
            });
            const count = enabled.users.size + enabled.types.size + [...channelInputs.values()].filter(input => input.checked).length;
            if (countLabel) countLabel.textContent = `| ${count}`;
            button.classList.toggle('has-filter-count', count < axes.users.length + axes.types.length + channelInputs.size);
            button.setAttribute('aria-label', `Filter chat, ${count} options enabled`);
            inputs.forEach(input => {
                const selection = enabled[input.dataset.chatFilterAxis];
                input.disabled = !axes[input.dataset.chatFilterAxis].includes(input.dataset.chatFilterOption);
                input.checked = selection.has(input.dataset.chatFilterOption);
                input.indeterminate = false;
            });
            platformToggles.forEach(input => {
                input.hidden = connectedPlatforms.length < 2;
                const keys = platforms[input.dataset.chatFilterPlatform];
                const count = keys.filter(key => enabled.users.has(key)).length;
                input.checked = count === keys.length;
                input.indeterminate = count > 0 && count < keys.length;
            });
            clearButtons.forEach(clear => {
                const axis = clear.dataset.chatFilterClear;
                clear.hidden = axis === 'all'
                    ? enabled.users.size === axes.users.length && enabled.types.size === axes.types.length && origin === 'all' && !Object.values(channels).includes(false)
                    : axis === 'channels' ? origin === 'all' && !Object.values(channels).includes(false) : enabled[axis].size === axes[axis].length;
            });
            const filtered = origin !== 'all' || Object.values(channels).includes(false) || Object.keys(axes).some(axis => enabled[axis].size < axes[axis].length);
            button.classList.toggle('is-filtered', filtered);
            button.title = filtered ? 'Filter chat (filters active)' : 'Filter chat (all messages shown)';
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
            if (!connectionBadgesShown) {
                connectionBadgesShown = true;
                window.setTimeout(() => {
                    connectionBadges.forEach(badge => {
                        if (badge.dataset.connected === 'true') badge.classList.add('is-fading');
                    });
                }, 1500);
            }
        });
        control.addEventListener('keydown', event => {
            if (event.key === 'Escape' && !options.hidden) {
                event.preventDefault(); event.stopPropagation(); close(true);
            }
        });
        document.addEventListener('click', event => { if (!control.contains(event.target)) close(); });
        document.addEventListener('dashboard-carousel-card-changed', () => close());
        const snapshot = () => ({version: 8, origin, channels: {...channels}, connectedPlatforms, users: [...enabled.users], types: [...enabled.types]});
        const syncUrl = !window.dashboardChatDebug?.active && control.dataset.preferencesUrl;
        const syncStatus = control.querySelector('[data-chat-filter-sync-status]');
        let remoteReady = false, loading = false, dirty = false, saving = false, pending = null;
        const status = message => { if (syncStatus && syncUrl) { syncStatus.textContent = message; syncStatus.hidden = !message; } };
        async function requestPreferences(options = {}) {
            const controller = new AbortController();
            const timeout = window.setTimeout(() => controller.abort(), 10000);
            try {
                const response = await fetch(syncUrl, {...options, signal: controller.signal, cache: 'no-store', headers: {Accept: 'application/json'}});
                if (!response.ok) throw new Error('Chat preferences unavailable');
                return await response.json();
            } finally { window.clearTimeout(timeout); }
        }
        async function saveRemote() {
            pending = snapshot();
            if (saving || !remoteReady) return;
            saving = true;
            try {
                while (pending) {
                    const selection = pending; pending = null;
                    const body = new FormData();
                    body.set('csrf_token', control.dataset.csrfToken);
                    body.set('preferences', JSON.stringify(selection));
                    await requestPreferences({method: 'POST', body});
                }
                dirty = false; status('');
            } catch (_) {
                remoteReady = false;
                status('OBS filters could not be saved. Change a filter to retry.');
            } finally { saving = false; }
        }
        async function loadRemote() {
            if (!syncUrl || loading) return;
            loading = true;
            try {
                const result = await requestPreferences();
                if (result.preferences && !dirty) { restore(result.preferences); sync(); onChange(); persistSelection(); }
                remoteReady = true;
                if (!result.preferences || dirty || JSON.stringify(result.preferences) !== JSON.stringify(snapshot())) await saveRemote();
            } catch (_) { status('OBS filters could not be loaded. Change a filter to retry.'); }
            finally { loading = false; }
        }
        function persistSelection() {
            try {
                window.localStorage.setItem(storageKey, JSON.stringify(snapshot()));
            } catch (_) {}
        }
        function applySelection() {
            for (const axis of Object.keys(axes)) {
                if (enabled[axis].size === 0) enabled[axis] = new Set(axes[axis]);
            }
            persistSelection();
            sync(); onChange();
            if (syncUrl) { dirty = true; if (remoteReady) saveRemote(); else loadRemote(); }
        }
        clearButtons.forEach(clear => clear.addEventListener('click', () => {
            const target = clear.dataset.chatFilterClear;
            if (target === 'all' || target === 'channels') { origin = 'all'; channels = {}; }
            const targets = target === 'all' ? Object.keys(axes) : target === 'channels' ? [] : [target];
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
            const channelInput = row?.querySelector('[data-chat-filter-channel]');
            if (channelInput && channelInput.dataset.chatFilterChannel !== 'shared') {
                event.preventDefault();
                const id = channelInput.dataset.chatFilterChannel;
                const soloed = [...channelInputs.keys()].filter(key => key !== 'shared').every(key => allowsChannel({origin: 'shared', channel: key}) === (key === id)) && origin === 'local';
                origin = soloed ? 'all' : 'local';
                channels = soloed ? {} : Object.fromEntries([...channelInputs.keys()].filter(key => key !== 'shared').map(key => [key, key === id]));
                applySelection(); return;
            }
            const input = row?.querySelector('[data-chat-filter-option]');
            if (input && inputs.includes(input) && !input.disabled) {
                event.preventDefault(); solo(input.dataset.chatFilterAxis, [input.dataset.chatFilterOption]);
            } else {
                const platformInput = row?.querySelector('[data-chat-filter-platform]');
                if (platformInput && platformToggles.includes(platformInput) && !platformInput.disabled && !platformInput.hidden) {
                    event.preventDefault(); solo('users', platforms[platformInput.dataset.chatFilterPlatform]);
                }
            }
        });
        platformToggles.forEach(input => input.addEventListener('change', () => {
            if (input.disabled || input.hidden) return;
            platforms[input.dataset.chatFilterPlatform].forEach(key => {
                if (input.checked) enabled.users.add(key); else enabled.users.delete(key);
            });
            applySelection();
        }));

        inputs.forEach(input => input.addEventListener('change', () => {
            if (input.disabled) return;
            const selection = enabled[input.dataset.chatFilterAxis];
            const key = input.dataset.chatFilterOption;
            if (input.checked) selection.add(key); else selection.delete(key);
            applySelection();
        }));
        function allowsChannel(category) { return channelAllowed({origin, channels}, category); }
        function participants(entries) {
            if (!channelList) return;
            const roster = [{id: 'shared', name: 'Enable shared chat'}, ...entries.filter(entry => String(entry.id) !== control.dataset.channelId)
                .map(entry => ({id: String(entry.id), name: `${entry.name || entry.id}'s Chat`}))];
            const ids = new Set(roster.map(entry => entry.id));
            channelInputs.forEach((input, id) => {
                if (!ids.has(id)) { input.parentElement.remove(); channelInputs.delete(id); }
            });
            roster.forEach(({id, name}) => {
                let input = channelInputs.get(id);
                if (!input) {
                    const row = document.createElement('label');
                    row.className = 'chat-filter-row chat-filter-suboption';
                    input = document.createElement('input'); input.type = 'checkbox';
                    input.dataset.chatFilterChannel = id;
                    const label = document.createElement('span');
                    row.append(input, label); channelList.append(row);
                    channelInputs.set(id, input);
                    input.addEventListener('change', () => {
                        if (id === 'shared') {
                            origin = input.checked ? 'all' : 'local'; channels = {};
                        } else { channels[id] = input.checked; }
                        applySelection();
                    });
                }
                input.parentElement.querySelector('span').textContent = name;
                input.parentElement.title = name;
            });
            sync(); positionDropdown();
        }
        participants([]);
        sync();
        persistSelection();
        if (syncUrl) Promise.resolve().then(loadRemote);
        return {participants, gigantified: () => enabled.types.has('gigantified_emotes'), allows: category => allowsChannel(category) && enabled.users.has(category.user)
            && (category.gigantified ? enabled.types.has('gigantified_emotes') || enabled.types.has('messages') : enabled.types.has(category.type))};
    }
    function channelAllowed(saved, {origin = 'local', channel = 'local'}) {
        if (origin === 'local') return true;
        if (Object.prototype.hasOwnProperty.call(saved.channels || {}, channel)) return saved.channels[channel];
        return !saved.origin || saved.origin === 'all' || saved.origin === origin;
    }

    function attachMirror(onChange) {
        let enabled = null;
        return {
            gigantified: () => !enabled || enabled.types.includes('gigantified_emotes'),
            allows: category => !enabled || channelAllowed(enabled, category) && enabled.users.includes(category.user)
                && (category.gigantified ? enabled.types.includes('gigantified_emotes') || enabled.types.includes('messages') : enabled.types.includes(category.type)),
            update(saved) {
                const types = saved?.types?.length ? migrateTypes(saved.types, saved.version) : messageTypes;
                enabled = saved ? {
                    origin: saved.origin || 'all', channels: saved.channels || {},
                    users: saved.users?.length ? saved.users : (saved.connectedPlatforms || Object.keys(platforms)).flatMap(key => platforms[key] || []),
                    types
                } : null;
                onChange();
            }
        };
    }
    window.dashboardChatFilters = {category, attach, attachMirror, dropdownPosition};
})();
