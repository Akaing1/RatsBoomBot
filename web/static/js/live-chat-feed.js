(() => {
    function makeElement(tag, className, text) {
        const element = document.createElement(tag);
        if (className) element.className = className;
        if (text !== undefined) element.textContent = text;
        return element;
    }

    function emoteSrcset(url) {
        const larger = url.includes("static-cdn.jtvnw.net/")
            ? url.replace(/\/2\.0$/, "/3.0")
            : url.replace(/\/2x\.webp$/, "/3x.webp");
        return larger === url ? "" : `${url} 2x, ${larger} 3x`;
    }

    function distanceFromBottom(element) {
        return element.scrollHeight - element.scrollTop - element.clientHeight;
    }

    function updateJumpButton(feed) {
        const atBottom = distanceFromBottom(feed.element) <= 24;
        feed.jumpButton.hidden = atBottom;

        if (atBottom) feed.hasUnseenMessages = false;
        feed.jumpButton.classList.toggle("has-unseen", feed.hasUnseenMessages && !atBottom);
    }

    function scrollToBottom(feed) {
        const finishScroll = () => {
            if (!feed.followNewest) return;
            feed.element.scrollTop = feed.element.scrollHeight;
            updateJumpButton(feed);
        };

        finishScroll();
        // Wrapped text and decoded emotes can change the row height after it is inserted.
        // Re-check after layout and paint so the complete final message remains visible.
        window.requestAnimationFrame(() => {
            finishScroll();
            window.requestAnimationFrame(finishScroll);
        });
    }

    function visibleMessageName(message) {
        const username = message?.username || "";
        const displayName = message?.display_name || username || "Unknown";
        if (message?.platform === "twitch" && username) {
            return displayName.toLocaleLowerCase() !== username.toLocaleLowerCase()
                ? `${displayName} (${username})`
                : username;
        }
        return displayName;
    }

    function markMessageDeleted(feed, messageId) {
        feed.element.querySelectorAll(`[data-message-id="${CSS.escape(messageId)}"]`).forEach(row => {
            row.classList.add("is-deleted");
            row.setAttribute("aria-label", "Deleted message");
            row.querySelector(".live-chat-message-actions")?.remove();
        });
    }

    function renderPinned(feed, message, durationMinutes = undefined, endsAt = undefined) {
        if (!feed.pinnedContainer) return;
        const shouldFollowNewest = feed.followNewest && distanceFromBottom(feed.element) <= 24;
        const previousMessageId = feed.pinnedMessageId;
        window.clearTimeout(feed.pinExpiryTimer);
        feed.pinnedContainer.replaceChildren();
        feed.pinnedContainer.hidden = !message;
        feed.pinnedMessageId = message?.id || "";
        if (!message) {
            feed.pinEndsAt = null;
            if (shouldFollowNewest) scrollToBottom(feed);
            return;
        }
        if (previousMessageId !== message.id) {
            feed.pinDurationMinutes = "";
            feed.pinEndsAt = null;
        }
        if (durationMinutes !== undefined) {
            feed.pinDurationMinutes = durationMinutes === null ? "" : String(durationMinutes);
        }
        if (endsAt !== undefined) feed.pinEndsAt = endsAt;

        const copy = makeElement("div", "live-chat-pinned-copy");
        const label = makeElement("span", "live-chat-pinned-label", "Pinned message");
        const name = makeElement("strong", "live-chat-pinned-name", visibleMessageName(message));
        const text = makeElement("p", "live-chat-pinned-text", message.message || "");
        copy.append(label, name, text);
        const actions = makeElement("div", "live-chat-pinned-actions");
        const duration = makeElement("select", "live-chat-pin-duration");
        duration.title = "How long this message stays pinned";
        duration.setAttribute("aria-label", "Pinned message duration");
        const durations = [["", "∞"], ...Array.from({length: 10}, (_, index) => [String(index + 1), `${index + 1} min`]), ...[15, 20, 25, 30].map(value => [String(value), `${value} min`])];
        durations.forEach(([value, labelText]) => {
            const option = makeElement("option", "", labelText);
            option.value = value;
            duration.appendChild(option);
        });
        duration.value = feed.pinDurationMinutes ?? "";
        duration.addEventListener("change", () => {
            feed.pinDurationMinutes = duration.value;
            moderateMessage(feed, "pin-duration", message.id, duration, {duration_minutes: duration.value});
        });

        const unpin = makeElement("button", "live-chat-pinned-action live-chat-unpin", "📌");
        unpin.type = "button";
        unpin.title = "Unpin message";
        unpin.setAttribute("aria-label", "Unpin message");
        unpin.addEventListener("click", () => moderateMessage(feed, "pin", message.id, unpin));
        actions.append(duration, unpin);
        feed.pinnedContainer.append(copy, actions);

        const expiry = Date.parse(feed.pinEndsAt || "");
        const durationMs = Number(feed.pinDurationMinutes) * 60_000;
        if (Number.isFinite(expiry) && durationMs > 0) {
            const remainingMs = Math.max(0, expiry - Date.now());
            if (remainingMs === 0) {
                renderPinned(feed, null);
                refreshPinned(feed);
                return;
            }
            const progress = Math.min(1, remainingMs / durationMs);
            const progressBar = makeElement("span", "live-chat-pin-progress");
            progressBar.setAttribute("aria-hidden", "true");
            progressBar.style.setProperty("--pin-progress", String(progress));
            progressBar.style.setProperty("--pin-remaining", `${remainingMs}ms`);
            feed.pinnedContainer.appendChild(progressBar);
            feed.pinExpiryTimer = window.setTimeout(() => {
                renderPinned(feed, null);
                refreshPinned(feed);
            }, remainingMs + 50);
        }
        if (shouldFollowNewest) scrollToBottom(feed);
    }

    async function moderateMessage(feed, action, messageId, button, extra = {}) {
        if (!feed.moderationUrl || !messageId) return;
        button.disabled = true;
        const data = new FormData();
        data.set("csrf_token", feed.csrfToken);
        data.set("action", action);
        data.set("message_id", messageId);
        Object.entries(extra).forEach(([key, value]) => data.set(key, value));
        try {
            const response = await fetch(feed.moderationUrl, {method: "POST", body: data});
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || "The message could not be moderated.");
            if (result.action === "deleted") {
                markMessageDeleted(feed, messageId);
                if (feed.pinnedMessageId === messageId) renderPinned(feed, null);
            } else {
                if (Object.hasOwn(result, "duration_minutes")) {
                    feed.pinDurationMinutes = result.duration_minutes === null ? "" : String(result.duration_minutes);
                }
                renderPinned(feed, result.pinned || null, result.duration_minutes, result.ends_at);
            }
        } catch (error) {
            window.alert(error.message);
        } finally {
            button.disabled = false;
        }
    }

    async function refreshPinned(feed) {
        if (!feed.pinnedUrl || document.hidden) return;
        try {
            const response = await fetch(feed.pinnedUrl, {headers: {Accept: "application/json"}, cache: "no-store"});
            if (!response.ok) return;
            const result = await response.json();
            const message = result.message || null;
            const durationMinutes = Object.hasOwn(result, "duration_minutes")
                ? (result.duration_minutes === null ? "" : String(result.duration_minutes))
                : feed.pinDurationMinutes;
            const endsAt = Object.hasOwn(result, "ends_at") ? (result.ends_at || null) : feed.pinEndsAt;
            if (message && feed.pinnedMessageId === message.id
                && feed.pinDurationMinutes === durationMinutes && feed.pinEndsAt === endsAt) return;
            renderPinned(feed, message, durationMinutes, endsAt);
        } catch (_error) {
            // Keep the last synchronized pin visible during a temporary Twitch failure.
        }
    }

    function renderMessage(feed, message) {
        if (!message || !message.id) return;
        if (message.deleted && feed.seen.has(message.id)) {
            markMessageDeleted(feed, message.id);
            return;
        }
        if (feed.seen.has(message.id)) return;
        const shouldFollowNewest = distanceFromBottom(feed.element) <= 24;
        feed.seen.add(message.id);

        const row = makeElement("article", `live-chat-message platform-${message.platform} kind-${message.kind}`);
        if (message.deleted) row.classList.add("is-deleted");
        if (message.mentioned) row.classList.add("is-mentioned");
        if (message.is_bot) row.classList.add("is-bot");
        const accents = new Set(["first-time", "broadcaster", "staff", "moderator", "vip", "artist", "subscriber"]);
        if (accents.has(message.accent)) row.classList.add(`accent-${message.accent}`);
        row.dataset.messageId = message.id;

        const content = makeElement("div", "live-chat-message-content");
        const heading = makeElement("div", "live-chat-message-heading");
        const platform = makeElement("span", `live-chat-platform ${message.platform}`, message.platform === "youtube" ? "YT" : "TW");
        const name = makeElement("strong", "live-chat-name", visibleMessageName(message));
        if (message.color && /^#[0-9a-f]{6}$/i.test(message.color)) name.style.color = message.color;
        heading.appendChild(platform);

        (Array.isArray(message.badges) ? message.badges : []).forEach(badge => {
            const label = typeof badge === "string" ? badge : (badge?.title || badge?.name || "Badge");
            const url = typeof badge === "object" && typeof badge?.url === "string" ? badge.url : "";

            if (url && /^https:\/\/static-cdn\.jtvnw\.net\//.test(url)) {
                const image = makeElement("img", "live-chat-badge-image");
                image.src = url;
                image.alt = label;
                image.title = label;
                image.loading = "eager";
                image.decoding = "async";

                const sources = [[badge.url_2x, "2x"], [badge.url_4x, "4x"]]
                    .filter(([source]) => typeof source === "string" && /^https:\/\/static-cdn\.jtvnw\.net\//.test(source));
                if (sources.length) image.srcset = `${url} 1x, ${sources.map(([source, density]) => `${source} ${density}`).join(", ")}`;
                heading.appendChild(image);
            } else {
                const fallback = makeElement("span", "live-chat-badge", label);
                fallback.title = label;
                heading.appendChild(fallback);
            }
        });
        heading.appendChild(name);

        let timestamp = null;
        const date = new Date(message.timestamp);
        if (!Number.isNaN(date.getTime())) {
            timestamp = makeElement("time", "live-chat-time", date.toLocaleTimeString([], {hour: "numeric", minute: "2-digit"}));
        }

        const body = makeElement("p", "live-chat-text");
        const segments = Array.isArray(message.segments) ? message.segments : [];

        if (segments.length) {
            segments.forEach(segment => {
                const text = typeof segment?.text === "string" ? segment.text : "";
                const url = typeof segment?.url === "string" ? segment.url : "";
                const trustedEmoteUrl = /^https:\/\/(?:static-cdn\.jtvnw\.net|cdn\.7tv\.app)\//.test(url);

                if (segment?.type === "emote" && trustedEmoteUrl) {
                    const emote = makeElement("img", "live-chat-emote");
                    emote.src = url;
                    emote.srcset = emoteSrcset(url);
                    emote.alt = text;
                    emote.title = segment.provider ? `${text} (${segment.provider})` : text;
                    emote.loading = "eager";
                    emote.decoding = "async";
                    body.appendChild(emote);
                } else {
                    body.appendChild(document.createTextNode(text));
                }
            });
        } else {
            body.textContent = message.message || "";
        }

        content.append(heading, body);
        if (timestamp) content.appendChild(timestamp);
        row.appendChild(content);
        if (!message.deleted && message.platform === "twitch" && feed.moderationUrl) {
            const actions = makeElement("div", "live-chat-message-actions");
            const reply = makeElement("button", "live-chat-message-action reply", "↩");
            reply.type = "button";
            reply.title = "Reply to message";
            reply.setAttribute("aria-label", `Reply to ${visibleMessageName(message)}`);
            reply.addEventListener("click", () => {
                document.dispatchEvent(new CustomEvent("dashboard-chat-reply", {detail: {
                    messageId: message.id,
                    name: visibleMessageName(message),
                    message: message.message || ""
                }}));
            });
            const pin = makeElement("button", "live-chat-message-action pin", "📌");
            pin.type = "button";
            pin.title = "Pin message";
            pin.setAttribute("aria-label", "Pin message");
            pin.addEventListener("click", () => moderateMessage(feed, "pin", message.id, pin));
            const remove = makeElement("button", "live-chat-message-action delete", "🗑");
            remove.type = "button";
            remove.title = "Delete message";
            remove.setAttribute("aria-label", "Delete message");
            remove.addEventListener("click", () => moderateMessage(feed, "delete", message.id, remove));
            actions.append(reply, pin, remove);
            row.appendChild(actions);
        }
        feed.element.appendChild(row);

        if (feed.followRowObserver) {
            feed.followRowObserver.disconnect();
            feed.followRowObserver = null;
        }

        while (feed.element.querySelectorAll(".live-chat-message").length > feed.maxMessages) {
            const oldest = feed.element.querySelector(".live-chat-message");
            if (!oldest) break;
            feed.seen.delete(oldest.dataset.messageId);
            oldest.remove();
        }

        if (shouldFollowNewest) {
            feed.followNewest = true;
            scrollToBottom(feed);
            if ("ResizeObserver" in window) {
                feed.followRowObserver = new ResizeObserver(() => {
                    if (feed.followNewest) scrollToBottom(feed);
                });
                feed.followRowObserver.observe(row);
            }
            row.querySelectorAll("img").forEach(image => {
                if (!image.complete) image.addEventListener("load", () => {
                    if (feed.followNewest) scrollToBottom(feed);
                }, {once: true});
            });
        } else {
            feed.followNewest = false;
            feed.hasUnseenMessages = true;
            updateJumpButton(feed);
        }
        if (feed.historyComplete && feed.element.dataset.activityNotify) {
            document.dispatchEvent(new CustomEvent("dashboard-activity-unread", {
                detail: {activity: feed.element.dataset.activityNotify}
            }));
        }
    }

    document.querySelectorAll("[data-live-chat-feed]").forEach(element => {
        const shell = makeElement("div", "live-chat-feed-shell");
        element.parentNode.insertBefore(shell, element);
        shell.appendChild(element);

        const connectionStatus = element.dataset.connectionStatusTarget
            ? document.querySelector(element.dataset.connectionStatusTarget)
            : null;
        let connectionFadeTimer = null;
        const feed = {
            element,
            seen: new Set(),
            maxMessages: Number(element.dataset.maxMessages || 100),
            hasUnseenMessages: false,
            followNewest: true,
            followRowObserver: null,
            historyComplete: false,
            moderationUrl: element.dataset.moderationUrl || "",
            pinnedUrl: element.dataset.pinnedUrl || "",
            csrfToken: element.dataset.csrfToken || "",
            pinnedMessageId: "",
            pinEndsAt: null,
            pinExpiryTimer: null,
            pinnedContainer: element.dataset.pinnedUrl ? makeElement("aside", "live-chat-pinned") : null,
            connectionStatus,
            jumpButton: makeElement("button", "live-chat-jump", "↓ Jump to present")
        };
        function showConnectionStatus(connected) {
            if (!connectionStatus) return;
            window.clearTimeout(connectionFadeTimer);
            window.clearTimeout(connectionStatus._connectionFadeTimer);
            connectionStatus.dataset.connectionState = connected ? "connected" : "disconnected";
            connectionStatus.className = `chat-send-status ${connected ? "success" : "error"}`;
            connectionStatus.textContent = connected ? "Connected" : "Not connected";
            if (connected) {
                connectionFadeTimer = window.setTimeout(() => connectionStatus.classList.add("is-fading"), 3000);
                connectionStatus._connectionFadeTimer = connectionFadeTimer;
            }
        }
        feed.jumpButton.type = "button";
        feed.jumpButton.hidden = true;
        feed.jumpButton.addEventListener("click", () => {
            feed.hasUnseenMessages = false;
            feed.followNewest = true;
            scrollToBottom(feed);
        });
        ["wheel", "touchmove"].forEach(eventName => {
            element.addEventListener(eventName, () => { feed.followNewest = false; }, {passive: true});
        });
        element.addEventListener("pointerdown", event => {
            if (event.target === element) feed.followNewest = false;
        }, {passive: true});
        element.addEventListener("scroll", () => {
            if (distanceFromBottom(element) <= 24) feed.followNewest = true;
            updateJumpButton(feed);
        }, {passive: true});
        if (feed.pinnedContainer) {
            feed.pinnedContainer.hidden = true;
            shell.insertBefore(feed.pinnedContainer, element);
            refreshPinned(feed);
            window.setInterval(() => refreshPinned(feed), 2000);
        }
        shell.appendChild(feed.jumpButton);

        const source = new EventSource(element.dataset.streamUrl);
        source.onopen = () => showConnectionStatus(true);
        source.onerror = () => showConnectionStatus(false);
        source.addEventListener("history-complete", () => { feed.historyComplete = true; });
        source.onmessage = event => {
            try {
                renderMessage(feed, JSON.parse(event.data));
            } catch (error) {
                console.error("Unable to render live-chat message", error);
            }
        };
        window.addEventListener("beforeunload", () => source.close(), {once: true});
    });
})();
