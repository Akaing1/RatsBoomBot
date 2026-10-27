(() => {
    const form = document.querySelector("[data-chat-composer]");
    if (!form) return;

    let messageInput = form.querySelector('[name="message"]');
    const defaultMessagePlaceholder = messageInput.placeholder;
    const sendButton = form.querySelector(".chat-send-button");
    const status = form.querySelector("[data-chat-send-status]");
    const targetButton = form.querySelector("[data-chat-target-cycle]");
    const emoteToggle = form.querySelector("[data-emote-toggle]");
    const emotePicker = form.querySelector("[data-emote-picker]");
    const pickerView = window.createChatEmotePicker({picker: emotePicker, getEmotes: () => emotes,
        getPersonalGroup: () => personalGroup, insert: name => insertValue(name)});
    const emoteSearch = pickerView.search;
    const emoteNote = pickerView.note;
    const suggestionBox = form.querySelector("[data-emote-suggestions]");
    const replyContext = form.querySelector("[data-reply-context]");
    const replyMessageId = form.querySelector("[data-reply-message-id]");
    const replyName = form.querySelector("[data-reply-name]");
    const replyPreview = form.querySelector("[data-reply-preview]");
    const replyCancel = form.querySelector("[data-reply-cancel]");
    let selectedTarget = "twitch";
    let emotes = [];
    let users = [];
    let catalogLoadedAt = 0;
    let catalogPromise = null;
    let usersLoadedAt = 0;
    let usersPromise = null;
    let autocomplete = null;
    let personalGroup = "";
    let composer = null;
    messageInput = window.createChatEmoteInput?.({input: messageInput, getEmotes: () => emotes,
        enabled: () => selectedTarget !== "youtube",
        onLimit: () => composer?.showStatus("Messages can contain up to 500 characters.", "warning", true)}) || messageInput;
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
        composer.showStatus(message, tone, fadeAfterDelay);
    }

    function reportSendFailure(platform, message) {
        document.dispatchEvent(new CustomEvent("dashboard-chat-send-error", {detail: {platform, message}}));
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
        resizeMessageInput();
        updateSuggestions();
        return true;
    }

    const trustedEmoteUrl = /^https:\/\/(?:static-cdn\.jtvnw\.net|cdn\.7tv\.app)\//;

    function hideSuggestions() {
        autocomplete?.hide();
    }

    function insertValue(value, range = null) {
        const start = range?.start ?? messageInput.selectionStart;
        const end = range?.end ?? messageInput.selectionEnd;
        const before = messageInput.value.slice(0, start);
        const after = messageInput.value.slice(end);
        const prefix = before && !/\s$/.test(before) ? " " : "";
        const suffix = after && !/^\s/.test(after) ? " " : "";
        const replacement = `${prefix}${value}${suffix || " "}`;
        if (before.length + replacement.length + after.length > messageInput.maxLength) {
            showStatus("Messages can contain up to 500 characters.", "warning", true);
            return;
        }
        messageInput.setRangeText(replacement, start, end, "end");
        emotePicker.hidden = true;
        emoteToggle.setAttribute("aria-expanded", "false");
        hideSuggestions();
        messageInput.dispatchEvent(new Event("input", {bubbles: true}));
        messageInput.focus();
    }

    function renderPicker() { pickerView.render(); }

    function renderGroupOptions() { pickerView.renderGroups(); }

    async function loadEmotes(force = false) {
        if (!force && catalogLoadedAt && Date.now() - catalogLoadedAt < 30000) return;
        if (catalogPromise) return catalogPromise;

        catalogPromise = (async () => {
          try {
            const response = await fetch((globalThis.document?.body?.dataset?.channelRoot || "/channel") + '/api/chat/emotes');
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || "Emotes are unavailable.");

            emotes = (Array.isArray(payload.emotes) ? payload.emotes : []).filter(emote =>
                typeof emote?.name === "string" && typeof emote?.url === "string" && trustedEmoteUrl.test(emote.url)
            );
            catalogLoadedAt = Date.now();
            messageInput.refreshEmotes?.();
            personalGroup = payload.personal_group_key || "";
            renderGroupOptions();
            emoteNote.replaceChildren();
            emoteNote.classList.toggle("requires-reconnect", Boolean(payload.twitch_reconnect_required));
            if (payload.twitch_reconnect_required) {
                emoteNote.append("Other channel emotes need additional Twitch permission. ");
                const reconnect = document.createElement("a");
                reconnect.href = globalThis.document?.body?.dataset?.channelRoot?.startsWith("/me/mod/") ? `${globalThis.document?.body?.dataset?.channelRoot}/connect` : "/connect/twitch";
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
                const response = await fetch((globalThis.document?.body?.dataset?.channelRoot || "/channel") + '/api/chat/users', {cache: "no-store"});
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

    function updateSuggestions() { autocomplete.update(); }

    function selectTarget(target) {
        targetSelector.select(target);
    }
    const targetSelector = window.createChatTargetSelector({form, button: targetButton, input: messageInput,
        onLayout: () => composer?.resize(),
        youtubeAvailable: form.dataset.youtubeConnected === "true",
        onChange(target) {
            selectedTarget = target;
            messageInput.refreshEmotes?.();
            emoteToggle.disabled = target === "youtube";
            if (target === "youtube") {
                clearReply(); emotePicker.hidden = true;
                emoteToggle.setAttribute("aria-expanded", "false"); hideSuggestions();
            }
        }});

    function clearReply() {
        replyMessageId.value = "";
        messageInput.placeholder = defaultMessagePlaceholder;
        replyName.textContent = "";
        replyPreview.textContent = "";
        replyContext.hidden = true;
    }

    function beginReply({messageId = "", username = "", displayName = "", name = "", message = ""} = {}) {
        if (!messageId.startsWith("twitch:")) return;
        replyMessageId.value = messageId;
        const label = username
            ? (displayName && displayName.toLocaleLowerCase() !== username.toLocaleLowerCase()
                ? `${displayName} (${username})` : username)
            : name || displayName || "message";
        replyName.textContent = `Replying to ${label}`;
        messageInput.placeholder = `Replying to ${label}...`;
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

    async function toggleEmotes() {
        const opening = emotePicker.hidden;
        emotePicker.hidden = !opening;
        emoteToggle.setAttribute("aria-expanded", String(opening));
        if (opening) {
            await loadEmotes();
            if (!emotePicker.hidden) emoteSearch.focus();
        }
    }
    emoteToggle.addEventListener("click", toggleEmotes);

    messageInput.addEventListener("focus", () => {
        loadEmotes();
        loadUsers();
    });
    function resizeMessageInput() {
        composer.resize();
    }

    function handleComposerKey(event) {
        if (targetSelector.handleKey(event, () => !suggestionBox.hidden && autocomplete.handleKey(event))) return true;
        if (event.key === "Escape" && replyMessageId.value) {
            event.preventDefault();
            hideSuggestions();
            clearReply();
            return true;
        }
        if (suggestionBox.hidden && (event.key === "ArrowUp" || event.key === "ArrowDown")) {
            const direction = event.key === "ArrowUp" ? -1 : 1;
            if (navigateMessageHistory(direction)) {
                event.preventDefault();
                return true;
            }
        }
        return false;
    }

    composer = window.createChatComposer({form, input: messageInput, sendButton, status,
        autocomplete: {box: suggestionBox,
            getEmotes: () => emotes, getUsers: () => users, getCommands: () => twitchCommands,
            loadEmotes, loadUsers, enabled: () => selectedTarget !== "youtube",
            insert: (suggestion, range) => insertValue(suggestion.value, range)},
        onInput() { browsingHistory = false; historyIndex = messageHistory.length; },
        onKey: handleComposerKey,
        focusAfterSend: true,
        async send(outgoingMessage, signal) {
          const target = selectedTarget;
          let failureReported = false;
          try {
            const simulated = window.dashboardChatDebug?.send(outgoingMessage, selectedTarget);
            let result = simulated, ok = true;
            if (simulated) {
                ok = Boolean(simulated.sent.length);
            } else {
                const data = new FormData(form);
                data.set("message", outgoingMessage);
                data.set("target", target);
                const response = await fetch((globalThis.document?.body?.dataset?.channelRoot || "/channel") + '/api/chat/send', {method: "POST", body: data, signal});
                result = await response.json();
                ok = response.ok;
            }

            for (const platform of ["twitch", "youtube"]) {
                if (!result.errors?.[platform]) continue;
                reportSendFailure(platform, result.errors[platform]);
                failureReported = true;
            }

            if (!ok && globalThis.document?.body?.dataset?.channelRoot?.startsWith("/me/mod/")) document.dispatchEvent(new Event("moderator-authorization-check"));
            if (!ok) throw new Error(result.detail || Object.values(result.errors || {}).join(" ") || "The message could not be sent.");
            window.confirmDashboardChatSend?.(result);

            const sent = (result.sent || []).map(platform => platform === "youtube" ? "YouTube" : "Twitch");
            const failures = Object.values(result.errors || {});
            return {message: result.message || (failures.length
                ? `Sent to ${sent.join(" and ")}. ${failures.join(" ")}` : `Sent to ${sent.join(" and ")}.`),
                tone: result.tone || (failures.length ? "warning" : "success")};
          } catch (error) {
            if (!signal?.aborted && !failureReported) {
                for (const platform of target === "both" ? ["twitch", "youtube"] : [target]) {
                    reportSendFailure(platform, `Delivery could not be confirmed. ${error.message || "Check the connection before retrying."}`);
                }
            }
            throw error;
          }
        },
        onSent(message) {
            rememberMessage(message); historyDraft = ""; clearReply();
            document.dispatchEvent(new CustomEvent("dashboard-chat-sent"));
        }
    });
    autocomplete = composer.autocomplete;
    window.addEventListener("beforeunload", () => { composer.destroy(); pickerView.destroy(); targetSelector.destroy(); }, {once: true});

    document.addEventListener("click", event => {
        if (!emotePicker.hidden && !emotePicker.contains(event.target) && !emoteToggle.contains(event.target)) {
            emotePicker.hidden = true;
            emoteToggle.setAttribute("aria-expanded", "false");
        }
    });

    loadEmotes();
    loadUsers();
})();
