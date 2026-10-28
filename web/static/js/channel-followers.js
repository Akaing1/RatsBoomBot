(() => {
    const root = document.querySelector('[data-followers]');
    if (!root) return;
    const form = root.querySelector('[data-followers-controls]'), body = root.querySelector('[data-followers-rows]');
    const status = root.querySelector('[data-followers-status]'), warning = root.querySelector('[data-followers-warning]');
    const prev = root.querySelector('[data-followers-prev]'), next = root.querySelector('[data-followers-next]');
    const refresh = root.querySelector('[data-followers-refresh]');
    const rolesMenu = root.querySelector('.followers-roles-menu');
    function syncRoleCount() {
        const count = rolesMenu.querySelectorAll('input:checked').length;
        rolesMenu.querySelector('[data-followers-role-count]').textContent = count ? `(${count})` : '';
    }
    function closeRolesOutside(event) { if (!rolesMenu.contains(event.target)) rolesMenu.open = false; }
    document.addEventListener('pointerdown', closeRolesOutside);
    rolesMenu.addEventListener('keydown', event => {
        if (event.key === 'Escape' && rolesMenu.open) { event.preventDefault(); rolesMenu.open = false; rolesMenu.querySelector('summary').focus(); }
    });
    rolesMenu.addEventListener('change', syncRoleCount);
    syncRoleCount();
    const expanded = new Set();
    const panel = root.querySelector('.followers-table-wrap'), table = panel.querySelector('table');
    let columnCount, botColumns = false, switchingColumns = false, slideFrame = 0, sizedWidth = 0, snapTimer, draggingColumns = false, pendingHash = false;
    const favoriteKey = `ratsboombot:raid-favorites:${root.dataset.channelId}`;
    let favorites = new Set();
    function readFavorites() {
        try { const saved = JSON.parse(localStorage.getItem(favoriteKey) || '[]'); favorites = new Set(Array.isArray(saved) ? saved.filter(id => typeof id === 'string' && /^\d{1,25}$/.test(id)).slice(0, 100) : []); } catch (_) { favorites = new Set(); }
    }
    readFavorites();
    let pendingFavorite = null;
    function closeFavoriteConfirmation(event) {
        if (pendingFavorite === null) return;
        if (event && event.target.closest('.follower-favorite-action')?.dataset.userId === pendingFavorite) return;
        pendingFavorite = null;
        for (const action of body.querySelectorAll('.follower-favorite-action.is-confirming')) {
            action.classList.remove('is-confirming');
            const button = action.querySelector('.follower-favorite-remove'); button.disabled = true; button.tabIndex = -1;
        }
    }
    document.addEventListener('pointerdown', closeFavoriteConfirmation);
    const standardColumns = [['name', 'Name'], ['raid_favorite', '★'], ['roles', 'Roles'], ['messages', 'Messages'], ['followed_at', 'Following Since'], ['last_seen', 'Last Active']];
    const extraColumns = [
        ['first_redeems', 'First redeems'], ['check_ins', 'Check-ins'],
        ['achievement_count', 'Achievements', 'Unique achievements unlocked in this channel.'],
        ['points', 'Current points'], ['lifetime_points', 'Points earned'],
        ['points_spent', 'Points spent', 'Historical spending totals are not recorded.'],
        ['watch_minutes', 'Watch time', 'Estimated from live chat presence samples.'],
    ];
    const sortableColumns = new Set([...standardColumns, ...extraColumns].map(([key]) => key));
    function writeLocation() {
        const url = new URL(location.href);
        url.hash = new URLSearchParams({columns: botColumns ? 'bot' : 'standard', sort: form.elements.sort.value, direction: form.elements.direction.value}).toString();
        if (url.href !== location.href) history.pushState(history.state, '', url);
    }
    async function restoreLocation(initial = false) {
        if (switchingColumns) { pendingHash = true; return; }
        const params = new URLSearchParams(location.hash.slice(1));
        const sort = sortableColumns.has(params.get('sort')) ? params.get('sort') : 'followed_at';
        const direction = params.get('direction') === 'asc' ? 'asc' : 'desc';
        const showBot = params.get('columns') === 'bot';
        const changedSort = sort !== form.elements.sort.value || direction !== form.elements.direction.value;
        form.elements.sort.value = sort; form.elements.direction.value = direction;
        if (initial) { botColumns = showBot; return; }
        if (showBot !== botColumns) await switchColumns(showBot, false, false);
        if (changedSort && !stopped) { clearTimeout(debounce); page = 1; load(); }
    }
    function onHashChange() { restoreLocation(); }
    window.addEventListener('hashchange', onHashChange);
    function buildColumns() {
        const columns = [...standardColumns, ['next', ''], ['back', ''], ...extraColumns];
        columnCount = columns.length;
        const header = table.tHead.rows[0], group = table.querySelector('colgroup');
        header.replaceChildren(); group.replaceChildren();
        for (const [key, label] of columns) {
            const col = document.createElement('col');
            col.dataset.fraction = key === 'name' ? '28' : key === 'raid_favorite' ? '6' : ['next', 'back'].includes(key) ? '4' : standardColumns.some(([id]) => id === key) ? '15.5' : String(62 / 7);
            group.append(col);
            const th = document.createElement('th'); th.scope = 'col';
            if (['next', 'back'].includes(key)) {
                th.className = 'followers-switch-header';
                const button = document.createElement('button'), arrow = document.createElement('span');
                button.type = 'button'; button.className = 'followers-columns-toggle'; button.dataset.followersView = key === 'next' ? 'bot' : 'standard';
                button.setAttribute('aria-label', key === 'next' ? 'Show RatsBoomBot columns' : 'Show standard columns'); button.title = key === 'next' ? 'RatsBoomBot columns' : 'Standard columns';
                arrow.dataset.followersColumnsArrow = ''; arrow.setAttribute('aria-hidden', 'true'); arrow.textContent = key === 'next' ? '›' : '‹';
                button.append(arrow); th.append(button); header.append(th); continue;
            }
            th.dataset.followersColumn = key;
            const button = document.createElement('button'), icon = document.createElement('span');
            button.type = 'button'; button.dataset.followersSort = key; button.append(document.createTextNode(label));
            if (key === 'raid_favorite') button.dataset.sortLabel = 'Raid favorites';
            icon.setAttribute('aria-hidden', 'true'); icon.textContent = '↕'; button.append(icon); th.append(button);
            header.append(th);
        }
        syncColumnView(); sizeColumns();
    }
    function syncColumnView() {
        table.dataset.columns = panel.dataset.columns = botColumns ? 'bot' : 'standard';
        for (const button of table.querySelectorAll('[data-followers-view]')) {
            button.toggleAttribute('data-followers-columns', button.dataset.followersView !== (botColumns ? 'bot' : 'standard'));
            button.disabled = switchingColumns;
        }
    }
    function columnViewWidth() { return Math.max(1080, panel.clientWidth); }
    function sizeColumns() {
        const width = columnViewWidth();
        if (width === sizedWidth) return;
        sizedWidth = width; table.style.width = `${width * 1.66}px`;
        table.style.setProperty('--followers-view-width', `${width}px`);
        table.style.setProperty('--followers-name-width', `${width * .28}px`);
        for (const col of table.querySelectorAll('col')) col.style.width = `${width * Number(col.dataset.fraction) / 100}px`;
        if (!switchingColumns) panel.scrollLeft = botColumns ? width * .66 : 0;
    }
    async function switchColumns(showBot, focus = false, updateLocation = true) {
        if (switchingColumns) return;
        clearTimeout(snapTimer);
        switchingColumns = true;
        botColumns = showBot; syncColumnView();
        if (updateLocation) writeLocation();
        try {
            const from = panel.scrollLeft, to = botColumns ? columnViewWidth() * .66 : 0;
            if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) panel.scrollLeft = to;
            else await new Promise(resolve => {
                const start = performance.now();
                function step(now) {
                    const progress = Math.min(1, (now - start) / 320), eased = progress * progress * (3 - 2 * progress);
                    panel.scrollLeft = from + (to - from) * eased;
                    if (progress < 1 && !stopped) slideFrame = requestAnimationFrame(step); else resolve();
                }
                slideFrame = requestAnimationFrame(step);
            });
        } finally {
            switchingColumns = false; syncColumnView();
            if (focus && !stopped) table.querySelector('[data-followers-columns]').focus({preventScroll: true});
            if (pendingHash && !stopped) { pendingHash = false; restoreLocation(); }
        }
    }
    panel.addEventListener('click', event => {
        const button = event.target.closest('[data-followers-view]');
        if (button) switchColumns(button.dataset.followersView === 'bot', true);
    });
    function scheduleColumnSnap() {
        clearTimeout(snapTimer);
        if (switchingColumns || draggingColumns || stopped) return;
        snapTimer = setTimeout(() => {
            const right = columnViewWidth() * .66, showBot = panel.scrollLeft >= right / 2;
            if (Math.abs(panel.scrollLeft - (showBot ? right : 0)) > 1 || botColumns !== showBot) switchColumns(showBot);
        }, 150);
    }
    panel.addEventListener('scroll', scheduleColumnSnap, {passive: true});
    panel.addEventListener('pointerdown', () => { draggingColumns = true; clearTimeout(snapTimer); });
    function endColumnDrag() { if (draggingColumns) { draggingColumns = false; scheduleColumnSnap(); } }
    document.addEventListener('pointerup', endColumnDrag);
    document.addEventListener('pointercancel', endColumnDrag);
    const rendered = new Map(), heights = new Map(), images = new Map(), imageQueue = new Set(), imageRetry = new Map();
    let rows = [], rowsSignature = '', renderDay = '', offsets = [0], page = 1, controller, timer, debounce, sequence = 0, frame = 0, windowDirty = true;
    let imageTimer, imageController, imageBusy = false, stopped = false;
    const avatarObserver = new IntersectionObserver(entries => {
        for (const entry of entries) if (entry.isIntersecting) {
            avatarObserver.unobserve(entry.target);
            imageQueue.add(entry.target.dataset.followerAvatar);
        }
        if (imageQueue.size) { clearTimeout(imageTimer); imageTimer = setTimeout(loadImages, 50); }
    }, {rootMargin: '120px'});
    function applyImage(img, url) {
        if (!url || img.getAttribute('src') === url) return;
        try { if (new URL(url).protocol === 'https:') img.src = url; } catch (_) {}
    }
    async function loadImages() {
        if (imageBusy || stopped) return;
        const mounted = new Set([...body.querySelectorAll('[data-follower-avatar]')].map(img => img.dataset.followerAvatar));
        const ids = [...imageQueue].filter(id => mounted.has(id) && !images.has(id) && (imageRetry.get(id) || 0) <= Date.now()).slice(0, 100);
        imageQueue.clear();
        if (!ids.length) return;
        imageBusy = true; imageController = new AbortController();
        try {
            const response = await fetch(`/channel/api/followers/profiles?${new URLSearchParams({ids: ids.join(',')})}`, {signal: imageController.signal, headers: {Accept: 'application/json'}});
            if (!response.ok) throw new Error('Profile pictures unavailable');
            const data = await response.json();
            const found = new Map((data.profiles || []).map(item => [item.id, item.profile_image_url]));
            for (const id of ids) images.set(id, found.get(id) || '');
            const requested = new Set(ids);
            for (const img of body.querySelectorAll('[data-follower-avatar]')) if (requested.has(img.dataset.followerAvatar)) applyImage(img, images.get(img.dataset.followerAvatar));
        } catch (error) { if (error.name !== 'AbortError') for (const id of ids) imageRetry.set(id, Date.now() + 30_000); }
        finally { imageBusy = false; if (imageQueue.size && !stopped) imageTimer = setTimeout(loadImages, 50); }
    }
    function scheduleRender() { if (!frame && !stopped) frame = requestAnimationFrame(() => { frame = 0; renderWindow(); }); }
    function rebuildOffsets() {
        windowDirty = true;
        offsets = [0]; let extraRows = 0;
        rows.forEach((item, index) => {
            const measured = heights.get(item.user_id) || {};
            offsets.push(offsets[index] + (measured.row || 68) + (expanded.has(item.user_id) ? measured.details || 170 : 0));
            const pair = rendered.get(index);
            if (pair) { pair.row.setAttribute('aria-rowindex', String(index + extraRows + 2)); pair.details.setAttribute('aria-rowindex', String(index + extraRows + 3)); }
            if (expanded.has(item.user_id)) extraRows++;
        });
        table.setAttribute('aria-rowcount', String(rows.length + extraRows + 1));
    }
    function indexAt(position) {
        let index = 0;
        while (index < rows.length - 1 && offsets[index + 1] <= position) index++;
        return index;
    }
    const rowObserver = new ResizeObserver(entries => {
        const top = body.getBoundingClientRect().top;
        const anchor = indexAt(Math.max(0, -top)), previous = offsets[anchor] || 0;
        let changed = false;
        for (const entry of entries) {
            const node = entry.target, item = rows[Number(node.dataset.followerIndex)];
            if (!item || !node.isConnected || node.hidden) continue;
            const height = entry.borderBoxSize?.[0]?.blockSize || entry.contentRect.height, key = node.classList.contains('follower-details') ? 'details' : 'row';
            const measured = heights.get(item.user_id) || {};
            if (height > 0 && Math.abs((measured[key] || 0) - height) > .5) { measured[key] = height; heights.set(item.user_id, measured); changed = true; }
        }
        if (changed) {
            rebuildOffsets();
            const delta = (offsets[anchor] || 0) - previous;
            if (top < 0 && delta) window.scrollBy({top: delta, behavior: 'instant'});
            scheduleRender();
        }
    });
    const numberFormat = new Intl.NumberFormat();
    const number = value => numberFormat.format(Number(value || 0));
    const watchTime = value => `${number(Math.floor((value || 0) / 60))}h ${number((value || 0) % 60)}m`;
    function statValue(item, key, expanded = false) {
        if (key === 'watch_minutes') return watchTime(item[key]);
        if (key === 'points_spent' && item[key] == null) return expanded ? 'Not recorded' : '—';
        return number(item[key]);
    }
    const dateCache = new Map();
    function date(value, dateOnly = false) {
        if (!value) return '—';
        const key = `${dateOnly}:${value}`;
        if (dateCache.has(key)) return dateCache.get(key);
        const parsed = new Date(/Z$|[+-]\d\d:\d\d$/.test(value) ? value : value.replace(' ', 'T') + 'Z');
        const text = Number.isNaN(parsed.getTime()) ? '—' : dateOnly ? parsed.toLocaleDateString() : parsed.toLocaleString();
        if (dateCache.size >= 256) dateCache.delete(dateCache.keys().next().value);
        dateCache.set(key, text);
        return text;
    }
    function cell(row, text) { const node = document.createElement('td'); node.textContent = text; if (text === '—') node.className = 'follower-empty'; row.append(node); return node; }
    function roleTags(item) {
        const group = document.createElement('div'); group.className = 'follower-roles';
        const labels = item.role_labels || [];
        for (const label of labels) { const tag = document.createElement('span'); tag.className = 'follower-role-tag'; tag.textContent = label; group.append(tag); }
        if (!labels.length) { group.textContent = '—'; group.classList.add('is-empty'); }
        return group;
    }
    function ensureDetails(item, details) {
        if (details.firstChild) return;
        const detailCell = cell(details, ''); detailCell.colSpan = columnCount;
        const list = document.createElement('dl');
        const pairs = [...extraColumns.map(([key, label, tooltip]) => [label, statValue(item, key, true), tooltip]),
            ['First seen in channel', date(item.first_seen)], ['Last active in channel', date(item.last_seen)], ['Twitch user ID', item.user_id]];
        for (const [title, value, tooltip] of pairs) {
            const group = document.createElement('div'), term = document.createElement('dt'), description = document.createElement('dd');
            term.textContent = title; description.textContent = value;
            if (tooltip) description.title = tooltip;
            group.append(term, description); list.append(group);
        }
        const roleGroup = document.createElement('div'), roleTitle = document.createElement('dt'), roleValue = document.createElement('dd');
        roleTitle.textContent = 'Roles'; roleValue.append(roleTags(item)); roleGroup.append(roleTitle, roleValue); list.append(roleGroup);
        const heading = document.createElement('h4'); heading.className = 'follower-stats-heading'; heading.textContent = 'RatsBoomBot stats';
        const content = document.createElement('div'); content.className = 'follower-detail-content'; content.append(heading, list); detailCell.append(content);
    }
    function syncSortHeaders() {
        root.querySelectorAll('[data-followers-sort]').forEach(button => {
            const selected = button.dataset.followersSort === form.elements.sort.value;
            const ascending = form.elements.direction.value === 'asc';
            button.closest('th').setAttribute('aria-sort', selected ? ascending ? 'ascending' : 'descending' : 'none');
            button.querySelector('span').textContent = selected ? ascending ? '▲' : '▼' : '↕';
            const label = button.dataset.sortLabel || button.firstChild.textContent.trim();
            const nextAscending = selected ? !ascending : ['name', 'label'].includes(button.dataset.followersSort);
            button.setAttribute('aria-label', `${label}: sort ${nextAscending ? 'ascending' : 'descending'}`);
        });
    }
    function createRow(item, index) {
            const row = document.createElement('tr'), details = document.createElement('tr');
            row.dataset.followerIndex = details.dataset.followerIndex = String(index);
            details.className = 'follower-details'; details.id = `follower-${item.user_id}`; details.hidden = !expanded.has(item.user_id);
            const person = document.createElement('div'); person.className = 'follower-person';
            const toggle = document.createElement('button'); toggle.className = 'follower-expand'; toggle.type = 'button';
            toggle.setAttribute('aria-label', `Details for ${item.login || item.name}`);
            const name = document.createElement('a'); name.className = 'follower-name';
            name.href = `https://www.twitch.tv/${encodeURIComponent(item.login || item.name)}`;
            name.target = '_blank'; name.rel = 'noopener noreferrer';
            const avatar = document.createElement('span'); avatar.className = 'follower-avatar'; avatar.dataset.initial = [...item.name][0] || '?'; avatar.setAttribute('aria-hidden', 'true');
            const img = document.createElement('img'); img.width = img.height = 34; img.alt = ''; img.loading = 'lazy'; img.decoding = 'async'; img.dataset.followerAvatar = item.user_id;
            avatar.append(img);
            const username = item.login || '', displayName = item.name || username;
            const text = document.createElement('span'); text.className = 'follower-person-text';
            text.textContent = username && displayName.toLowerCase() !== username.toLowerCase() ? `${displayName} (${username})` : username || displayName;
            toggle.setAttribute('aria-expanded', String(!details.hidden)); toggle.setAttribute('aria-controls', details.id);
            name.append(text);
            person.append(toggle, avatar, name); cell(row, '').append(person);
            const favorite = document.createElement('button'); favorite.type = 'button'; favorite.className = 'follower-favorite';
            favorite.textContent = favorites.has(item.user_id) ? '★' : '☆';
            favorite.setAttribute('aria-label', `Raid favorite: ${item.login || item.name}`);
            favorite.setAttribute('aria-pressed', String(favorites.has(item.user_id)));
            const action = document.createElement('div'), strip = document.createElement('div'), remove = document.createElement('button');
            action.className = 'follower-favorite-action'; action.dataset.userId = item.user_id; strip.className = 'follower-favorite-strip';
            remove.type = 'button'; remove.className = 'follower-favorite-remove'; remove.textContent = '×'; remove.disabled = true; remove.tabIndex = -1;
            remove.title = 'Are you sure you want to remove this raid favorite?'; remove.setAttribute('aria-label', `Confirm removing ${item.login || item.name} from raid favorites`);
            strip.append(favorite, remove); action.append(strip);
            cell(row, '').className = 'follower-favorite-cell'; row.lastElementChild.append(action);
            cell(row, '').append(roleTags(item));
            cell(row, number(item.messages)).className = 'follower-number';
            const followed = cell(row, date(item.followed_at, true));
            followed.classList.add('follower-date');
            if (followed.textContent !== '—') {
                const days = Math.max(0, Math.floor((Date.now() - new Date(item.followed_at).getTime()) / 86_400_000));
                followed.title = `${date(item.followed_at)}\nFollowing for ${days ? `${number(days)} ${days === 1 ? 'day' : 'days'}` : 'less than a day'}`;
            }
            const lastSeen = cell(row, date(item.last_seen, true));
            lastSeen.classList.add('follower-date');
            if (lastSeen.textContent !== '—') lastSeen.title = date(item.last_seen);
            cell(row, '').className = 'follower-switch-cell';
            cell(row, '').className = 'follower-switch-cell';
            for (const [key, , tooltip] of extraColumns) {
                const metric = cell(row, statValue(item, key)); metric.classList.add('follower-number');
                if (tooltip) metric.title = tooltip;
            }
            if (!details.hidden) ensureDetails(item, details);
            if (images.has(item.user_id)) applyImage(img, images.get(item.user_id)); else avatarObserver.observe(img);
            rowObserver.observe(row); rowObserver.observe(details);
            return {row, details, signature: renderDay + JSON.stringify(item)};
    }
    function spacer(height) {
        const row = document.createElement('tr'); row.className = 'follower-spacer'; row.setAttribute('aria-hidden', 'true'); row.setAttribute('role', 'presentation');
        const td = cell(row, ''); td.colSpan = columnCount; td.style.height = `${Math.max(0, height)}px`; return row;
    }
    function renderWindow() {
        const bodyTop = body.getBoundingClientRect().top;
        const top = Math.max(0, -bodyTop), bottom = Math.max(0, window.innerHeight - bodyTop);
        const start = Math.max(0, indexAt(top) - 3), end = Math.min(rows.length, indexAt(bottom) + 4);
        const indices = new Set(Array.from({length: Math.max(0, end - start)}, (_, index) => start + index));
        const focused = document.activeElement.closest?.('[data-follower-index]');
        if (focused && body.contains(focused)) indices.add(Number(focused.dataset.followerIndex));
        if (!windowDirty && indices.size === rendered.size && [...indices].every(index => rendered.has(index))) return;
        for (const [index, pair] of rendered) if (!indices.has(index)) {
            rowObserver.unobserve(pair.row); rowObserver.unobserve(pair.details); avatarObserver.unobserve(pair.row.querySelector('img'));
            pair.row.remove(); pair.details.remove(); rendered.delete(index);
        }
        const desired = []; let previous = 0;
        for (const index of [...indices].sort((a, b) => a - b)) {
            if (index >= rows.length) continue;
            if (offsets[index] > previous) desired.push(spacer(offsets[index] - previous));
            if (!rendered.has(index)) rendered.set(index, createRow(rows[index], index));
            const pair = rendered.get(index); desired.push(pair.row, pair.details); previous = offsets[index + 1];
        }
        if (offsets[rows.length] > previous) desired.push(spacer(offsets[rows.length] - previous));
        if (!rows.length) { const row = document.createElement('tr'); cell(row, 'No followers to display.').colSpan = columnCount; desired.push(row); }
        const keep = new Set(desired);
        for (const node of [...body.children]) if (!keep.has(node)) node.remove();
        desired.forEach((node, index) => { if (body.children[index] !== node) body.insertBefore(node, body.children[index] || null); });
        rebuildOffsets();
        windowDirty = false;
    }
    function render(nextRows) {
        closeFavoriteConfirmation();
        renderDay = new Date().toDateString();
        const signature = renderDay + JSON.stringify(nextRows);
        if (signature === rowsSignature) return;
        rowsSignature = signature;
        const same = rows.length === nextRows.length && rows.every((item, index) => item.user_id === nextRows[index].user_id);
        if (same) {
            for (const [index, pair] of rendered) {
                if (pair.signature === renderDay + JSON.stringify(nextRows[index])) continue;
                rowObserver.unobserve(pair.row); rowObserver.unobserve(pair.details); avatarObserver.unobserve(pair.row.querySelector('img'));
                pair.row.remove(); pair.details.remove(); rendered.delete(index);
            }
            rows = nextRows; rebuildOffsets(); renderWindow();
            return;
        }
        rowObserver.disconnect(); avatarObserver.disconnect(); rendered.clear(); body.replaceChildren();
        rows = nextRows; body.dataset.totalRows = String(rows.length); rebuildOffsets();
        if (panel.getBoundingClientRect().top < 0) window.scrollTo({top: window.scrollY + panel.getBoundingClientRect().top, behavior: 'instant'});
        renderWindow();
    }
    async function load(force = false) {
        clearTimeout(timer); controller?.abort(); controller = new AbortController();
        const request = ++sequence;
        syncSortHeaders();
        prev.disabled = next.disabled = true; refresh.disabled = true; root.setAttribute('aria-busy', 'true');
        const params = new URLSearchParams(new FormData(form)); params.set('page', String(page));
        if (favorites.size && (form.elements.raid_favorites.checked || form.elements.sort.value === 'raid_favorite')) params.set('favorites', [...favorites].join(','));
        if (force) params.set('refresh', 'true');
        try {
            const response = await fetch(`/channel/api/followers?${params}`, {signal: controller.signal, cache: 'no-store', headers: {Accept: 'application/json'}});
            const data = await response.json();
            if (request !== sequence) return;
            if (!response.ok) throw new Error(data.detail || 'Followers could not be loaded.');
            page = data.page; render(data.rows);
            status.textContent = data.loading ? data.total > 0 && data.loaded >= data.total ? 'Loading follower details…' : `Loading followers… ${number(data.loaded)} of ${number(data.total)}` : `${number(data.count)} matching followers · ${number(data.total)} total`;
            warning.textContent = [data.error, ...(data.warnings || [])].filter(Boolean).join(' '); warning.hidden = !warning.textContent;
            root.querySelector('[data-followers-page]').textContent = `Page ${page} of ${data.pages}`;
            prev.disabled = page <= 1; next.disabled = page >= data.pages;
            if (data.loading) timer = setTimeout(() => load(), 1500);
        } catch (error) {
            if (error.name === 'AbortError' || request !== sequence) return;
            status.textContent = 'Unable to update the follower list.'; warning.textContent = error.message; warning.hidden = false;
        } finally { if (request === sequence) { refresh.disabled = false; root.removeAttribute('aria-busy'); } }
    }
    form.addEventListener('submit', event => event.preventDefault());
    table.tHead.addEventListener('click', event => {
        const button = event.target.closest('[data-followers-sort]');
        if (!button || switchingColumns) return;
        clearTimeout(debounce);
        const sort = button.dataset.followersSort;
        form.elements.direction.value = form.elements.sort.value === sort
            ? form.elements.direction.value === 'asc' ? 'desc' : 'asc'
            : sort === 'name' ? 'asc' : 'desc';
        form.elements.sort.value = sort; writeLocation(); page = 1; load();
    });
    form.addEventListener('change', event => { if (event.target === form.elements.search) return; clearTimeout(debounce); page = 1; load(); });
    root.querySelector('[name="page_size"]').addEventListener('change', () => { clearTimeout(debounce); page = 1; load(); });
    form.elements.search.addEventListener('input', () => { clearTimeout(debounce); clearTimeout(timer); controller?.abort(); sequence++; page = 1; debounce = setTimeout(() => load(), 250); });
    prev.addEventListener('click', () => { page--; load(); }); next.addEventListener('click', () => { page++; load(); });
    refresh.addEventListener('click', () => load(true));
    window.addEventListener('scroll', scheduleRender, {passive: true});
    window.addEventListener('resize', scheduleRender);
    const panelObserver = new ResizeObserver(() => { sizeColumns(); scheduleRender(); }); panelObserver.observe(panel);
    function updateFavoriteState() {
        closeFavoriteConfirmation();
        if (form.elements.raid_favorites.checked || form.elements.sort.value === 'raid_favorite') { load(); return; }
        for (const {row} of rendered.values()) {
            const action = row.querySelector('.follower-favorite-action'), button = action.querySelector('.follower-favorite');
            const selected = favorites.has(action.dataset.userId);
            button.textContent = selected ? '★' : '☆'; button.setAttribute('aria-pressed', String(selected));
        }
    }
    function saveFavorite(userId, removing) {
        const updated = new Set(favorites);
        if (removing) updated.delete(userId);
        else if (updated.size < 100) updated.add(userId);
        else { warning.textContent = 'You can save up to 100 raid favorites.'; warning.hidden = false; return; }
        try { localStorage.setItem(favoriteKey, JSON.stringify([...updated])); }
        catch (_) { warning.textContent = 'Raid favorites could not be saved in this browser.'; warning.hidden = false; return; }
        favorites = updated; updateFavoriteState();
    }
    body.addEventListener('click', event => {
        const row = event.target.closest('[data-follower-index]');
        if (!row || row.classList.contains('follower-details') || event.target.closest('a,input,select,textarea')) return;
        const index = Number(row.dataset.followerIndex), item = rows[index], pair = rendered.get(index);
        if (!pair || pair.row !== row) return;
        const button = event.target.closest('button');
        if (button?.classList.contains('follower-favorite')) {
            if (!favorites.has(item.user_id)) { saveFavorite(item.user_id, false); return; }
            if (pendingFavorite === item.user_id) { closeFavoriteConfirmation(); return; }
            closeFavoriteConfirmation(); pendingFavorite = item.user_id;
            const action = button.closest('.follower-favorite-action'), remove = action.querySelector('.follower-favorite-remove');
            action.classList.add('is-confirming'); remove.disabled = false; remove.tabIndex = 0;
        } else if (button?.classList.contains('follower-favorite-remove')) {
            if (pendingFavorite === item.user_id) saveFavorite(item.user_id, true);
        } else if (!button || button.classList.contains('follower-expand')) {
            if (pair.details.hidden) ensureDetails(item, pair.details);
            pair.details.hidden = !pair.details.hidden;
            row.querySelector('.follower-expand').setAttribute('aria-expanded', String(!pair.details.hidden));
            if (pair.details.hidden) expanded.delete(item.user_id); else expanded.add(item.user_id);
            rebuildOffsets(); scheduleRender();
        }
    });
    body.addEventListener('load', event => {
        if (event.target.matches('[data-follower-avatar]')) event.target.parentElement.classList.add('is-loaded');
    }, true);
    body.addEventListener('error', event => {
        if (event.target.matches('[data-follower-avatar]')) { event.target.parentElement.classList.remove('is-loaded'); event.target.removeAttribute('src'); }
    }, true);
    function syncFavoriteStorage(event) { if (event.key === favoriteKey || event.key === null) { readFavorites(); updateFavoriteState(); } }
    window.addEventListener('storage', syncFavoriteStorage);
    body.addEventListener('keydown', event => {
        if (event.key === 'Escape' && event.target.closest('.follower-favorite-action')) {
            event.preventDefault(); closeFavoriteConfirmation(); event.target.closest('.follower-favorite-action').querySelector('.follower-favorite').focus(); return;
        }
        if (event.key !== 'Tab' || event.ctrlKey || event.altKey || event.metaKey || !event.target.matches(event.shiftKey ? '.follower-expand' : '.follower-favorite')) return;
        const index = Number(event.target.closest('[data-follower-index]').dataset.followerIndex) + (event.shiftKey ? -1 : 1);
        if (index < 0 || index >= rows.length || rendered.has(index)) return;
        event.preventDefault();
        window.scrollTo({top: window.scrollY + body.getBoundingClientRect().top + offsets[index] - 8, behavior: 'instant'});
        renderWindow(); rendered.get(index)?.row.querySelector(event.shiftKey ? '.follower-favorite' : '.follower-expand').focus({preventScroll: true});
    });
    window.addEventListener('pagehide', () => {
        stopped = true;
        clearTimeout(timer); clearTimeout(debounce); clearTimeout(imageTimer); clearTimeout(snapTimer);
        cancelAnimationFrame(frame); cancelAnimationFrame(slideFrame);
        controller?.abort(); imageController?.abort();
        avatarObserver.disconnect(); rowObserver.disconnect(); panelObserver.disconnect();
        document.removeEventListener('pointerdown', closeRolesOutside);
        document.removeEventListener('pointerdown', closeFavoriteConfirmation);
        document.removeEventListener('pointerup', endColumnDrag); document.removeEventListener('pointercancel', endColumnDrag);
        window.removeEventListener('storage', syncFavoriteStorage);
        window.removeEventListener('hashchange', onHashChange);
        window.removeEventListener('scroll', scheduleRender); window.removeEventListener('resize', scheduleRender);
    });
    restoreLocation(true); buildColumns(); load();
})();
