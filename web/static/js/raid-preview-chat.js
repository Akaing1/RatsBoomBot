(() => {
    let pickerSequence = 0;
    window.createRaidPreviewChat = (host, channel, csrfToken) => {
        const element = (tag, className, text) => {
            const node = document.createElement(tag); node.className = className;
            if (text) node.textContent = text;
            return node;
        };
        const heading = element("header", "raid-preview-chat-heading", "Chat");
        const status = element("p", "chat-send-status", "Connecting…"); status.setAttribute("role", "status");
        const reconnect = element("a", "raid-preview-chat-reconnect", "Reconnect Twitch");
        reconnect.href = "/connect"; reconnect.target = "_blank"; reconnect.rel = "noopener noreferrer"; reconnect.hidden = true;
        const shell = element("div", "live-chat-feed-shell");
        const messages = element("div", "live-chat-feed raid-preview-chat-messages");
        messages.setAttribute("aria-label", `${channel.display_name || channel.login} chat`);
        shell.append(messages);
        const form = element("form", "dashboard-chat-composer raid-preview-chat-compose");
        let input = element("textarea", ""); input.rows = 1; input.maxLength = 500;
        input.placeholder = "Send a message…"; input.setAttribute("aria-label", "Message");
        const send = element("button", "button primary chat-send-button raid-preview-chat-send"); send.type = "submit";
        send.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 3 21 12 4 21 8 12Z"/></svg>';
        send.setAttribute("aria-label", "Send message"); send.title = "Send";
        const entry = element("div", "chat-message-entry raid-preview-chat-entry");
        entry.append(input, status); form.append(entry, send);
        const suggestions = element("div", "chat-emote-suggestions"); suggestions.hidden = true;
        entry.append(suggestions);
        const emoteToggle = element("button", "chat-emote-toggle"); emoteToggle.type = "button";
        emoteToggle.title = "Emotes"; emoteToggle.setAttribute("aria-label", "Open emote picker");
        emoteToggle.setAttribute("aria-expanded", "false");
        const smile = element("span", "", "☺"); smile.setAttribute("aria-hidden", "true"); emoteToggle.append(smile);
        const picker = element("div", "chat-emote-picker"); picker.hidden = true;
        picker.id = `raid-preview-emotes-${++pickerSequence}`;
        emoteToggle.setAttribute("aria-controls", picker.id);
        entry.append(emoteToggle); form.append(picker);
        host.replaceChildren(heading, shell, form, reconnect);
        const feed = window.createTwitchPreviewFeed(messages);
        const url = new URL("/channel/api/raid-browser/chat/stream", window.location.origin);
        url.searchParams.set("target_id", channel.id);
        const source = new EventSource(url);
        let closed = false, streamStopped = false;
        function stopStream() {
            if (streamStopped) return;
            streamStopped = true;
            source.onmessage = source.onerror = null;
            source.close();
        }
        let emotes = [], emotesLoadedAt = 0, emoteRequest = null, emotePromise = null, emoteError = "";
        input = window.createChatEmoteInput?.({input, getEmotes: () => emotes,
            onLimit: () => composer.showStatus("Messages can contain up to 500 characters.", "warning", true)}) || input;
        let personalGroup = "", renderedEmotes = null;
        const pickerView = window.createChatEmotePicker({picker, getEmotes: () => emotes,
            getPersonalGroup: () => personalGroup, insert: insertEmote});
        const emoteSearch = pickerView.search, emoteNote = pickerView.note;
        function closePicker() {
            picker.hidden = true; emoteToggle.setAttribute("aria-expanded", "false");
        }
        function insertEmote(name) {
            if (closed) return;
            const start = input.selectionStart, end = input.selectionEnd;
            const before = input.value.slice(0, start), after = input.value.slice(end);
            const replacement = `${before && !/\s$/.test(before) ? " " : ""}${name}${/^\s/.test(after) ? "" : " "}`;
            if (before.length + replacement.length + after.length > input.maxLength) {
                composer.showStatus("Messages can contain up to 500 characters.", "warning", true); return;
            }
            input.setRangeText(replacement, start, end, "end");
            closePicker(); autocomplete.hide();
            input.dispatchEvent(new Event("input", {bubbles: true})); input.focus();
        }
        function renderEmotes() {
            if (closed || picker.hidden) return;
            if (renderedEmotes !== emotes) {
                pickerView.renderGroups(); pickerView.render();
                renderedEmotes = emotes;
            }
            emoteNote.textContent = emoteError || "Tip: type : followed by an emote name, then press Tab.";
        }
        const chatters = new Map();
        chatters.set(channel.login.toLowerCase(), {username: channel.login, display_name: channel.display_name || channel.login});
        async function loadEmotes() {
            if (closed || (emotesLoadedAt && Date.now() - emotesLoadedAt < 30000)) return;
            if (emotePromise) return emotePromise;
            emoteRequest = new AbortController();
            emotePromise = (async () => {
                try {
                    const catalogUrl = new URL('/channel/api/raid-browser/chat/emotes', window.location.origin);
                    catalogUrl.searchParams.set('target_id', channel.id);
                    const response = await fetch(catalogUrl, {signal: emoteRequest.signal, cache: 'no-store'});
                    const catalog = await response.json();
                    if (closed) return;
                    if (!response.ok) throw new Error("Emotes are unavailable.");
                    emotes = (Array.isArray(catalog.emotes) ? catalog.emotes : []).filter(emote =>
                        typeof emote?.name === "string" && /^https:\/\/(?:static-cdn\.jtvnw\.net|cdn\.7tv\.app)\//.test(emote.url || ""));
                    emotesLoadedAt = Date.now(); emoteError = "";
                    input.refreshEmotes?.();
                    personalGroup = catalog.personal_group_key || "";
                    renderEmotes();
                    autocomplete.update();
                } catch (_) { emoteError = "Emotes are unavailable."; renderEmotes(); }
                finally { emotePromise = null; emoteRequest = null; }
            })();
            return emotePromise;
        }
        const composer = window.createChatComposer({form, input, sendButton: send, status,
            autocomplete: {box: suggestions, getEmotes: () => emotes,
                getUsers: () => [...chatters.values()], loadEmotes},
            async send(message, signal) {
                const response = await fetch("/channel/api/raid-browser/chat/send", {method: "POST", signal,
                    body: new URLSearchParams({target_id: channel.id, message, csrf_token: csrfToken})});
                const payload = await response.json();
                if (!response.ok) throw new Error(payload.detail || "Message couldn't be sent.");
                // No local echo: the real chat event confirms delivery.
            }});
        const autocomplete = composer.autocomplete;
        function fitSuggestions() {
            if (closed) return;
            const available = host.clientHeight - form.offsetHeight - heading.offsetHeight - 16;
            if (available > 0) {
                suggestions.style.maxHeight = `${Math.min(240, available)}px`;
                picker.style.maxHeight = `${Math.min(380, available)}px`;
            }
        }
        async function toggleEmotes() {
            if (closed) return;
            if (!picker.hidden) { closePicker(); return; }
            autocomplete.hide(); picker.hidden = false; emoteToggle.setAttribute("aria-expanded", "true");
            fitSuggestions(); emoteNote.textContent = "Loading emotes…";
            await loadEmotes();
            if (closed || picker.hidden) return;
            renderEmotes(); emoteSearch.focus();
        }
        function onOutside(event) {
            if (!picker.hidden && !picker.contains(event.target) && !emoteToggle.contains(event.target)) closePicker();
        }
        function onPickerKey(event) {
            if (event.key !== "Escape" || picker.hidden) return;
            event.preventDefault(); event.stopPropagation(); closePicker(); emoteToggle.focus();
        }
        emoteToggle.addEventListener("mousedown", event => event.preventDefault());
        emoteToggle.addEventListener("click", toggleEmotes);
        document.addEventListener("pointerdown", onOutside);
        host.addEventListener("keydown", onPickerKey);
        const suggestionObserver = window.ResizeObserver ? new window.ResizeObserver(fitSuggestions) : null;
        suggestionObserver?.observe(host); suggestionObserver?.observe(form);
        function showStatus(text, error = false, fade = true) {
            composer.showStatus(text, error ? "error" : "", fade);
        }
        showStatus("Connecting…", false, false);
        source.onmessage = event => {
            if (closed || streamStopped) return;
            try {
                const payload = JSON.parse(event.data);
                if (payload.type === "status") {
                    showStatus(payload.text, Boolean(payload.error), !payload.error);
                    reconnect.hidden = !payload.text.startsWith("Reconnect Twitch");
                    if (payload.terminal) stopStream();
                } else {
                    if (payload.type === 'message' && /^[A-Za-z0-9_]{1,25}$/.test(payload.message?.username || '')) {
                        const message = payload.message;
                        chatters.set(message.username.toLowerCase(), {username: message.username, display_name: message.display_name || message.username});
                        if (chatters.size > 200) chatters.delete(chatters.keys().next().value);
                        if (input.value.includes('@')) autocomplete.update();
                    }
                    feed.receive(payload);
                }
            } catch (_) { /* Ignore malformed events without resetting the chat. */ }
        };
        source.onerror = () => { if (!closed && !streamStopped) showStatus("Chat disconnected. Retrying…", true, false); };
        function onFocus() { fitSuggestions(); loadEmotes(); }
        input.addEventListener('focus', onFocus);
        return {destroy() {
            if (closed) return;
            closed = true;
            composer.destroy(); pickerView.destroy(); stopStream(); emoteRequest?.abort();
            input.removeEventListener('focus', onFocus);
            document.removeEventListener("pointerdown", onOutside); host.removeEventListener("keydown", onPickerKey);
            suggestionObserver?.disconnect(); feed.destroy(); host.replaceChildren();
        }};
    };
})();
