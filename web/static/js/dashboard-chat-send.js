(() => {
    const form = document.querySelector("[data-chat-composer]");
    if (!form) return;

    const messageInput = form.querySelector('[name="message"]');
    const sendButton = form.querySelector(".chat-send-button");
    const status = form.querySelector("[data-chat-send-status]");
    const targets = Array.from(form.querySelectorAll("[data-chat-target]"));
    let selectedTarget = "twitch";
    let sending = false;

    function selectTarget(target) {
        const selected = targets.find(button => button.dataset.chatTarget === target && !button.disabled);
        if (!selected) return;
        selectedTarget = target;
        targets.forEach(button => {
            const active = button === selected;
            button.classList.toggle("active", active);
            button.setAttribute("aria-pressed", String(active));
        });
    }

    targets.forEach(button => button.addEventListener("click", () => selectTarget(button.dataset.chatTarget)));

    messageInput.addEventListener("keydown", event => {
        if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
            event.preventDefault();
            form.requestSubmit();
        }
    });

    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (sending || !messageInput.value.trim()) return;

        sending = true;
        sendButton.disabled = true;
        status.className = "chat-send-status";
        status.textContent = "Sending…";

        const data = new FormData(form);
        data.set("message", messageInput.value.trim());
        data.set("target", selectedTarget);

        try {
            const response = await fetch("/channel/api/chat/send", {method: "POST", body: data});
            const result = await response.json();

            if (!response.ok) throw new Error(result.detail || "The message could not be sent.");

            const sent = (result.sent || []).map(platform => platform === "youtube" ? "YouTube" : "Twitch");
            const failures = Object.values(result.errors || {});
            messageInput.value = "";
            status.classList.add(failures.length ? "warning" : "success");
            status.textContent = failures.length ? `Sent to ${sent.join(" and ")}. ${failures.join(" ")}` : `Sent to ${sent.join(" and ")}.`;
        } catch (error) {
            status.classList.add("error");
            status.textContent = error.message || "The message could not be sent.";
        } finally {
            sending = false;
            sendButton.disabled = false;
            messageInput.focus();
        }
    });
})();
