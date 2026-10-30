(() => {
    const cache = new Map();
    document.querySelectorAll('[data-shoutout-user-list]').forEach(panel => {
        const query = panel.querySelector('[data-shoutout-user-query]');
        const values = panel.querySelector('textarea');
        const options = panel.querySelector('datalist');
        const status = panel.querySelector('[data-shoutout-user-status]');
        let timer, request;
        query.addEventListener('input', () => {
            clearTimeout(timer); request?.abort(); options.replaceChildren();
            const name = query.value.trim().replace(/^@/, '').toLowerCase();
            status.textContent = '';
            if (!/^[a-z0-9_]{3,25}$/.test(name)) return;
            timer = setTimeout(async () => {
                const controller = new AbortController(); request = controller;
                try {
                    let users = cache.get(name);
                    if (!users) {
                        const response = await fetch(`${panel.dataset.searchUrl}?query=${encodeURIComponent(name)}`, {signal: controller.signal, headers: {Accept: 'application/json'}});
                        const payload = await response.json();
                        if (!response.ok) throw new Error(payload.detail || 'User lookup failed.');
                        users = payload.users; if (cache.size >= 100) cache.delete(cache.keys().next().value); cache.set(name, users);
                    }
                    if (controller.signal.aborted) return;
                    options.replaceChildren(...users.map(user => {
                        const option = document.createElement('option'); option.value = user.login; option.label = user.display_name; return option;
                    }));
                } catch (error) { if (!controller.signal.aborted) status.textContent = error.message; }
            }, 300);
        });
        panel.querySelector('[data-shoutout-user-add]').addEventListener('click', () => {
            const name = query.value.trim().replace(/^@/, '').toLowerCase();
            if (!/^[a-z0-9_]{1,25}$/.test(name)) { status.textContent = 'Enter a Twitch username.'; return; }
            const names = [...new Set([...values.value.split(/[\s,]+/).filter(Boolean).map(value => value.replace(/^@/, '').toLowerCase()), name])];
            if (names.length > 100) { status.textContent = 'Use up to 100 usernames.'; return; }
            values.value = names.join('\n'); values.dispatchEvent(new Event('input', {bubbles: true}));
            query.value = ''; options.replaceChildren(); request?.abort(); clearTimeout(timer); status.textContent = 'Added. Save Changes to apply.';
        });
        window.addEventListener('pagehide', () => { clearTimeout(timer); request?.abort(); });
    });
})();
