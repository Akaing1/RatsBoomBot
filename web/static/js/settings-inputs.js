(() => {
    'use strict';
    const book = document.querySelector('[data-settings-book]');
    if (!book) return;
    function grow(input) {
        if (!input.clientWidth) return;
        input.style.height = 'auto';
        const style = getComputedStyle(input);
        input.style.height = `${input.scrollHeight + parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth)}px`;
    }
    const growVisible = () => book.querySelectorAll('textarea[data-settings-grow]').forEach(grow);
    book.addEventListener('input', event => { if (event.target.matches('textarea[data-settings-grow]')) grow(event.target); });
    book.addEventListener('settings-section-changed', growVisible);
    let width;
    const observer = new ResizeObserver(entries => {
        const next = entries[0].contentRect.width;
        if (next !== width) { width = next; growVisible(); }
    });
    observer.observe(book);
    window.addEventListener('pagehide', () => observer.disconnect(), {once: true});
    book.querySelectorAll('[data-settings-list]').forEach(editor => {
        const value = editor.querySelector('[data-settings-list-value]');
        const list = document.createElement('div');
        list.className = 'settings-entry-list';
        const add = document.createElement('button');
        add.type = 'button'; add.className = 'button secondary'; add.textContent = '+ Add entry';
        add.dataset.settingsAddEntry = '';
        function sync() {
            const rows = [...list.children];
            value.value = rows.map(row => row.querySelector('input').value.trim()).filter(Boolean).join('\n');
            rows.forEach((row, index) => {
                row.querySelector('span').textContent = index + 1;
                row.querySelector('input').setAttribute('aria-label', `${editor.dataset.entryLabel}, entry ${index + 1}`);
                const remove = row.querySelector('button');
                remove.setAttribute('aria-label', `Remove entry ${index + 1}`);
                remove.disabled = rows.length === 1;
                remove.title = remove.disabled ? 'Keep at least one entry' : 'Remove entry';
            });
            const input = rows[0].querySelector('input');
            input.setCustomValidity(value.value.length > Number(editor.dataset.entryLimit) ? `Keep the list to ${editor.dataset.entryLimit} characters or fewer.` : '');
        }
        function append(text = '') {
            const row = document.createElement('div'); row.className = 'settings-entry-row';
            const number = document.createElement('span'); number.setAttribute('aria-hidden', 'true');
            const input = document.createElement('input');
            input.type = 'text'; input.className = 'profile-setting-input'; input.maxLength = 100;
            input.value = text; input.placeholder = editor.dataset.entryPlaceholder;
            const remove = document.createElement('button');
            remove.type = 'button'; remove.className = 'button secondary settings-entry-remove'; remove.textContent = '×';
            remove.addEventListener('click', () => {
                const index = [...list.children].indexOf(row);
                row.remove(); sync();
                list.children[Math.min(index, list.children.length - 1)].querySelector('input').focus();
                value.dispatchEvent(new Event('input', {bubbles: true}));
            });
            input.addEventListener('input', sync);
            row.append(number, input, remove); list.append(row);
            return input;
        }
        const initial = value.value.split(/\r?\n/).filter(text => text.trim());
        (initial.length ? initial : ['']).forEach(append);
        value.hidden = true; editor.append(list, add); sync();
        add.addEventListener('click', () => { const input = append(); sync(); input.focus(); });
        editor.addEventListener('settings-reset-list', () => {
            list.replaceChildren();
            const entries = value.value.split(/\r?\n/).filter(text => text.trim());
            (entries.length ? entries : ['']).forEach(append);
            sync();
        });
    });
    growVisible();
})();
