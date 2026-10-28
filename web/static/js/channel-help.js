(() => {
    const root = document.querySelector('.channel-help');
    const controls = root?.querySelector('[data-help-filters]');
    if (!controls) return;
    const groups = [...root.querySelectorAll('[data-help-group]')];
    const cards = [...root.querySelectorAll('[data-help-command]')];
    const search = root.querySelector('#help-search');
    const permission = root.querySelector('#help-permission');
    const nav = root.querySelector('[data-help-categories]');
    let selected = null;
    [...new Set(cards.map(card => card.dataset.permission))].sort().forEach(value => {
        const option = document.createElement('option'); option.value = value; option.textContent = value; permission.append(option);
    });
    const buttons = [null, ...groups].map(group => {
        const button = document.createElement('button'); button.type = 'button';
        button.textContent = group ? group.dataset.helpGroup : 'All commands';
        button.addEventListener('click', () => { selected = group; update(); });
        nav.append(button); return button;
    });
    function update() {
        const query = search.value.trim().toLocaleLowerCase(); let count = 0;
        groups.forEach(group => {
            let visible = 0;
            group.querySelectorAll('[data-help-command]').forEach(card => {
                const matches = (!selected || selected === group) && (!permission.value || permission.value === card.dataset.permission)
                    && card.dataset.search.includes(query);
                card.hidden = !matches; if (matches) { visible++; count++; }
            });
            group.hidden = visible === 0;
            if (visible && (query || selected || permission.value)) group.open = true;
        });
        buttons.forEach((button, i) => button.setAttribute('aria-pressed', String((i === 0 && !selected) || groups[i - 1] === selected)));
        root.querySelector('[data-help-count]').textContent = `${count} of ${cards.length} commands`;
        root.querySelector('[data-help-empty]').hidden = count > 0;
    }
    cards.forEach(card => {
        card.dataset.search = (card.textContent + ' ' + card.closest('[data-help-group]').dataset.helpGroup).toLocaleLowerCase();
        const code = card.querySelector('code');
        const button = document.createElement('button'); button.type = 'button'; button.className = 'help-copy'; button.textContent = 'Copy';
        button.setAttribute('aria-label', 'Copy ' + code.textContent.trim());
        button.addEventListener('click', async () => {
            const status = root.querySelector('[data-help-copy-status]');
            try {
                await navigator.clipboard.writeText(code.textContent.trim()); button.textContent = 'Copied';
                status.textContent = 'Command copied. Replace any placeholders before sending in Twitch chat.';
                setTimeout(() => { button.textContent = 'Copy'; }, 2000);
            } catch { button.textContent = 'Select text'; status.textContent = 'Copy unavailable. Select and copy the command text.'; }
        });
        card.append(button);
    });
    search.addEventListener('input', update); permission.addEventListener('change', update);
    controls.hidden = false; update();
})();
