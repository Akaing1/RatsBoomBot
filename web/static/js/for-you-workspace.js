(() => {
    'use strict';
    const root = document.querySelector('[data-workspace-page]');
    if (!root) return;
    const find = selector => root.querySelector(selector);
    const status = find('[data-workspace-status]'), note = find('#workspace-note'), save = find('[data-note-save]');
    let revision = null, dirty = false, saving = false, quoteBusy = false, noteOffset = 0, quoteOffset = 0, search = '', quoteGeneration = 0, noteGeneration = 0;
    const notify = (text, error = false) => { status.textContent = text; status.classList.toggle('fy-error', error); };
    const title = key => key === 'legacy' ? 'Previous notes' : key.startsWith('day:') ? `Offline · ${key.slice(4)} (UTC)` : `Stream #${key.slice(7)}`;
    async function request(path = '', data) {
        const response = await fetch('/channel/api/for-you' + path, {credentials: 'same-origin', cache: 'no-store', method: data ? 'POST' : 'GET', ...(data ? {body: new URLSearchParams({csrf_token: root.dataset.csrf, ...data})} : {})});
        let result;
        try { result = await response.json(); } catch { throw new Error('Could not reach For You. Please try again.'); }
        if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Please check your input and try again.');
        return result;
    }
    async function loadNote(force = false) {
        if (saving || (dirty && !force)) return;
        if (dirty && !confirm('Discard your unsaved note edits and reload?')) return;
        const generation = ++noteGeneration;
        const result = await request();
        if (generation !== noteGeneration || saving || (dirty && !force)) return;
        note.value = result.notes; revision = result.notes_revision; dirty = false; note.disabled = false; save.disabled = true;
        find('[data-note-title]').textContent = title(result.note_key);
        find('[data-note-state]').textContent = 'Saved';
    }
    const run = fn => Promise.resolve().then(fn).catch(e => notify(e.message, true));
    note.addEventListener('input', () => { ++noteGeneration; dirty = true; save.disabled = saving; find('[data-note-state]').textContent = 'Unsaved changes'; });
    save.addEventListener('click', () => run(async () => {
        if (saving || revision === null) return;
        saving = true; save.disabled = true; ++noteGeneration;
        const submitted = note.value;
        try {
            const result = await request('', {action: 'notes', notes: submitted, revision});
            revision = result.notes_revision; dirty = note.value !== submitted;
            find('[data-note-state]').textContent = dirty ? 'Unsaved changes' : 'Saved'; notify('Note saved.'); await loadArchive();
        } finally { saving = false; save.disabled = !dirty; }
    }));
    find('[data-note-refresh]').addEventListener('click', () => run(() => loadNote(true)));
    function button(label, callback) { const b = document.createElement('button'); b.type = 'button'; b.className = 'button secondary'; b.textContent = label; b.addEventListener('click', () => run(callback)); return b; }
    async function loadArchive() {
        const result = await request('/notes?offset=' + noteOffset), list = find('[data-notes-list]'); list.replaceChildren();
        for (const entry of result.items) { const details = document.createElement('details'), summary = document.createElement('summary'), text = document.createElement('pre'); summary.textContent = title(entry.note_key) + " · " + entry.updated_at + " UTC"; text.textContent = entry.notes || '(Empty note)'; details.append(summary, text); list.append(details); }
        if (!result.items.length) list.textContent = 'No saved notes yet.';
        find('[data-notes-prev]').disabled = noteOffset === 0; find('[data-notes-next]').disabled = !result.more;
    }
    async function loadQuotes() {
        const generation = ++quoteGeneration;
        const result = await request('/quotes?search=' + encodeURIComponent(search) + '&offset=' + quoteOffset);
        if (generation !== quoteGeneration) return;
        const list = find('[data-quotes-list]'); list.replaceChildren();
        for (const entry of result.items) {
            const card = document.createElement('article'); card.className = 'fy-quote';
            const label = document.createElement('label'); label.textContent = `Quote #${entry.number}`; label.htmlFor = 'quote-' + entry.manager_id;
            const field = document.createElement('textarea'); field.id = label.htmlFor; field.value = entry.message; field.maxLength = 350; field.rows = 3;
            const actions = document.createElement('div'); actions.className = 'fy-actions';
            const mutate = async action => {
                if (quoteBusy) return;
                if (action === 'delete' && !confirm(`Delete quote #${entry.number}? Remaining quotes will be renumbered.`)) return;
                quoteBusy = true; actions.querySelectorAll('button').forEach(b => { b.disabled = true; });
                try { await request('/quotes', {action, identity: entry.manager_id, original: entry.message, message: field.value}); notify(action === 'delete' ? 'Quote deleted.' : 'Quote saved.'); await loadQuotes(); }
                finally { quoteBusy = false; actions.querySelectorAll('button').forEach(b => { b.disabled = false; }); }
            };
            actions.append(button('Save changes', () => mutate('edit')), button('Delete', () => mutate('delete'))); card.append(label, field, actions); list.append(card);
        }
        if (!result.items.length) list.textContent = 'No quotes found.';
        find('[data-quotes-prev]').disabled = quoteOffset === 0; find('[data-quotes-next]').disabled = !result.more;
    }
    find('[data-quote-add]').addEventListener('submit', event => { event.preventDefault(); const form = event.currentTarget; run(async () => {
        if (quoteBusy) return; quoteBusy = true; const field = find('#new-quote'), submitted = field.value; form.querySelector('button').disabled = true;
        try { await request('/quotes', {action: 'add', message: submitted}); if (field.value === submitted) field.value = ''; quoteOffset = 0; notify('Quote added.'); await loadQuotes(); }
        finally { quoteBusy = false; form.querySelector('button').disabled = false; }
    }); });
    find('[data-quote-search]').addEventListener('submit', event => { event.preventDefault(); search = find('#quote-search').value; quoteOffset = 0; run(loadQuotes); });
    for (const [kind, load] of [['notes', loadArchive], ['quotes', loadQuotes]]) for (const [direction, amount] of [['prev', -20], ['next', 20]]) find(`[data-${kind}-${direction}]`).addEventListener('click', () => { if (kind === 'notes') noteOffset = Math.max(0, noteOffset + amount); else quoteOffset = Math.max(0, quoteOffset + amount); run(load); });
    find('[data-archive-refresh]').addEventListener('click', () => run(loadArchive));
    root.querySelectorAll('[data-workspace-tab]').forEach(tab => tab.addEventListener('click', () => {
        notify('');
        root.querySelectorAll('[data-workspace-tab]').forEach(b => { b.classList.toggle('active', b === tab); b.setAttribute('aria-pressed', String(b === tab)); });
        root.querySelectorAll('[data-workspace-panel]').forEach(p => { p.hidden = p.dataset.workspacePanel !== tab.dataset.workspaceTab; });
    }));
    window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
    window.addEventListener('focus', () => run(() => loadNote()));
    run(loadNote); run(loadArchive); run(loadQuotes);
})();
