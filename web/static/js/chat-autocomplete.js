(() => {
    let sequence = 0;
    window.createChatAutocomplete = ({input, box, getEmotes = () => [], getUsers = () => [], getCommands = () => [],
        loadEmotes = async () => {}, loadUsers = async () => {}, enabled = () => true, insert, onLimit = () => {}}) => {
        let suggestions = [], options = [], selected = 0, range = null, active = true, queryKey = '', revision = 0;
        box.id ||= `chat-completions-${++sequence}`;
        box.setAttribute('role', 'listbox');
        input.setAttribute('aria-controls', box.id);
        input.setAttribute('aria-autocomplete', 'list');
        function hide() {
            revision++;
            suggestions = []; options = []; range = null; box.hidden = true; box.replaceChildren();
            input.setAttribute('aria-expanded', 'false');
        }
        function choose(suggestion) {
            if (!active || !range) return;
            if (insert) { insert(suggestion, range); return; }
            const before = input.value.slice(0, range.start), after = input.value.slice(range.end);
            const prefix = before && !/\s$/.test(before) ? ' ' : '';
            const suffix = after && !/^\s/.test(after) ? ' ' : '';
            const replacement = `${prefix}${suggestion.value}${suffix || ' '}`;
            if (before.length + replacement.length + after.length > input.maxLength) { onLimit(); return; }
            input.setRangeText(replacement, range.start, range.end, 'end');
            hide(); input.dispatchEvent(new Event('input', {bubbles: true})); input.focus();
        }
        function render() {
            box.replaceChildren();
            options = [];
            suggestions.forEach((suggestion, index) => {
                const option = document.createElement('button'); option.type = 'button';
                option.className = 'chat-emote-suggestion'; option.classList.toggle('active', index === selected);
                option.setAttribute('role', 'option'); option.setAttribute('aria-selected', String(index === selected));
                option.title = suggestion.description || suggestion.label;
                const visual = document.createElement(suggestion.kind === 'emote' ? 'img' : 'span');
                if (suggestion.kind === 'emote') {
                    visual.src = suggestion.url; visual.alt = '';
                    const larger = suggestion.url.includes('static-cdn.jtvnw.net/')
                        ? suggestion.url.replace(/\/2\.0$/, '/3.0') : suggestion.url.replace(/\/2x\.webp$/, '/3x.webp');
                    if (larger !== suggestion.url) visual.srcset = `${suggestion.url} 2x, ${larger} 3x`;
                } else { visual.className = 'chat-completion-icon'; visual.textContent = suggestion.kind === 'command' ? '/' : '@'; }
                const label = document.createElement('span'); label.textContent = suggestion.label;
                const detail = document.createElement('small'); detail.textContent = suggestion.detail;
                option.append(visual, label, detail);
                option.addEventListener('mousedown', event => event.preventDefault());
                option.addEventListener('click', () => choose(suggestion)); box.appendChild(option); options.push(option);
            });
            box.hidden = !suggestions.length; input.setAttribute('aria-expanded', String(!box.hidden));
            options[selected]?.scrollIntoView({block: 'nearest'});
        }
        function select(index) {
            const previous = options[selected], next = options[index];
            if (previous) { previous.classList.toggle('active', false); previous.setAttribute('aria-selected', 'false'); }
            selected = index;
            if (next) {
                next.classList.toggle('active', true); next.setAttribute('aria-selected', 'true');
                next.scrollIntoView({block: 'nearest'});
            }
        }
        function token() {
            if (input.selectionStart !== input.selectionEnd) return null;
            const before = input.value.slice(0, input.selectionStart);
            const command = before.match(/^\/([A-Za-z]*)$/), user = before.match(/(?:^|\s)@([A-Za-z0-9_]*)$/);
            const emote = before.match(/(?:^|\s):([A-Za-z0-9_+-]+)$/), match = command || user || emote;
            return match ? {kind: command ? 'command' : user ? 'user' : 'emote', query: match[1].toLocaleLowerCase(),
                start: input.selectionStart - match[1].length - 1, end: input.selectionStart} : null;
        }
        function update() {
            if (!active || !enabled()) { hide(); return; }
            const match = token(); if (!match) { hide(); return; }
            const key = `${match.kind}:${match.query}:${match.start}`;
            if (key !== queryKey) selected = 0; queryKey = key;
            if (match.kind === 'command') suggestions = getCommands().filter(command => command.name.includes(match.query));
            else if (match.kind === 'user') suggestions = getUsers().filter(user =>
                user.username.toLocaleLowerCase().includes(match.query) || (user.display_name || '').toLocaleLowerCase().includes(match.query))
                .map(user => ({kind: 'user', value: `@${user.username}`, label: user.username,
                    detail: user.display_name && user.display_name !== user.username ? user.display_name : 'USER', description: `Mention @${user.username}`}));
            else {
                const seen = new Set();
                suggestions = getEmotes().filter(emote => {
                    if (typeof emote.name !== 'string' || typeof emote.url !== 'string'
                        || !/^https:\/\/(?:static-cdn\.jtvnw\.net|cdn\.7tv\.app)\//.test(emote.url)
                        || seen.has(emote.name) || !emote.name.toLocaleLowerCase().includes(match.query)) return false;
                    seen.add(emote.name); return true;
                }).sort((a, b) => a.name.localeCompare(b.name, undefined, {sensitivity: 'variant'}))
                    .map(emote => ({kind: 'emote', value: emote.name, label: emote.name, detail: (emote.provider || 'twitch').toUpperCase(),
                        description: `${emote.name} · ${emote.group || (emote.provider || 'twitch').toUpperCase()}`, url: emote.url}));
            }
            range = {start: match.start, end: match.end}; selected = Math.min(selected, Math.max(0, suggestions.length - 1)); render();
        }
        function handleKey(event) {
            if (!active || event.isComposing || !enabled()) return false;
            if (event.key === 'Escape') {
                const open = !box.hidden; hide();
                if (open) { event.preventDefault(); event.stopPropagation?.(); }
                return open;
            }
            const match = token();
            if (event.key === 'Tab' && match && ((match.kind === 'emote' && !getEmotes().length) || (match.kind === 'user' && !getUsers().length))) {
                event.preventDefault(); const value = input.value, cursor = input.selectionStart, version = revision;
                Promise.resolve(match.kind === 'emote' ? loadEmotes() : loadUsers()).then(() => {
                    if (!active || revision !== version || input.value !== value || input.selectionStart !== cursor) return;
                    update(); if (suggestions.length) choose(suggestions[0]);
                }).catch(() => {});
                return true;
            }
            if (box.hidden || !suggestions.length) return false;
            if (event.key === 'Tab' || (event.key === 'Enter' && !event.shiftKey)) {
                event.preventDefault(); choose(suggestions[selected]); return true;
            }
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                select((selected + (event.key === 'ArrowDown' ? 1 : -1) + suggestions.length) % suggestions.length);
                return true;
            }
            return false;
        }
        const outside = event => { if (!box.contains(event.target) && event.target !== (input.element || input)) hide(); };
        document.addEventListener('click', outside); hide();
        return {update, handleKey, hide, get isOpen() { return !box.hidden; },
            destroy() {
                if (!active) return;
                active = false; document.removeEventListener('click', outside); hide();
            }};
    };
})();
