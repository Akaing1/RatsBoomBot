(() => {
    document.querySelectorAll('[data-role-form]').forEach(form => {
        const select = form.querySelector('[data-role-select]');
        const status = form.querySelector('[data-role-status]');
        select.addEventListener('change', async () => {
            const data = new FormData(form);
            select.disabled = true;
            status.textContent = 'Saving…';
            try {
                const response = await fetch(form.action, {method: 'POST', body: data, credentials: 'same-origin', headers: {'Accept': 'application/json'}});
                if (!response.ok) throw new Error(await failure(response, 'Could not change role. Try again.'));
                select.dataset.original = select.value;
                select.classList.toggle('role-super', select.value === 'super');
                select.classList.toggle('role-edit', select.value === 'edit');
                status.textContent = 'Role updated.';
            } catch (error) {
                select.value = select.dataset.original;
                status.textContent = error.message;
            } finally { select.disabled = false; }
        });
    });
    const search = document.querySelector('[data-access-search]');
    const result = document.querySelector('[data-access-result]');
    if (!search || !result) return;
    const query = search.elements.query;
    const message = search.querySelector('[data-access-message]');
    const id = result.querySelector('[data-access-id]');
    const label = result.querySelector('[data-access-label]');
    const save = result.querySelector('button[type="submit"]');
    let generation = 0;
    let controller;
    function clearSelection() {
        generation += 1;
        controller?.abort();
        result.hidden = true;
        id.value = '';
        message.textContent = '';
    }
    query.addEventListener('input', clearSelection);
    async function failure(response, fallback) {
        try {
            const payload = await response.json();
            return typeof payload.detail === 'string' ? payload.detail : fallback;
        } catch { return fallback; }
    }
    search.addEventListener('submit', async event => {
        event.preventDefault();
        clearSelection();
        const current = generation;
        controller = new AbortController();
        message.textContent = 'Searching Twitch…';
        try {
            const response = await fetch(`/channel/access/search?query=${encodeURIComponent(query.value)}`, {
                headers: {'Accept': 'application/json'}, credentials: 'same-origin', signal: controller.signal
            });
            if (!response.ok) throw new Error(await failure(response, 'Twitch user lookup failed. Please try again.'));
            const {user} = await response.json();
            if (current !== generation) return;
            if (user.is_owner) { message.textContent = 'You already own this channel.'; return; }
            id.value = user.id;
            label.textContent = `${user.display_name} (${user.id})`;
            result.elements.permission.value = user.permission || 'edit';
            save.textContent = user.permission ? 'Update access' : 'Save access';
            result.hidden = false;
            message.textContent = user.permission ? 'This user already has access. You can update their permission.' : 'User found. Confirm their access below.';
        } catch (error) {
            if (current === generation && error.name !== 'AbortError') message.textContent = error.message;
        }
    });
    result.addEventListener('submit', async event => {
        event.preventDefault();
        if (!id.value || save.disabled) return;
        save.disabled = true;
        const current = generation;
        const data = new FormData(result);
        try {
            const response = await fetch(result.action, {method: 'POST', body: data, credentials: 'same-origin', headers: {'Accept': 'application/json'}});
            if (!response.ok) throw new Error(await failure(response, 'Could not save access. Please try again.'));
            window.location.assign('/channel/access');
        } catch (error) {
            if (current === generation) message.textContent = error.message;
        } finally { save.disabled = false; }
    });
})();
