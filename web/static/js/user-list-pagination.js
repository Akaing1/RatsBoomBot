(() => {
    const pageSize = 10;
    const states = new WeakMap();
    function refresh(list) {
        let state = states.get(list);
        if (!state) {
            const nav = document.createElement('nav'); nav.className = 'user-list-pagination';
            nav.setAttribute('aria-label', 'User list pages');
            const previous = document.createElement('button'); previous.type = 'button'; previous.className = 'button secondary'; previous.setAttribute('aria-label', 'Previous page'); previous.title = 'Previous page';
            previous.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 18-6-6 6-6"/></svg>';
            const status = document.createElement('span'); status.setAttribute('aria-live', 'polite');
            const next = document.createElement('button'); next.type = 'button'; next.className = 'button secondary'; next.setAttribute('aria-label', 'Next page'); next.title = 'Next page';
            next.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg>';
            nav.append(previous, status, next); list.after(nav);
            state = {page: 0, rows: null, nav, previous, status, next}; states.set(list, state);
            previous.addEventListener('click', () => { state.page--; render(list, state); });
            next.addEventListener('click', () => { state.page++; render(list, state); });
        }
        const rows = [...list.children].filter(node => node.matches('.user-list-row'));
        if (state.rows?.length === rows.length && rows.every((row, index) => row === state.rows[index])) return;
        state.rows = rows;
        render(list, state);
    }
    function render(list, state) {
        const count = state.rows.length;
        const pages = Math.max(1, Math.ceil(count / pageSize));
        state.page = Math.max(0, Math.min(state.page, pages - 1));
        const start = state.page * pageSize;
        state.rows.forEach((row, index) => { row.hidden = index < start || index >= start + pageSize; });
        state.nav.hidden = count <= pageSize;
        state.previous.disabled = state.page === 0;
        state.next.disabled = state.page === pages - 1;
        state.status.textContent = `${state.page + 1} / ${pages}`;
    }
    document.querySelectorAll('[data-user-list]').forEach(refresh);
    new MutationObserver(records => {
        const lists = new Set();
        records.forEach(record => {
            const list = record.target.closest?.('[data-user-list]');
            if (list) lists.add(list);
            record.addedNodes.forEach(node => {
                if (!(node instanceof Element)) return;
                if (node.matches('[data-user-list]')) lists.add(node);
                node.querySelectorAll('[data-user-list]').forEach(item => lists.add(item));
            });
        });
        lists.forEach(list => { if (list.isConnected) refresh(list); });
    }).observe(document.body, {childList: true, subtree: true});
})();
