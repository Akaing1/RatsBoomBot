(() => {
    // Both chats use the same input lifecycle; callers provide only their transport
    // and optional dashboard features (platform selection, replies and history).
    window.createChatComposer = ({form, input, sendButton, status, autocomplete: options,
        send, handleLocal, onSent = () => {}, onInput = () => {}, onKey = () => false, focusAfterSend = false}) => {
        let closed = false, sending = false, request = null, statusTimer = null, width = 0;
        const listeners = [];
        function listen(element, type, handler) {
            element.addEventListener(type, handler);
            listeners.push(() => element.removeEventListener(type, handler));
        }
        function showStatus(message, tone = "", fade = false) {
            if (closed) return;
            window.clearTimeout(statusTimer);
            window.clearTimeout(status._connectionFadeTimer);
            status.className = `chat-send-status${tone ? ` ${tone}` : ""}`;
            status.textContent = message;
            if (fade) statusTimer = window.setTimeout(() => {
                if (status.dataset.connectionState === "disconnected") {
                    status.className = "chat-send-status error";
                    status.textContent = "Not connected";
                } else {
                    status.classList.add("is-fading");
                }
            }, 3000);
        }
        function resize() {
            if (closed) return;
            if (input.refreshEmotes) { input.refreshEmotes(); return; }
            const styles = getComputedStyle(input);
            const borders = parseFloat(styles.borderTopWidth) + parseFloat(styles.borderBottomWidth);
            const baseline = parseFloat(styles.lineHeight) + parseFloat(styles.paddingTop)
                + parseFloat(styles.paddingBottom) + borders;
            input.style.height = `${baseline}px`;
            // Ignore wrapped placeholders; CSS owns each chat's maximum height.
            if (input.value) input.style.height = `${Math.max(baseline, input.scrollHeight + borders)}px`;
        }
        const autocomplete = window.createChatAutocomplete({input, ...options,
            onLimit: () => showStatus("Messages can contain up to 500 characters.", "warning", true)});
        listen(input, "input", () => { resize(); onInput(); autocomplete.update(); });
        listen(input, "click", autocomplete.update);
        listen(input, "keydown", event => {
            if (onKey(event) || autocomplete.handleKey(event)) return;
            if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
                event.preventDefault(); form.requestSubmit();
            }
        });
        listen(form, "submit", async event => {
            event.preventDefault();
            const draft = input.value, message = draft.trim();
            if (closed || sending || !message) return;
            if (draft.length > input.maxLength) {
                showStatus("Messages can contain up to 500 characters.", "warning", true);
                return;
            }
            if (handleLocal?.(message)) {
                if (input.value === draft) { input.value = ""; resize(); onInput(); }
                autocomplete.hide();
                return;
            }
            sending = true; sendButton.disabled = true;
            request = new AbortController();
            showStatus("Sending…");
            try {
                const result = await send(message, request.signal);
                if (closed) return;
                // A new draft typed during delivery belongs to the user.
                if (input.value === draft) { input.value = ""; resize(); }
                autocomplete.hide();
                showStatus(result?.message || "Sent", result?.tone || "success", true);
                onSent(message, result);
            } catch (error) {
                if (!closed) showStatus(error.message || "The message could not be sent.", "error", true);
            } finally {
                request = null;
                sending = false;
                if (!closed) {
                    sendButton.disabled = false;
                    if (focusAfterSend) input.focus();
                }
            }
        });
        const observer = window.ResizeObserver ? new window.ResizeObserver(entries => {
            const nextWidth = entries[0].contentRect.width;
            if (width !== nextWidth) { width = nextWidth; resize(); }
        }) : null;
        observer?.observe(input.element || input);
        resize();
        return {autocomplete, resize, showStatus, destroy() {
            if (closed) return;
            closed = true;
            request?.abort();
            window.clearTimeout(statusTimer);
            observer?.disconnect();
            listeners.forEach(remove => remove());
            autocomplete.destroy();
            input.destroyEmoteInput?.();
        }};
    };
})();
