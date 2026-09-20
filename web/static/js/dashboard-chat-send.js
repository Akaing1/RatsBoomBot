(() => {
    const form = document.querySelector("[data-chat-composer]");
    if (!form) return;

    const messageInput = form.querySelector('[name="message"]');
    const sendButton = form.querySelector(".chat-send-button");
    const status = form.querySelector("[data-chat-send-status]");
    const targets = Array.from(form.querySelectorAll("[data-chat-target]"));
    const emoteToggle = form.querySelector("[data-emote-toggle]");
    const emotePicker = form.querySelector("[data-emote-picker]");
    const emoteSearch = form.querySelector("[data-emote-search]");
    const emoteGroup = form.querySelector("[data-emote-group]");
    const emoteChannels = form.querySelector("[data-emote-channels]");
    const seventvButton = form.querySelector("[data-emote-seventv]");
    const emoteGrid = form.querySelector("[data-emote-grid]");
    const emoteCount = form.querySelector("[data-emote-count]");
    const emoteNote = form.querySelector("[data-emote-note]");
    const suggestionBox = form.querySelector("[data-emote-suggestions]");
    const replyContext = form.querySelector("[data-reply-context]");
    const replyMessageId = form.querySelector("[data-reply-message-id]");
    const replyName = form.querySelector("[data-reply-name]");
    const replyPreview = form.querySelector("[data-reply-preview]");
    const replyCancel = form.querySelector("[data-reply-cancel]");
    let selectedTarget = "twitch";
    let sending = false;
    let emotes = [];
    let users = [];
    let catalogLoadedAt = 0;
    let catalogPromise = null;
    let usersLoadedAt = 0;
    let usersPromise = null;
    let suggestions = [];
    let selectedSuggestion = 0;
    let completionRange = null;
    let selectedGroup = null;
    let personalGroup = "";
    let statusFadeTimer = null;
    const messageHistoryKey = `ratsboombot:chat-message-history:${form.dataset.channelId || "channel"}`;
    let messageHistory = [];
    let historyIndex = 0;
    let historyDraft = "";
    let browsingHistory = false;
    const messageHistoryLimit = 20;
    try {
        const storedHistory = JSON.parse(window.sessionStorage.getItem(messageHistoryKey) || "[]");
        if (Array.isArray(storedHistory)) {
            messageHistory = storedHistory.filter(value => typeof value === "string" && value).slice(-messageHistoryLimit);
        }
    } catch (_error) {
        messageHistory = [];
    }
    historyIndex = messageHistory.length;
    const twitchCommands = [
        ["announce", "[message]", "Send a highlighted announcement."],
        ["announceblue", "[message]", "Send a blue announcement."],
        ["announcegreen", "[message]", "Send a green announcement."],
        ["announceorange", "[message]", "Send an orange announcement."],
        ["announcepurple", "[message]", "Send a purple announcement."],
        ["ban", "<username> [reason]", "Permanently ban a user."],
        ["clear", "", "Clear the chat history."],
        ["commercial", "<seconds>", "Run a commercial break."],
        ["emoteonly", "", "Enable emote-only chat."],
        ["emoteonlyoff", "", "Disable emote-only chat."],
        ["followers", "[duration]", "Enable followers-only chat."],
        ["followersoff", "", "Disable followers-only chat."],
        ["marker", "[description]", "Add a stream marker."],
        ["mod", "<username>", "Add a channel moderator."],
        ["raid", "<channel>", "Start a raid."],
        ["shoutout", "<username>", "Send a channel shoutout."],
        ["slow", "[seconds]", "Enable slow mode."],
        ["slowoff", "", "Disable slow mode."],
        ["subscribers", "", "Enable subscribers-only chat."],
        ["subscribersoff", "", "Disable subscribers-only chat."],
        ["timeout", "<username> [seconds] [reason]", "Temporarily ban a user."],
        ["unban", "<username>", "Remove a ban or timeout."],
        ["unmod", "<username>", "Remove a channel moderator."],
        ["unraid", "", "Cancel the current raid."],
        ["unvip", "<username>", "Remove a VIP."],
        ["vip", "<username>", "Add a VIP."],
        ["warn", "<username> <reason>", "Warn a user."],
        ["uniquechat", "", "Require unique chat messages."],
        ["uniquechatoff", "", "Disable unique chat mode."]
    ].map(([name, usage, description]) => ({
        kind: "command",
        name,
        value: `/${name}`,
        label: `/${name}${usage ? ` ${usage}` : ""}`,
        detail: "COMMAND",
        description
    })).sort((left, right) => left.name.localeCompare(right.name));

    function showStatus(message, tone = "", fadeAfterDelay = false) {
        window.clearTimeout(statusFadeTimer);
        window.clearTimeout(status._connectionFadeTimer);
        status.className = `chat-send-status${tone ? ` ${tone}` : ""}`;
        status.textContent = message;
        if (fadeAfterDelay) {
            statusFadeTimer = window.setTimeout(() => {
                if (status.dataset.connectionState === "disconnected") {
                    status.className = "chat-send-status error";
                    status.textContent = "Not connected";
                } else {
                    status.classList.add("is-fading");
                }
            }, 3000);
        }
    }

    function saveMessageHistory() {
        try {
            window.sessionStorage.setItem(messageHistoryKey, JSON.stringify(messageHistory));
        } catch (_error) {
            // History remains available until this page is closed when storage is unavailable.
        }
    }

    function rememberMessage(message) {
        if (!message) return;
        if (messageHistory.at(-1) !== message) {
            messageHistory.push(message);
            messageHistory = messageHistory.slice(-messageHistoryLimit);
            saveMessageHistory();
        }
        historyIndex = messageHistory.length;
        browsingHistory = false;
    }

    function navigateMessageHistory(direction) {
        const caretAtStart = messageInput.selectionStart === 0 && messageInput.selectionEnd === 0;
        const caretAtEnd = messageInput.selectionStart === messageInput.value.length
            && messageInput.selectionEnd === messageInput.value.length;
        if ((direction < 0 && !caretAtStart) || (direction > 0 && !caretAtEnd)) return false;
        if (!messageHistory.length || (direction > 0 && !browsingHistory)) return false;

        if (!browsingHistory) {
            historyDraft = messageInput.value;
            historyIndex = messageHistory.length;
            browsingHistory = true;
        }

        historyIndex = Math.max(0, Math.min(messageHistory.length, historyIndex + direction));
        if (historyIndex === messageHistory.length) {
            messageInput.value = historyDraft;
            browsingHistory = false;
        } else {
            messageInput.value = messageHistory[historyIndex];
        }
        const caret = direction < 0 ? 0 : messageInput.value.length;
        messageInput.setSelectionRange(caret, caret);
        updateSuggestions();
        return true;
    }

    function groupKey(emote) {
        return emote.group_key || `${emote.provider}:other`;
    }

    function orderedGroups() {
        const groups = new Map();
        emotes.forEach(emote => groups.set(groupKey(emote), {
            key: groupKey(emote), label: emote.group || emote.provider.toUpperCase(), image: emote.group_image || ""
        }));
        const rank = key => key === personalGroup ? 0 : key === "7tv" ? 3 : key === "twitch:global" ? 2 : 1;
        return Array.from(groups.values()).sort((a, b) => rank(a.key) - rank(b.key)
            || a.label.localeCompare(b.label, undefined, {sensitivity: "base"}));
    }

    function setGroupIcon(button, group) {
        button.replaceChildren();
        button.title = group.key === personalGroup ? `Your channel · ${group.label}` : group.label;
        button.setAttribute("aria-label", button.title);
        const fallback = document.createElement("span");
        fallback.textContent = group.key === "7tv" ? "7TV" : group.label.slice(0, 2);
        const image = document.createElement("img");
        image.alt = "";
        image.src = group.key === "7tv" ? "/static/img/7tv.svg"
            : /^https:\/\/[^/]*jtvnw\.net\//.test(group.image) ? group.image
            : "/static/img/twitch.svg";
        image.addEventListener("error", () => image.replaceWith(fallback), {once: true});
        button.appendChild(image);
    }

    const trustedEmoteUrl = /^https:\/\/(?:static-cdn\.jtvnw\.net|cdn\.7tv\.app)\//;

    function emoteSrcset(url) {
        const larger = url.includes("static-cdn.jtvnw.net/")
            ? url.replace(/\/2\.0$/, "/3.0")
            : url.replace(/\/2x\.webp$/, "/3x.webp");
        return larger === url ? "" : `${url} 2x, ${larger} 3x`;
    }

    function hideSuggestions() {
        suggestionBox.hidden = true;
        suggestionBox.replaceChildren();
        suggestions = [];
        completionRange = null;
    }

    function insertValue(value, range = null) {
        const start = range?.start ?? messageInput.selectionStart;
        const end = range?.end ?? messageInput.selectionEnd;
        const before = messageInput.value.slice(0, start);
        const after = messageInput.value.slice(end);
        const prefix = before && !/\s$/.test(before) ? " " : "";
        const suffix = after && !/^\s/.test(after) ? " " : "";
        const replacement = `${prefix}${value}${suffix || " "}`;
        messageInput.setRangeText(replacement, start, end, "end");
        emotePicker.hidden = true;
        emoteToggle.setAttribute("aria-expanded", "false");
        hideSuggestions();
        messageInput.dispatchEvent(new Event("input", {bubbles: true}));
        messageInput.focus();
    }

    function insertEmote(name, range = null) {
        insertValue(name, range);
    }

    function insertSuggestion(suggestion) {
        insertValue(suggestion.value, completionRange);
    }

    function renderPicker() {
        const query = emoteSearch.value.trim().toLocaleLowerCase();
        const matches = emotes.filter(emote =>
            (selectedGroup === null || groupKey(emote) === selectedGroup)
            && (!query || emote.name.toLocaleLowerCase().includes(query))
        ).sort((left, right) => left.name.localeCompare(right.name, undefined, {sensitivity: "variant"}));
        emoteGrid.replaceChildren();
        emoteGrid.scrollTop = 0;
        emoteCount.textContent = `${matches.length} emote${matches.length === 1 ? "" : "s"}`;

        orderedGroups().forEach(group => {
            const items = matches.filter(emote => groupKey(emote) === group.key);
            if (!items.length) return;
            const section = document.createElement("section");
            section.className = "chat-emote-section";
            const heading = document.createElement("h4");
            heading.textContent = group.key === personalGroup ? `Your channel · ${group.label}` : group.label;
            const grid = document.createElement("div");
            grid.className = "chat-emote-section-grid";
            items.forEach(emote => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "chat-emote-option";
            button.title = `${emote.name} · ${emote.group || emote.provider.toUpperCase()}`;
            button.setAttribute("aria-label", button.title);

            const image = document.createElement("img");
            image.src = emote.url;
            image.srcset = emoteSrcset(emote.url);
            image.alt = "";
            image.loading = "lazy";
            image.decoding = "async";

            const label = document.createElement("span");
            label.textContent = emote.name;
            button.append(image, label);
            button.addEventListener("click", () => insertEmote(emote.name));
            grid.appendChild(button);
            });
            section.append(heading, grid);
            emoteGrid.appendChild(section);
        });
    }

    function renderGroupOptions() {
        const groups = orderedGroups();
        if (!groups.some(group => group.key === selectedGroup)) selectedGroup = null;
        emoteChannels.replaceChildren();
        groups.filter(group => group.key !== "7tv").forEach(group => {
                const key = group.key;
                const button = document.createElement("button");
                button.type = "button";
                button.className = "chat-emote-section-button";
                button.dataset.emoteSection = key;
                setGroupIcon(button, group);
                button.addEventListener("click", () => selectEmoteGroup(key));
                emoteChannels.appendChild(button);
            });
        seventvButton.dataset.emoteSection = "7tv";
        setGroupIcon(seventvButton, {key: "7tv", label: "7TV", image: ""});
        updateGroupButtons();
    }

    function updateGroupButtons() {
        emoteGroup.querySelectorAll("[data-emote-section]").forEach(button => {
            button.setAttribute("aria-pressed", String(button.dataset.emoteSection === selectedGroup));
        });
    }

    function selectEmoteGroup(key) {
        selectedGroup = selectedGroup === key ? null : key;
        updateGroupButtons();
        renderPicker();
    }

    async function loadEmotes(force = false) {
        if (!force && emotes.length && Date.now() - catalogLoadedAt < 30000) return;
        if (catalogPromise) return catalogPromise;

        catalogPromise = (async () => {
          try {
            const response = await fetch("/channel/api/chat/emotes");
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || "Emotes are unavailable.");

            emotes = (Array.isArray(payload.emotes) ? payload.emotes : []).filter(emote =>
                typeof emote?.name === "string" && typeof emote?.url === "string" && trustedEmoteUrl.test(emote.url)
            );
            catalogLoadedAt = Date.now();
            personalGroup = payload.personal_group_key || "";
            renderGroupOptions();
            emoteNote.replaceChildren();
            emoteNote.classList.toggle("requires-reconnect", Boolean(payload.twitch_reconnect_required));
            if (payload.twitch_reconnect_required) {
                emoteNote.append("Other channel emotes need additional Twitch permission. ");
                const reconnect = document.createElement("a");
                reconnect.href = "/connect/twitch";
                reconnect.textContent = "Reconnect Twitch to load them";
                reconnect.title = "Authorize access to every emote this Twitch account can use";
                emoteNote.append(reconnect, ".");
            } else {
                emoteNote.textContent = "Tip: type : followed by an emote name, then press Tab.";
            }
            renderPicker();
            updateSuggestions();
          } catch (error) {
            emoteNote.textContent = error.message || "Emotes are unavailable.";
          } finally {
            catalogPromise = null;
          }
        })();

        return catalogPromise;
    }

    async function loadUsers(force = false) {
        if (!force && usersLoadedAt && Date.now() - usersLoadedAt < 30000) return;
        if (usersPromise) return usersPromise;

        usersPromise = (async () => {
            try {
                const response = await fetch("/channel/api/chat/users", {cache: "no-store"});
                const payload = await response.json();
                if (!response.ok) throw new Error(payload.detail || "Users are unavailable.");
                users = (Array.isArray(payload.users) ? payload.users : []).filter(user =>
                    typeof user?.username === "string" && /^[A-Za-z0-9_]+$/.test(user.username)
                );
                usersLoadedAt = Date.now();
                updateSuggestions();
            } catch (_error) {
                users = [];
            } finally {
                usersPromise = null;
            }
        })();

        return usersPromise;
    }

    function renderSuggestions() {
        suggestionBox.replaceChildren();

        suggestions.forEach((suggestion, index) => {
            const option = document.createElement("button");
            option.type = "button";
            option.className = "chat-emote-suggestion";
            option.classList.toggle("active", index === selectedSuggestion);
            option.setAttribute("role", "option");
            option.setAttribute("aria-selected", String(index === selectedSuggestion));
            option.title = suggestion.description || suggestion.label;

            let visual;
            if (suggestion.kind === "emote") {
                visual = document.createElement("img");
                visual.src = suggestion.url;
                visual.srcset = emoteSrcset(suggestion.url);
                visual.alt = "";
            } else {
                visual = document.createElement("span");
                visual.className = "chat-completion-icon";
                visual.textContent = suggestion.kind === "command" ? "/" : "@";
            }
            const label = document.createElement("span");
            label.textContent = suggestion.label;
            const detail = document.createElement("small");
            detail.textContent = suggestion.detail;
            option.append(visual, label, detail);
            option.addEventListener("mousedown", event => event.preventDefault());
            option.addEventListener("click", () => insertSuggestion(suggestion));
            suggestionBox.appendChild(option);
        });

        suggestionBox.hidden = !suggestions.length;
        suggestionBox.querySelector(".chat-emote-suggestion.active")?.scrollIntoView({block: "nearest"});
    }

    function updateSuggestions() {
        if (selectedTarget === "youtube") {
            hideSuggestions();
            return;
        }

        const cursor = messageInput.selectionStart;
        if (cursor !== messageInput.selectionEnd) {
            hideSuggestions();
            return;
        }

        const inputBeforeCursor = messageInput.value.slice(0, cursor);
        const commandMatch = inputBeforeCursor.match(/^\/([A-Za-z]*)$/);
        const userMatch = inputBeforeCursor.match(/(?:^|\s)@([A-Za-z0-9_]*)$/);
        const emoteMatch = inputBeforeCursor.match(/(?:^|\s):([A-Za-z0-9_+-]+)$/);
        const match = commandMatch || userMatch || emoteMatch;
        if (!match) {
            hideSuggestions();
            return;
        }

        const query = match[1].toLocaleLowerCase();
        if (commandMatch) {
            suggestions = twitchCommands.filter(command => command.name.includes(query));
        } else if (userMatch) {
            if (!usersLoadedAt && !usersPromise) loadUsers();
            suggestions = users.filter(user =>
                user.username.toLocaleLowerCase().includes(query)
                || user.display_name.toLocaleLowerCase().includes(query)
            ).map(user => ({
                kind: "user",
                value: `@${user.username}`,
                label: user.username,
                detail: user.display_name !== user.username ? user.display_name : "USER",
                description: `Mention @${user.username}`
            }));
        } else {
            const seen = new Set();
            suggestions = emotes.filter(emote => {
                const key = emote.name.toLocaleLowerCase();
                if (seen.has(emote.name) || !key.includes(query)) return false;
                seen.add(emote.name);
                return true;
            }).sort((left, right) => left.name.localeCompare(right.name, undefined, {sensitivity: "variant"}))
                .map(emote => ({
                    kind: "emote",
                    value: emote.name,
                    label: emote.name,
                    detail: emote.provider.toUpperCase(),
                    description: `${emote.name} · ${emote.group || emote.provider.toUpperCase()}`,
                    url: emote.url
                }));
        }
        completionRange = {start: cursor - match[1].length - 1, end: cursor};
        selectedSuggestion = Math.min(selectedSuggestion, Math.max(0, suggestions.length - 1));
        renderSuggestions();
    }

    function selectTarget(target) {
        const selected = targets.find(button => button.dataset.chatTarget === target && !button.disabled);
        if (!selected) return;
        selectedTarget = target;
        if (target === "youtube") clearReply();
        targets.forEach(button => {
            const active = button === selected;
            button.classList.toggle("active", active);
            button.setAttribute("aria-pressed", String(active));
        });
        emoteToggle.disabled = target === "youtube";
        if (target === "youtube") {
            emotePicker.hidden = true;
            emoteToggle.setAttribute("aria-expanded", "false");
            hideSuggestions();
        }
    }

    targets.forEach(button => button.addEventListener("click", () => selectTarget(button.dataset.chatTarget)));

    function clearReply() {
        replyMessageId.value = "";
        replyName.textContent = "";
        replyPreview.textContent = "";
        replyContext.hidden = true;
    }

    function beginReply({messageId = "", name = "", message = ""} = {}) {
        if (!messageId.startsWith("twitch:")) return;
        replyMessageId.value = messageId;
        replyName.textContent = `Replying to ${name || "message"}`;
        replyPreview.textContent = message;
        replyContext.hidden = false;
        if (selectedTarget === "youtube") selectTarget("twitch");
        messageInput.focus();
    }

    replyCancel.addEventListener("click", () => {
        clearReply();
        messageInput.focus();
    });
    document.addEventListener("dashboard-chat-reply", event => beginReply(event.detail));
    document.addEventListener("keydown", event => {
        if (event.key !== "Escape" || !replyMessageId.value) return;
        event.preventDefault();
        hideSuggestions();
        clearReply();
        messageInput.focus();
    });

    emoteToggle.addEventListener("click", async () => {
        const opening = emotePicker.hidden;
        emotePicker.hidden = !opening;
        emoteToggle.setAttribute("aria-expanded", String(opening));
        if (opening) {
            await loadEmotes();
            emoteSearch.focus();
        }
    });

    emoteSearch.addEventListener("input", renderPicker);
    seventvButton.addEventListener("click", () => selectEmoteGroup("7tv"));
    messageInput.addEventListener("focus", () => {
        loadEmotes();
        loadUsers();
    });
    messageInput.addEventListener("input", () => {
        browsingHistory = false;
        historyIndex = messageHistory.length;
        updateSuggestions();
    });
    messageInput.addEventListener("click", updateSuggestions);

    messageInput.addEventListener("keydown", event => {
        if (event.key === "Escape" && replyMessageId.value) {
            event.preventDefault();
            hideSuggestions();
            clearReply();
            return;
        }
        if (suggestionBox.hidden && (event.key === "ArrowUp" || event.key === "ArrowDown")) {
            const direction = event.key === "ArrowUp" ? -1 : 1;
            if (navigateMessageHistory(direction)) {
                event.preventDefault();
                return;
            }
        }
        const inputBeforeCursor = messageInput.value.slice(0, messageInput.selectionStart);
        const needsEmotes = !emotes.length && /(?:^|\s):[A-Za-z0-9_+-]+$/.test(inputBeforeCursor);
        const needsUsers = !usersLoadedAt && /(?:^|\s)@[A-Za-z0-9_]*$/.test(inputBeforeCursor);
        if (event.key === "Tab" && (needsEmotes || needsUsers)) {
            event.preventDefault();
            const loader = needsEmotes ? loadEmotes() : loadUsers();
            loader.then(() => {
                updateSuggestions();
                if (suggestions.length) insertSuggestion(suggestions[0]);
            });
            return;
        }

        if (!suggestionBox.hidden && suggestions.length) {
            if (event.key === "Tab" || (event.key === "Enter" && !event.shiftKey)) {
                event.preventDefault();
                insertSuggestion(suggestions[selectedSuggestion]);
                return;
            }
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                const direction = event.key === "ArrowDown" ? 1 : -1;
                selectedSuggestion = (selectedSuggestion + direction + suggestions.length) % suggestions.length;
                renderSuggestions();
                return;
            }
            if (event.key === "Escape") {
                event.preventDefault();
                hideSuggestions();
                return;
            }
        }

        if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
            event.preventDefault();
            form.requestSubmit();
        }
    });

    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (sending || !messageInput.value.trim()) return;

        sending = true;
        sendButton.disabled = true;
        showStatus("Sending…");

        const outgoingMessage = messageInput.value.trim();
        const data = new FormData(form);
        data.set("message", outgoingMessage);
        data.set("target", selectedTarget);

        try {
            const response = await fetch("/channel/api/chat/send", {method: "POST", body: data});
            const result = await response.json();

            if (!response.ok) throw new Error(result.detail || "The message could not be sent.");

            const sent = (result.sent || []).map(platform => platform === "youtube" ? "YouTube" : "Twitch");
            const failures = Object.values(result.errors || {});
            rememberMessage(outgoingMessage);
            messageInput.value = "";
            historyDraft = "";
            clearReply();
            hideSuggestions();
            showStatus(
                result.message || (failures.length ? `Sent to ${sent.join(" and ")}. ${failures.join(" ")}` : `Sent to ${sent.join(" and ")}.`),
                failures.length ? "warning" : "success",
                true
            );
        } catch (error) {
            showStatus(error.message || "The message could not be sent.", "error", true);
        } finally {
            sending = false;
            sendButton.disabled = false;
            messageInput.focus();
        }
    });

    document.addEventListener("click", event => {
        if (!emotePicker.hidden && !emotePicker.contains(event.target) && !emoteToggle.contains(event.target)) {
            emotePicker.hidden = true;
            emoteToggle.setAttribute("aria-expanded", "false");
        }
        if (!suggestionBox.hidden && !suggestionBox.contains(event.target) && event.target !== messageInput) {
            hideSuggestions();
        }
    });

    loadEmotes();
    loadUsers();
})();
