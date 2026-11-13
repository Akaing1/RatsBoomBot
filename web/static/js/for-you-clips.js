(() => {
    'use strict';
    const panel = document.querySelector('[data-workspace-panel="clips"]');
    if (!panel) return;
    const find = s => panel.querySelector(s), form = find('[data-clips-filters]');
    const grid = find('[data-clips-grid]'), status = find('[data-clips-status]'), previous = find('[data-clips-prev]'), next = find('[data-clips-next]'), retry = find('[data-clips-retry]');
    const dialog = find('[data-clip-player]'), frame = find('[data-clip-frame]');
    let selectedClip = null, downloadGeneration = 0;
    const pageSize = 50;
    let clips = [], page = 1, totalPages = 1, controller, generation = 0, loaded = false;
    function render() {
        const query = find('#clip-search').value.trim().toLowerCase();
        const days = Number(find('#clip-days').value);
        const cutoff = days ? Date.now() - days * 86400000 : -Infinity;
        const rows = clips.filter(c => Date.parse(c.created_at) >= cutoff &&
            (c.title + ' ' + c.creator_name).toLowerCase().includes(query));
        rows.sort(find('#clip-sort').value === 'newest'
            ? (a,b) => Date.parse(b.created_at) - Date.parse(a.created_at)
            : (a,b) => b.view_count - a.view_count);
        totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
        page = Math.min(page, totalPages);
        previous.disabled = page <= 1; next.disabled = page >= totalPages;
        find('[data-clips-page]').textContent = 'Page ' + page + ' of ' + totalPages;
        grid.replaceChildren();
        for (const clip of rows.slice((page - 1) * pageSize, page * pageSize)) {
            const card = document.createElement('button'); card.type = 'button'; card.className = 'fy-clip-card';
            const image = document.createElement('img'); image.loading = 'lazy'; image.alt = '';
            try { const url = new URL(clip.thumbnail_url); if (url.protocol === 'https:') image.src = url.href; } catch {}
            const title = document.createElement('strong'); title.textContent = clip.title;
            const meta = document.createElement('small'); meta.textContent = clip.creator_name + ' · ' + clip.view_count + ' views · ' + new Date(clip.created_at).toLocaleDateString();
            card.append(image, title, meta); card.addEventListener('click', () => {
                frame.replaceChildren();
                selectedClip = clip.id; ++downloadGeneration;
                find('[data-clip-download]').disabled = false;
                find('[data-clip-save]').hidden = true;
                find('[data-clip-save]').removeAttribute('href');
                const iframe = document.createElement('iframe'); iframe.title = clip.title || 'Twitch clip';
                iframe.src = 'https://clips.twitch.tv/embed?' + new URLSearchParams({clip:clip.id,parent:location.hostname,autoplay:'true'});
                iframe.allow = 'autoplay; fullscreen'; iframe.allowFullscreen = true;
                frame.append(iframe); find('[data-clip-link]').href = 'https://clips.twitch.tv/' + encodeURIComponent(clip.id);
                find('[data-clip-message]').textContent = ''; dialog.showModal();
            }); grid.append(card);
        }
        find('[data-clips-count]').textContent = '– ' + rows.length + ' matching clips';
        status.textContent = !rows.length ? 'No clips match your filters.'
            : 'Showing ' + ((page - 1) * pageSize + 1) + '–' + Math.min(page * pageSize, rows.length) + ' of ' + rows.length + ' clips.';
    }
    async function load() {
        controller?.abort(); controller = new AbortController(); const current = ++generation;
        loaded = false; clips = []; page = 1;
        let cursor = '';
        const collection = new Map(), seenCursors = new Set();
        grid.replaceChildren();
        find('[data-clips-count]').textContent = '';
        find('[data-clips-page]').textContent = '';
        previous.disabled = true; next.disabled = true; retry.hidden = true;
        status.textContent = 'Loading channel clips…'; find('[data-clips-signin]').hidden = true;
        try {
            do {
                if (seenCursors.has(cursor)) throw new Error('Clip pagination stopped progressing. Please retry.');
                seenCursors.add(cursor);
                // Scan complete chronological intervals to include older clips even
                // when Twitch limits its popularity-ordered result set.
                const params = new URLSearchParams({days:'0', after:cursor, sort:'newest'});
                const response = await fetch((document.body.dataset.channelRoot || '/channel') + '/api/for-you/clips?' + params, {signal:controller.signal,cache:'no-store',credentials:'same-origin'});
                if (response.status === 401) throw new Error('Your channel session needs attention. Sign in again, then retry.');
                if (!(response.headers.get('content-type') || '').includes('application/json'))
                    throw new Error('Clips could not load (HTTP ' + response.status + '). Please retry shortly. If this continues, check the bot logs.');
                const result = await response.json();
                if (current !== generation) return;
                if (!response.ok) throw new Error(result.detail || 'Unable to load clips.');
                if (!Array.isArray(result.clips)) throw new Error('Unexpected clip response. Please reload this page.');
                for (const clip of result.clips) collection.set(clip.id, clip);
                cursor = result.cursor || '';
                status.textContent = 'Loading channel clips… ' + collection.size + ' found.';
            } while (cursor);
            clips = [...collection.values()]; loaded = true; render();
        } catch (error) {
            if (error.name !== 'AbortError' && current === generation) {
                status.textContent = error.message;
                find('[data-clips-signin]').hidden = !error.message.includes('Sign in again');
                retry.hidden = false;
            }
        }
    }
    function filterChanged() { page = 1; if (loaded) render(); }
    form.addEventListener('submit', e => e.preventDefault());
    find('#clip-days').addEventListener('change', filterChanged);
    find('#clip-search').addEventListener('input', filterChanged);
    find('#clip-sort').addEventListener('change', filterChanged);
    previous.addEventListener('click', () => { if (loaded && page > 1) { --page; render(); } });
    next.addEventListener('click', () => { if (loaded && page < totalPages) { ++page; render(); } });
    retry.addEventListener('click', load);
    find('[data-clip-close]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => {
        frame.replaceChildren(); selectedClip = null; ++downloadGeneration;
        find('[data-clip-save]').hidden = true; find('[data-clip-save]').removeAttribute('href');
    });
    find('[data-clip-download]').addEventListener('click', async () => {
        if (!selectedClip) return;
        const current = ++downloadGeneration, button = find('[data-clip-download]');
        button.disabled = true;
        find('[data-clip-save]').hidden = true;
        find('[data-clip-message]').textContent = 'Preparing download…';
        try {
            const response = await fetch((document.body.dataset.channelRoot || '/channel') + '/api/for-you/clips/download', {
                method:'POST', credentials:'same-origin', cache:'no-store',
                body: new URLSearchParams({
                    clip_id:selectedClip,
                    csrf_token:document.querySelector('[data-workspace-page]').dataset.csrf
                })
            });
            if (!(response.headers.get('content-type') || '').includes('application/json'))
                throw new Error('Download service unavailable (HTTP ' + response.status + '). Please retry.');
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || 'Download unavailable.');
            const url = new URL(result.url);
            if (url.protocol !== 'https:') throw new Error('Invalid download response.');
            if (current !== downloadGeneration || !dialog.open) return;
            const save = find('[data-clip-save]');
            save.href = url.href; save.hidden = false;
            find('[data-clip-message]').textContent = 'Ready. Select Save video. If it opens in a new tab, use the video menu to save it.';
        } catch (error) {
            if (current === downloadGeneration) find('[data-clip-message]').textContent = error.message;
        } finally { if (current === downloadGeneration) button.disabled = false; }
    });
    find('[data-clip-copy]').addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(find('[data-clip-link]').href); find('[data-clip-message]').textContent = 'Link copied.'; }
        catch { find('[data-clip-message]').textContent = 'Copy failed. Use the Open on Twitch link.'; }
    });
    document.querySelectorAll('[data-workspace-tab]').forEach(tab => tab.addEventListener('click', () => {
        if (tab.dataset.workspaceTab === 'clips') { if (!loaded) load(); }
        else { controller?.abort(); ++generation; dialog.close(); frame.replaceChildren(); }
    }));
})();
