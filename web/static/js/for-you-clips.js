(() => {
    'use strict';
    const panel = document.querySelector('[data-workspace-panel="clips"]');
    if (!panel) return;
    const find = s => panel.querySelector(s), form = find('[data-clips-filters]');
    const grid = find('[data-clips-grid]'), status = find('[data-clips-status]'), more = find('[data-clips-more]');
    const dialog = find('[data-clip-player]'), frame = find('[data-clip-frame]');
    let clips = [], cursor = '', controller, generation = 0, loaded = false;
    function render() {
        const query = find('#clip-search').value.trim().toLowerCase();
        const rows = clips.filter(c => (c.title + ' ' + c.creator_name).toLowerCase().includes(query));
        rows.sort(find('#clip-sort').value === 'newest'
            ? (a,b) => Date.parse(b.created_at) - Date.parse(a.created_at)
            : (a,b) => b.view_count - a.view_count);
        grid.replaceChildren();
        for (const clip of rows) {
            const card = document.createElement('button'); card.type = 'button'; card.className = 'fy-clip-card';
            const image = document.createElement('img'); image.loading = 'lazy'; image.alt = '';
            try { const url = new URL(clip.thumbnail_url); if (url.protocol === 'https:') image.src = url.href; } catch {}
            const title = document.createElement('strong'); title.textContent = clip.title;
            const meta = document.createElement('small'); meta.textContent = clip.creator_name + ' · ' + clip.view_count + ' views · ' + new Date(clip.created_at).toLocaleDateString();
            card.append(image, title, meta); card.addEventListener('click', () => {
                frame.replaceChildren();
                const iframe = document.createElement('iframe'); iframe.title = clip.title || 'Twitch clip';
                iframe.src = 'https://clips.twitch.tv/embed?' + new URLSearchParams({clip:clip.id,parent:location.hostname,autoplay:'true'});
                iframe.allow = 'autoplay; fullscreen'; iframe.allowFullscreen = true;
                frame.append(iframe); find('[data-clip-link]').href = 'https://clips.twitch.tv/' + encodeURIComponent(clip.id);
                find('[data-clip-message]').textContent = ''; dialog.showModal();
            }); grid.append(card);
        }
        status.textContent = rows.length + ' shown · ' + clips.length + ' loaded' + (clips.length ? '' : '. No clips found in this date range.');
    }
    async function load(reset) {
        controller?.abort(); controller = new AbortController(); const current = ++generation;
        if (reset) { loaded = false; clips = []; cursor = ''; grid.replaceChildren(); more.hidden = true; }
        status.textContent = 'Loading clips…'; find('[data-clips-signin]').hidden = true; more.disabled = true;
        try {
            const params = new URLSearchParams({days:find('#clip-days').value,after:cursor});
            const response = await fetch('/channel/api/for-you/clips?' + params, {signal:controller.signal,cache:'no-store',credentials:'same-origin'});
            if (response.redirected || response.status === 401 || response.status === 403) {
                throw new Error('Your channel session needs attention. Sign in again, then retry.');
            }
            if (!(response.headers.get('content-type') || '').includes('application/json')) {
                throw new Error('The server returned a page instead of clips. Sign in again or reload after deployment, then retry.');
            }
            const result = await response.json(); if (!response.ok) throw new Error(result.detail || 'Unable to load clips.');
            if (!Array.isArray(result.clips)) throw new Error('Unexpected clip response. Please reload this page.');
            if (current !== generation) return;
            clips = [...new Map([...clips,...result.clips].map(c => [c.id,c])).values()].slice(0,1000);
            cursor = result.cursor; loaded = true; more.hidden = !cursor || clips.length >= 1000; render();
        } catch (error) { if (error.name !== 'AbortError' && current === generation) { status.textContent = error.message; find('[data-clips-signin]').hidden = !error.message.includes('Sign in again'); } }
        finally { if (current === generation) more.disabled = false; }
    }
    form.addEventListener('submit', e => {e.preventDefault(); load(true);});
    form.addEventListener('reset', () => setTimeout(() => load(true),0));
    find('#clip-search').addEventListener('input', render); find('#clip-sort').addEventListener('change',render);
    more.addEventListener('click', () => load(false));
    find('[data-clip-close]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => frame.replaceChildren());
    find('[data-clip-copy]').addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(find('[data-clip-link]').href); find('[data-clip-message]').textContent = 'Link copied.'; }
        catch { find('[data-clip-message]').textContent = 'Copy failed. Use the Open on Twitch link.'; }
    });
    document.querySelectorAll('[data-workspace-tab]').forEach(tab => tab.addEventListener('click', () => {
        if (tab.dataset.workspaceTab === 'clips') { if (!loaded) load(true); }
        else { controller?.abort(); ++generation; dialog.close(); frame.replaceChildren(); }
    }));
})();
