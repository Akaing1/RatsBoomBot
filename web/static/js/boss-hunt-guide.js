(() => {
    const nav = document.querySelector('[data-hunt-nav]');
    if (!nav) return;
    const panels = [...document.querySelectorAll('.public-raid-guide > details')];
    const labels = ['Shop', 'Crafting', 'How to play', 'Rewards', 'Commands', 'History'];
    const buttons = panels.map((panel, index) => {
        const button = document.createElement('button');
        button.type = 'button'; button.textContent = labels[index];
        panel.id = 'hunt-' + labels[index].toLowerCase().replaceAll(' ', '-');
        button.setAttribute('aria-controls', panel.id);
        button.addEventListener('click', () => select(index));
        nav.append(button); return button;
    });
    function select(index) {
        panels.forEach((panel, i) => { panel.hidden = i !== index; if (i === index) panel.open = true; });
        buttons.forEach((button, i) => button.setAttribute('aria-pressed', String(i === index)));
    }
    select(0); nav.hidden = false;
    const categories = [...document.querySelectorAll('.public-raid-shop-category')];
    const filters = document.createElement('div'); filters.className = 'hunt-shop-filters';
    filters.setAttribute('aria-label', 'Shop categories');
    const choices = ['All items', ...categories.map(section => section.querySelector('h3').textContent)];
    choices.forEach((name, index) => {
        const button = document.createElement('button'); button.type = 'button'; button.textContent = name;
        button.setAttribute('aria-pressed', String(index === 0));
        button.addEventListener('click', () => {
            categories.forEach((section, i) => { section.hidden = index !== 0 && i !== index - 1; });
            [...filters.children].forEach(child => child.setAttribute('aria-pressed', String(child === button)));
        });
        filters.append(button);
    });
    categories[0]?.before(filters);
    const status = document.querySelector('[data-hunt-copy-status]');
    document.querySelectorAll('.hunt-guide code').forEach(code => {
        const command = code.textContent.trim();
        if (!command.startsWith('!')) return;
        const button = document.createElement('button'); button.type = 'button'; button.className = 'hunt-copy';
        button.setAttribute('aria-label', 'Copy ' + command);
        code.replaceWith(button); button.append(code);
        const label = document.createElement('span'); label.textContent = 'Copy'; button.append(label);
        button.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(command);
                label.textContent = 'Copied'; status.textContent = 'Copied ' + command + '. Paste it into Twitch chat.';
                setTimeout(() => { label.textContent = 'Copy'; }, 2000);
            } catch {
                label.textContent = 'Select text'; status.textContent = 'Copy unavailable. Select and copy the command text.';
            }
        });
    });
})();
