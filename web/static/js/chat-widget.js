(() => {
    const form = document.querySelector('[data-dock-composer]');
    if (!form) return;
    let input = form.querySelector('[name="message"]');
    const button = form.querySelector('[type="submit"]');
    const status = form.querySelector('[data-dock-send-status]');
    let emotes = [], personalGroup = '', loadedAt = 0, loading = null;
    const target = document.querySelector('#dock-target');
    const picker = form.querySelector('[data-dock-picker]');
    const toggle = form.querySelector('[data-dock-emotes]');
    input = window.createChatEmoteInput?.({input, getEmotes: () => emotes,
        enabled: () => target?.value !== 'youtube',
        onLimit: () => { status.textContent = 'Messages can contain up to 500 characters.'; }}) || input;
    const pickerView = window.createChatEmotePicker?.({picker, getEmotes: () => emotes,
        getPersonalGroup: () => personalGroup,
        insert(name) {
            const start = input.selectionStart, end = input.selectionEnd;
            const prefix = start && !/\s/.test(input.value[start - 1]) ? ' ' : '';
            input.setRangeText(prefix + name + ' ', start, end, 'end');
            input.dispatchEvent(new Event('input', {bubbles: true})); input.focus();
        }});
    async function loadEmotes() {
        if (loading || Date.now() - loadedAt < 30000) return loading;
        loading = (async () => {
            try {
                const response = await fetch('/channel/api/chat/emotes', {cache: 'no-store'});
                const result = await response.json();
                if (!response.ok) throw new Error(result.detail || 'Emotes unavailable.');
                emotes = (result.emotes || []).filter(emote => typeof emote.name === 'string'
                    && /^https:\/\/(?:static-cdn\.jtvnw\.net|cdn\.7tv\.app|cdn\.betterttv\.net|cdn\.frankerfacez\.com)\//.test(emote.url));
                personalGroup = result.personal_group_key || '';
                loadedAt = Date.now(); input.refreshEmotes?.();
                pickerView.renderGroups(); pickerView.render();
                pickerView.note.textContent = result.twitch_reconnect_required
                    ? 'Reconnect Twitch from the dashboard to load all your available emotes.' : '';
            } catch (error) { pickerView.note.textContent = error.message; }
            finally { loading = null; }
        })();
        return loading;
    }
    function closePicker() { if (picker) picker.hidden = true; toggle?.setAttribute('aria-expanded', 'false'); }
    if (pickerView) {
        toggle.addEventListener('click', () => {
            picker.hidden = !picker.hidden;
            toggle.setAttribute('aria-expanded', String(!picker.hidden));
            if (!picker.hidden) { loadEmotes(); pickerView.search.focus(); }
        });
        target?.addEventListener('change', () => {
            toggle.disabled = target.value === 'youtube'; closePicker(); input.refreshEmotes?.();
        });
        document.addEventListener('click', event => { if (!form.contains(event.target)) closePicker(); });
        form.addEventListener('keydown', event => { if (event.key === 'Escape') closePicker(); });
        input.addEventListener('focus', loadEmotes);
    }
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
            status.textContent = errors.length ? errors.join(' ') : '';
            if ((result.sent || []).length && input.value === draft) input.value = '';
        } catch (error) {
            status.textContent = error.name === 'AbortError' ? 'Send timed out. Check chat before retrying.' : error.message;
        } finally {
            window.clearTimeout(timeout); sending = false; button.disabled = false; input.focus();
        }
    });
})();
