(() => {
    const tabs = Array.from(document.querySelectorAll("[data-command-tab]"));
    const panels = Array.from(document.querySelectorAll("[data-command-panel]"));

    function selectTab(name) {
        tabs.forEach(tab => {
            const active = tab.dataset.commandTab === name;
            tab.classList.toggle("active", active);
            tab.setAttribute("aria-selected", String(active));
        });
        panels.forEach(panel => {
            panel.hidden = panel.dataset.commandPanel !== name;
        });
    }

    tabs.forEach(tab => tab.addEventListener("click", () => selectTab(tab.dataset.commandTab)));

    let nextSearchId = 0;
    const candidatePools = new Map();
    const pendingWrites = new Set();
    const cachedRequests = new Map();
    function fetchCached(url) {
        if (!cachedRequests.has(url)) {
            const request = fetch(url, {headers: {'Accept': 'application/json'}}).then(async response => ({ok: response.ok, payload: await response.json()}));
            cachedRequests.set(url, request);
            request.finally(() => { if (cachedRequests.get(url) === request) cachedRequests.delete(url); }).catch(() => {});
        }
        return cachedRequests.get(url);
    }
    const pictureRequests = new Map();
    const pictureQueues = new Map();
    function loadPicture(endpoint, id) {
        const key = `${endpoint}:${id}`;
        const cached = pictureRequests.get(key);
        if (cached && cached.expires > Date.now()) return cached.promise;
        let resolve;
        const entry = {promise: new Promise(done => { resolve = done; }), expires: Infinity};
        pictureRequests.set(key, entry);
        if (!pictureQueues.has(endpoint)) pictureQueues.set(endpoint, {ids: new Map(), timer: null});
        const queue = pictureQueues.get(endpoint);
        queue.ids.set(id, {entry, resolve});
        if (queue.timer === null) queue.timer = setTimeout(async () => {
            queue.timer = null;
            const pending = new Map(queue.ids);
            queue.ids.clear();
            const entries = [...pending];
            for (let offset = 0; offset < entries.length; offset += 100) {
                const batch = entries.slice(offset, offset + 100);
                let profiles = new Map();
                let retry = false;
                try {
                    const response = await fetch(`${endpoint}?ids=${encodeURIComponent(batch.map(([id]) => id).join(','))}`, {headers: {'Accept': 'application/json'}});
                    if (!response.ok) throw new Error('Profile pictures unavailable');
                    const payload = await response.json();
                    profiles = new Map(payload.profiles.map(user => [user.id, user.profile_image_url]));
                } catch (_) { retry = true; }
                batch.forEach(([id, {entry, resolve}]) => {
                    const url = profiles.get(id) || '';
                    entry.expires = Date.now() + (url ? 86400000 : retry ? 30000 : 300000);
                    resolve(url);
                });
            }
        }, 0);
        return entry.promise;
    }
    function initializeSearch(searchForm, resultForm) {
        const blacklist = resultForm.hasAttribute('data-user-search-blacklist');
        const local = resultForm.hasAttribute('data-user-search-local');
        const readBlacklist = () => new Set([...document.querySelectorAll('[data-queue-blacklist-members] input[name="username"]')].map(input => input.value.toLocaleLowerCase()));
        let blacklistedNames = blacklist ? readBlacklist() : null;

        const queryInput = searchForm.querySelector('input[name="query"]');
        const message = searchForm.querySelector('[data-protected-search-message]');
        const template = resultForm.cloneNode(true);
        const results = document.createElement('div');
        results.className = 'protected-user-results';
        results.id = `user-search-results-${++nextSearchId}`;
        results.setAttribute('role', 'listbox');
        results.setAttribute('popover', 'auto');
        results.setAttribute('data-overlay-scrollbars', 'off');
        queryInput.setAttribute('role', 'combobox');
        queryInput.setAttribute('aria-autocomplete', 'list');
        queryInput.setAttribute('aria-controls', results.id);
        queryInput.setAttribute('aria-expanded', 'false');
        let selectedId = null;
        let internalClose = false;
        let positionFrame;
        function positionResults() {
            positionFrame = null;
            const rect = queryInput.getBoundingClientRect();
            const width = Math.min(Math.max(searchForm.querySelector('.protected-user-search-controls')?.getBoundingClientRect().width || rect.width, 300), innerWidth - 24);
            const below = innerHeight - rect.bottom - 16;
            const above = rect.top - 16;
            const upwards = below < 180 && above > below;
            Object.assign(results.style, {
                width: `${Math.max(0, width)}px`,
                left: `${Math.max(12, Math.min(rect.left, innerWidth - width - 12))}px`,
                top: upwards ? 'auto' : `${rect.bottom + 6}px`,
                bottom: upwards ? `${innerHeight - rect.top + 6}px` : 'auto',
                maxHeight: `${Math.max(0, Math.min(420, upwards ? above : below))}px`,
            });
        }
        function schedulePosition() {
            if (results.matches(':popover-open') && !positionFrame) positionFrame = requestAnimationFrame(positionResults);
        }
        window.addEventListener('resize', schedulePosition);
        document.addEventListener('scroll', schedulePosition, true);
        new ResizeObserver(schedulePosition).observe(queryInput);
        function selectResult(id) {
            selectedId = null;
            results.querySelectorAll('[data-protected-user-result]').forEach(row => {
                const selected = row.querySelector('[data-protected-result-id]').value === id && !row.querySelector('[data-protected-add]').disabled;
                row.classList.toggle('is-keyboard-selected', selected);
                row.setAttribute('aria-selected', String(selected));
                if (selected) { selectedId = id; queryInput.setAttribute('aria-activedescendant', row.id); }
            });
            if (selectedId === null) queryInput.removeAttribute('aria-activedescendant');
            queryInput.setAttribute('aria-expanded', String(results.childElementCount > 0));
        }
        function showResults(users) {
            results.replaceChildren(...users.map(render));
            selectResult(selectedId);
            if (users.length) {
                positionResults();
                if (!results.matches(':popover-open')) results.showPopover();
            } else hideResults();
        }
        function hideResults() {
            internalClose = true;
            if (results.matches(':popover-open')) results.hidePopover();
            internalClose = false;
            queryInput.setAttribute('aria-expanded', 'false');
        }
        function clearResults() {
            results.replaceChildren();
            selectResult(null);
            hideResults();
        }
        results.addEventListener('beforetoggle', event => {
            if (event.newState === 'closed' && !internalClose) {
                interrupt(); stopCached(); results.replaceChildren(); selectResult(null);
            }
        });
        results.addEventListener('keydown', event => {
            if (event.key === 'Escape') {
                event.preventDefault(); event.stopPropagation(); interrupt(); stopCached(); clearResults(); queryInput.focus();
            }
        });
        resultForm.replaceWith(results);
        let timer;
        let controller;
        let cachedLoading = false;
        let cachedLoaded = false;
        let cachedAt = 0;
        let cacheTimer;
        let cacheRevision = 0;
        let showing = false;
        const cacheKey = 'ratsboombot:protected-user-search:' + (searchForm.closest('[data-settings-book]')?.dataset.channel || searchForm.dataset.searchUrl);
        if (!candidatePools.has(cacheKey)) candidatePools.set(cacheKey, new Map());
        const candidates = candidatePools.get(cacheKey);
        function persistCandidates() {
            if (pendingWrites.has(cacheKey)) return;
            pendingWrites.add(cacheKey);
            queueMicrotask(() => {
                pendingWrites.delete(cacheKey);
                try {
                    const users = [...candidates.values()].filter(user => user.expires > Date.now()).sort((a, b) => b.expires - a.expires).slice(0, 5000);
                    localStorage.setItem(cacheKey, JSON.stringify(users.map(({names, ...user}) => user)));
                } catch (_) {
                    // Storage restrictions must not prevent searching or adding users.
                }
            });
        }
        function remember(users, persist = true) {
            const now = Date.now();
            let changed = false;
            users.forEach(user => {
                const previous = candidates.get(user.id);
                const related = Boolean(user.related || previous?.related);
                const profile_image_url = user.profile_image_url || (previous?.expires > now ? previous.profile_image_url || '' : '');
                const expires = user.expires || (previous?.expires > now ? previous.expires : now + 86400000);
                if (previous && previous.login === user.login && previous.display_name === user.display_name
                    && previous.profile_image_url === profile_image_url && previous.related === related
                    && previous.automatic === user.automatic && previous.already_protected === user.already_protected
                    && previous.expires === expires) return;
                candidates.set(user.id, {...user, related, profile_image_url, expires,
                    names: previous?.login === user.login && previous?.display_name === user.display_name ? previous.names
                        : [...new Set([user.login || '', user.display_name].map(name => name.toLocaleLowerCase()))]});
                changed = true;
            });
            if (persist && changed) persistCandidates();
        }
        try {
            const stored = JSON.parse(localStorage.getItem(cacheKey) || '[]');
            if (Array.isArray(stored)) remember(stored.filter(user => user && user.expires > Date.now()
                && typeof user.id === 'string' && typeof user.login === 'string' && typeof user.display_name === 'string'), false);
        } catch (_) {}

        function similarity(a, b) {
            if (a === b) return 1;
            const row = Array.from({length: b.length + 1}, (_, index) => index);
            for (let i = 1; i <= a.length; i++) {
                let previous = row[0]; row[0] = i;
                for (let j = 1; j <= b.length; j++) {
                    const old = row[j];
                    row[j] = Math.min(row[j] + 1, row[j - 1] + 1, previous + (a[i - 1] === b[j - 1] ? 0 : 1));
                    previous = old;
                }
            }
            return 1 - row[b.length] / Math.max(a.length, b.length, 1);
        }
        function rankedUsers(retainedIds = null) {
            const query = normalizedQuery();
            const related = [], remote = [];
            const now = Date.now();
            const compare = (a, b) => a.type - b.type || b.score - a.score || a.user.login.localeCompare(b.user.login);
            for (const user of candidates.values()) {
                if (user.expires <= now || (!user.related && !retainedIds?.has(user.id))) continue;
                const ranked = user.related ? related : remote;
                let type = 3;
                for (const name of user.names) {
                    type = Math.min(type, name === query ? 0 : name.startsWith(query) ? 1 : name.includes(query) ? 2 : 3);
                    if (type === 0) break;
                }
                const last = ranked[4];
                if (last && type > last.type) continue;
                let score = type === 0 ? 1 : 0;
                if (type !== 0) for (const name of user.names) score = Math.max(score, similarity(query, name));
                const item = {user, type, score};
                if (type === 3 && score < 0.6 && !retainedIds?.has(user.id)) continue;
                let index = 0;
                while (index < ranked.length && compare(item, ranked[index]) >= 0) index++;
                if (index < 5) { ranked.splice(index, 0, item); if (ranked.length > 5) ranked.pop(); }
            }
            return [...related, ...remote].map(item => item.user);
        }
        function showCached() {
            const query = normalizedQuery();
            if (!showing || selectedId !== null || !/^[a-z0-9_]{1,25}$/.test(query)) return;
            showResults(rankedUsers(remoteStarted ? remoteMatches : null));
        }
        async function loadCached(force = false) {
            if (cachedLoading || (cachedLoaded && !force)) return;
            clearTimeout(cacheTimer);
            cachedLoading = true;
            const current = ++cacheRevision;
            try {
                const {ok, payload} = await fetchCached(`${searchForm.dataset.searchUrl}?query=&cached_only=true`);
                if (current !== cacheRevision || !ok) return;
                remember(payload.users.map(user => ({...user, related: true})));
                cachedLoaded = true;
                cachedAt = Date.now();
                showCached();
                if (payload.followers_loading) cacheTimer = setTimeout(() => loadCached(true), 1000);
            } catch (_) {
                // The explicit Twitch search remains available when cache loading fails.
            } finally {
                if (current === cacheRevision) cachedLoading = false;
            }
        }
        function stopCached() {
            clearTimeout(cacheTimer);
            cacheRevision++;
            cachedLoading = false;
        }
        let remoteStarted = false;
        let remoteMatches = null;
        let revision = 0;
        let pendingQuery;
        let lastQuery;
        const normalizedQuery = () => queryInput.value.trim().replace(/^@/, '').toLocaleLowerCase();

        function render(user) {
            const form = template.cloneNode(true);
            form.hidden = false;
            form.id = `${results.id}-${user.id}`;
            form.setAttribute('role', 'option');
            const avatar = form.querySelector('[data-protected-result-avatar]');
            if (avatar) {
                avatar.hidden = !user.profile_image_url;
                if (user.profile_image_url) avatar.src = user.profile_image_url;
                else avatar.removeAttribute('src');
            }
            if (avatar && !user.profile_image_url && /^[0-9]{1,25}$/.test(user.id)) {
                const endpoint = searchForm.dataset.searchUrl.replace(/\/search$/, '/profiles');
                loadPicture(endpoint, user.id).then(url => {
                    if (!url) return;
                    const cached = candidates.get(user.id);
                    if (cached && cached.profile_image_url !== url) {
                        cached.profile_image_url = url;
                        cached.expires = Date.now() + 86400000;
                        persistCandidates();
                    }
                    // Update only the image; keep the name, row, and action in place.
                    if (form.isConnected) { avatar.src = url; avatar.hidden = false; }
                });
            }
            form.querySelector('[data-protected-result-id]').value = user.id;
            const login = user.login || '';
            const loginInput = form.querySelector('[data-protected-result-login]');
            if (loginInput) loginInput.value = login;
            form.querySelector('[data-protected-result-label]').textContent = login && user.display_name.toLocaleLowerCase() !== login.toLocaleLowerCase()
                ? `${user.display_name} (${login})` : user.display_name;
            const id = form.querySelector('[data-protected-result-user-id]');
            if (id) id.textContent = user.id;
            const button = form.querySelector('[data-protected-add]');
            const existing = local ? (searchForm.closest('[data-shoutout-user-list]').querySelector('[data-shoutout-list-value]').value.split(/\s+/).includes(login.toLowerCase()))
                : blacklist ? blacklistedNames.has(login.toLocaleLowerCase()) : user.already_protected;
            button.disabled = existing;
            form.setAttribute('aria-disabled', String(Boolean(existing)));
            button.textContent = local ? existing ? 'Already added' : 'Add User'
                : blacklist ? existing ? 'Already blacklisted' : 'Blacklist' : existing ? 'Already Protected' : 'Add User';
            if (local) form.addEventListener('submit', event => {
                event.preventDefault(); event.stopPropagation();
                interrupt(); stopCached(); clearResults(); queryInput.value = ''; message.textContent = '';
                searchForm.dispatchEvent(new CustomEvent('user-search-selected', {bubbles: true, detail: {...user, profile_image_url: candidates.get(user.id)?.profile_image_url || user.profile_image_url}}));
            });
            return form;
        }

        searchForm.closest('[data-settings-book]')?.addEventListener('settings-save-failed', event => {
            if (!results.contains(event.detail.form)) return;
            showing = true;
            positionResults();
            if (!results.matches(':popover-open')) results.showPopover();
            queryInput.setAttribute('aria-expanded', 'true');
        });

        searchForm.closest('[data-settings-book]')?.addEventListener('settings-saved', event => {
            const kind = event.detail.form.dataset.settingsImmediateAction;
            if (blacklist ? kind !== 'queue-blacklist' : kind !== 'protected-users') return;
            const saved = new Map(JSON.parse(event.detail.snapshot));
            if (blacklist) blacklistedNames = readBlacklist();
            else {
                const user = candidates.get(saved.get('user_id'));
                if (user) {
                    user.already_protected = event.detail.form.getAttribute('action').endsWith('/add');
                    persistCandidates();
                }
            }
            results.querySelectorAll('[data-protected-user-result]').forEach(form => {
                const matches = blacklist ? form.querySelector('[data-protected-result-login]').value === saved.get('username') : form.querySelector('[data-protected-result-id]').value === saved.get('user_id');
                if (matches) form.remove();
            });
            selectResult(selectedId);
            if (!results.childElementCount) hideResults();
            message.textContent = '';
        });

        async function lookup() {
            clearTimeout(timer);
            const query = normalizedQuery();
            if (!/^[a-z0-9_]{2,25}$/.test(query)) {
                message.textContent = query ? 'Enter at least two characters of a Twitch username.' : '';
                return;
            }
            if (pendingQuery === query) return;
            const request = new AbortController();
            controller?.abort();
            controller = request;
            pendingQuery = query;
            remoteStarted = true;
            showing = true;
            message.textContent = 'Searching Twitch...';
            const current = revision;
            try {
                const response = await fetch(`${searchForm.dataset.searchUrl}?query=${encodeURIComponent(query)}`, {
                    headers: {'Accept': 'application/json'}, signal: request.signal,
                });
                const payload = await response.json();
                if (current !== revision) return;
                if (!response.ok) throw new Error(payload.detail || 'Twitch user lookup failed.');
                const users = payload.users.slice(0, 10);
                remember(users);
                remoteMatches = new Set(users.map(user => user.id));
                const merged = rankedUsers(remoteMatches);
                showResults(merged);
                message.textContent = merged.length ? '' : 'No matching users.';
            } catch (error) {
                if (current === revision && error.name !== 'AbortError') message.textContent = error.message || 'Twitch user lookup failed.';
            } finally {
                if (current === revision) pendingQuery = null;
            }
        }
        function cancelLookup() {
            clearTimeout(timer);
            controller?.abort();
            controller = null;
            revision++;
            pendingQuery = null;
        }
        function interrupt(clearMessage = true) {
            cancelLookup();
            showing = false;
            remoteStarted = false;
            remoteMatches = null;
            selectResult(null);
            if (clearMessage) message.textContent = '';
        }
        function schedule() {
            const query = normalizedQuery();
            // Casing, an @ prefix, and surrounding spaces do not change the search.
            if (showing && query === lastQuery) return;
            lastQuery = query;
            const starting = !showing;
            interrupt();
            clearResults();
            showing = true;
            showCached();
            loadCached(starting || Date.now() - cachedAt >= 30000);
            if (/^[a-z0-9_]{2,25}$/.test(query)) timer = setTimeout(lookup, 1000);
        }
        document.addEventListener('pointerdown', event => {
            const add = event.target.closest('[data-protected-add]');
            if (add && results.contains(add) && !add.disabled) {
                // Keep the button in place until click/release completes.
                interrupt(false);
                stopCached();
                const stopped = revision;
                document.addEventListener('pointerup', () => setTimeout(() => {
                    if (revision === stopped) message.textContent = '';
                }, 0), {once: true});
            }
            else if (!searchForm.contains(event.target) && !results.contains(event.target)) {
                interrupt(false);
                stopCached();
            }
        }, true);
        document.addEventListener('click', event => {
            if (!searchForm.contains(event.target) && !results.contains(event.target)) {
                message.textContent = '';
                clearResults();
            }
        });
        // Keyboard submissions must cancel the lookup too, without removing the
        // chosen form before the save handler reads it.
        results.addEventListener('submit', event => { if (!event.defaultPrevented) { interrupt(); stopCached(); hideResults(); } });
        queryInput.addEventListener('keydown', event => {
            if (event.isComposing) return;
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                const options = [...results.children].filter(row => !row.querySelector('[data-protected-add]').disabled);
                if (!options.length) return;
                event.preventDefault();
                cancelLookup();
                remoteStarted = true;
                stopCached();
                message.textContent = '';
                const index = options.findIndex(row => row.querySelector('[data-protected-result-id]').value === selectedId);
                const next = index < 0 ? event.key === 'ArrowDown' ? 0 : options.length - 1
                    : (index + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length;
                selectResult(options[next].querySelector('[data-protected-result-id]').value);
                options[next].scrollIntoView({block: 'nearest'});
            } else if (event.key === 'Enter' && selectedId !== null) {
                event.preventDefault();
                if (!event.repeat) results.querySelector('.is-keyboard-selected [data-protected-add]')?.click();
            } else if (event.key === 'Escape') {
                event.preventDefault(); event.stopPropagation();
                interrupt(); stopCached(); clearResults();
            }
        });
        queryInput.addEventListener('input', event => { if (!event.isComposing) schedule(); });
        queryInput.addEventListener('compositionend', schedule);
        searchForm.addEventListener('submit', event => { event.preventDefault(); lookup(); });
        window.addEventListener('pagehide', () => { interrupt(); stopCached(); }, {once: true});
        loadCached();
    }
    document.querySelectorAll('[data-protected-user-search]').forEach(form => {
        const result = form.nextElementSibling;
        if (result?.matches('[data-protected-user-result]')) initializeSearch(form, result);
    });
})();
