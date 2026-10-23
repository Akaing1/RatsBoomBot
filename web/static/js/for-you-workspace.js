(() => {
    'use strict';
    const root = document.querySelector('[data-workspace-page]');
    if (!root) return;
    const find = selector => root.querySelector(selector);
    const status = find('[data-workspace-status]'), note = find('#workspace-note'), save = find('[data-note-save]');
    let revision = null, dirty = false, saving = false, quoteBusy = false, noteOffset = 0, quoteOffset = 0, search = '', quoteGeneration = 0, noteGeneration = 0;
    const notify = (text, error = false) => { status.textContent = text; status.classList.toggle('fy-error', error); };
    const titleInput = find('#workspace-title');
    let selected = null, currentMode = true, noteBusy = false;
    const canLeave = () => !dirty || confirm('Discard your unsaved note changes?');
    async function request(path = '', data) {
        const response = await fetch('/channel/api/for-you' + path, {credentials: 'same-origin', cache: 'no-store', method: data ? 'POST' : 'GET', ...(data ? {body: new URLSearchParams({csrf_token: root.dataset.csrf, ...data})} : {})});
        let result;
        try { result = await response.json(); } catch { throw new Error('Could not reach For You. Please try again.'); }
        if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Please check your input and try again.');
        return result;
    }
    function adoptNote(entry, current) {
        selected = entry; currentMode = current;
        revision = current ? entry.notes_revision : entry.revision;
        note.value = entry.notes; titleInput.value = entry.title;
        titleInput.placeholder = entry.display_name; find('[data-note-title]').textContent = entry.display_name;
        dirty = false; note.disabled = false; titleInput.disabled = false; save.disabled = true;
        find('[data-note-delete]').disabled = !entry.note_id;
        find('[data-note-state]').textContent = '';
    }
    async function loadNote(force = false) {
        if (saving || noteBusy || (!currentMode && !force) || (dirty && !force)) return;
        if (dirty && !canLeave()) return;
        const generation = ++noteGeneration;
        if (!currentMode && selected?.note_id) {
            const entry = await request('/notes/' + selected.note_id);
            if (generation === noteGeneration) adoptNote(entry, false);
        } else {
            const entry = await request();
            if (generation === noteGeneration) adoptNote(entry, true);
        }
    }
    const run = fn => Promise.resolve().then(fn).catch(e => notify(e.message, true));
    for (const field of [note, titleInput]) field.addEventListener('input', () => { ++noteGeneration; dirty = true; save.disabled = saving; find('[data-note-state]').textContent = 'Unsaved changes'; });
    save.addEventListener('click', () => run(async () => {
        if (saving || noteBusy || revision === null) return;
        saving = true; save.disabled = true; ++noteGeneration;
        const submitted = note.value, submittedTitle = titleInput.value;
        try {
            const result = currentMode
                ? await request('', {action: 'notes', notes: submitted, title: submittedTitle, revision})
                : (await request('/notes', {action: 'save', identity: selected.note_id, revision, notes: submitted, title: submittedTitle})).item;
            selected = result; revision = currentMode ? result.notes_revision : result.revision;
            dirty = note.value !== submitted || titleInput.value !== submittedTitle;
            titleInput.placeholder = result.display_name; find('[data-note-title]').textContent = result.display_name;
            find('[data-note-delete]').disabled = !result.note_id;
            find('[data-note-state]').textContent = dirty ? 'Unsaved changes' : '';
            notify('Note saved.'); await loadArchive();
        } finally { saving = false; save.disabled = !dirty; }
    }));
    find('[data-note-refresh]').addEventListener('click', () => run(() => loadNote(true)));
    function button(label, callback) { const b = document.createElement('button'); b.type = 'button'; b.className = 'button secondary'; b.textContent = label; b.addEventListener('click', () => run(callback)); return b; }
    async function noteAction(action, entry) {
        if (noteBusy || saving) return;
        if (action === 'delete' && !confirm('Delete this note?')) return;
        if ((action === 'delete' || action === 'create') && !canLeave()) return;
        noteBusy = true; ++noteGeneration; note.disabled = true; titleInput.disabled = true;
        try {
            const result = await request('/notes', {action, identity: entry?.note_id || '', revision: entry?.revision || 0});
            if (action === 'create') { adoptNote(result.item, false); noteOffset = 0; }
            if (action === 'delete') { selected = null; currentMode = true; dirty = false; adoptNote(await request(), true); }
            await loadArchive(); notify(action === 'delete' ? 'Note deleted.' : action === 'create' ? 'Note created.' : 'Note moved.');
        } finally { noteBusy = false; note.disabled = false; titleInput.disabled = false; }
    }
    find('[data-note-current]').addEventListener('click', () => run(async () => { if (saving || noteBusy || !canLeave()) return; dirty = false; currentMode = true; await loadNote(true); await loadArchive(); }));
    find('[data-note-new]').addEventListener('click', () => run(() => noteAction('create')));
    find('[data-note-delete]').addEventListener('click', () => run(async () => {
        if (!selected?.note_id || saving || noteBusy) return;
        // The Overview and archive have separate revision counters.
        const entry = currentMode ? {...selected, revision: selected.archive_revision} : selected;
        await noteAction('delete', entry);
    }));
    async function loadArchive() {
        const result = await request('/notes?offset=' + noteOffset), list = find('[data-notes-list]'); list.replaceChildren();
        if (!result.items.length && noteOffset > 0) { noteOffset = Math.max(0, noteOffset - 20); return loadArchive(); }
        for (const entry of result.items) {
            const row = document.createElement('div'); row.className = 'fy-note-row';
            const open = button(entry.display_name, async () => { if (saving || noteBusy || !canLeave()) return; const generation = ++noteGeneration; const item = await request('/notes/' + entry.note_id); if (generation !== noteGeneration) return; adoptNote(item, false); await loadArchive(); });
            open.className = 'fy-note-open'; open.setAttribute('aria-current', String(selected?.note_id === entry.note_id));
            const up = button('↑', () => noteAction('up', entry)), down = button('↓', () => noteAction('down', entry));
            up.setAttribute('aria-label', 'Move ' + entry.display_name + ' up'); down.setAttribute('aria-label', 'Move ' + entry.display_name + ' down');
            up.disabled = entry.position === 1;
            down.disabled = !result.more && entry === result.items.at(-1);
            row.append(open, up, down); list.append(row);
            if (selected?.note_id === entry.note_id && !dirty) { find('[data-note-title]').textContent = entry.display_name; titleInput.placeholder = entry.display_name; }
        }
        if (!result.items.length) list.textContent = 'No saved notes.';
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
