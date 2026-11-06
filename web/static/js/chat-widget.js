(() => {
    document.querySelector('[data-dock-reload]')?.addEventListener('click', () => window.location.reload());
    const form = document.querySelector('[data-dock-composer]');
    if (!form) return;
    const input = form.querySelector('[name="message"]');
    const button = form.querySelector('[type="submit"]');
    const status = form.querySelector('[data-dock-send-status]');
    let sending = false;
    input.addEventListener('keydown', event => {
        if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
            event.preventDefault(); form.requestSubmit();
        }
    });
    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (sending || !input.value.trim()) return;
        sending = true; button.disabled = true;
        const draft = input.value;
        const controller = new AbortController();
        const timeout = window.setTimeout(() => controller.abort(), 15000);
        status.textContent = 'Sending…';
        try {
            const response = await fetch(form.action, {method: 'POST', body: new FormData(form),
                credentials: 'same-origin', signal: controller.signal, headers: {Accept: 'application/json'}});
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || 'Unable to send message.');
            const errors = Object.values(result.errors || {});
            status.textContent = errors.length ? errors.join(' ') : 'Sent';
            if ((result.sent || []).length && input.value === draft) input.value = '';
        } catch (error) {
            status.textContent = error.name === 'AbortError' ? 'Send timed out. Check chat before retrying.' : error.message;
        } finally {
            window.clearTimeout(timeout); sending = false; button.disabled = false; input.focus();
        }
    });
})();
