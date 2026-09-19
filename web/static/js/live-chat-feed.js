(() => {
    function makeElement(tag, className, text) {
        const element = document.createElement(tag);
        if (className) element.className = className;
        if (text !== undefined) element.textContent = text;
        return element;
    }

    function renderMessage(feed, message) {
        if (!message || !message.id || feed.seen.has(message.id)) return;
        feed.seen.add(message.id);

        const empty = feed.element.querySelector("[data-live-chat-empty]");
        if (empty) empty.remove();

        const row = makeElement("article", `live-chat-message platform-${message.platform} kind-${message.kind}`);
        row.dataset.messageId = message.id;

        const content = makeElement("div", "live-chat-message-content");
        const heading = makeElement("div", "live-chat-message-heading");
        const platform = makeElement("span", `live-chat-platform ${message.platform}`, message.platform === "youtube" ? "YT" : "TW");
        const name = makeElement("strong", "live-chat-name", message.display_name || message.username || "Unknown");
        if (message.color && /^#[0-9a-f]{6}$/i.test(message.color)) name.style.color = message.color;
        heading.append(platform, name);

        (Array.isArray(message.badges) ? message.badges : []).forEach(label => {
            heading.appendChild(makeElement("span", "live-chat-badge", label));
        });

        const date = new Date(message.timestamp);
        if (!Number.isNaN(date.getTime())) {
            heading.appendChild(makeElement("time", "live-chat-time", date.toLocaleTimeString([], {hour: "numeric", minute: "2-digit"})));
        }

        content.append(heading, makeElement("p", "live-chat-text", message.message || ""));
        row.appendChild(content);
        feed.element.appendChild(row);

        while (feed.element.querySelectorAll(".live-chat-message").length > feed.maxMessages) {
            const oldest = feed.element.querySelector(".live-chat-message");
            if (!oldest) break;
            feed.seen.delete(oldest.dataset.messageId);
            oldest.remove();
        }

        feed.element.scrollTop = feed.element.scrollHeight;
    }

    document.querySelectorAll("[data-live-chat-feed]").forEach(element => {
        const feed = {
            element,
            seen: new Set(),
            maxMessages: Number(element.dataset.maxMessages || 100)
        };
        const empty = makeElement("div", "live-chat-empty", element.dataset.emptyTitle || "Waiting for messages");
        empty.dataset.liveChatEmpty = "true";
        element.appendChild(empty);

        const source = new EventSource(element.dataset.streamUrl);
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
