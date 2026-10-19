(() => {
    window.createChatTargetSelector = ({form, button, input, youtubeAvailable, onChange, onLayout = () => {}}) => {
        const targets = youtubeAvailable ? ["twitch", "youtube", "both"] : ["twitch"];
        const labels = {twitch: "Twitch", youtube: "YouTube", both: "All"};
        let selected = "twitch", shifted = false, active = true, prefixWidth = 0;
        const target = () => shifted && youtubeAvailable ? "both" : selected;
        function measurePrefix() {
            if (!active || !input) return;
            const width = button.getBoundingClientRect().width;
            if (width <= 0 || width === prefixWidth) return;
            prefixWidth = width;
            input.style.setProperty("--chat-target-indent", `${Math.ceil(width) + 2}px`);
            onLayout();
        }
        function onInputScroll() {
            if (active) button.style.visibility = input.scrollTop > 0 ? "hidden" : "";
        }
        function render() {
            if (!active) return;
            const current = target();
            button.textContent = `[${labels[current]}]`;
            button.dataset.target = current;
            button.title = labels[current];
            button.setAttribute("aria-label", `Send to ${labels[current]}. Click or press Tab to change.`);
            button.disabled = targets.length === 1;
            measurePrefix();
            onChange(current);
        }
        function shift(value) {
            if (!active || !youtubeAvailable || shifted === value) return;
            shifted = value; render();
        }
        function select(value) {
            if (!active || !targets.includes(value)) return;
            selected = value; render();
        }
        function cycle() {
            select(targets[(targets.indexOf(selected) + 1) % targets.length]);
        }
        function handleKey(event, complete = () => false) {
            if (!active || event.isComposing || event.ctrlKey || event.altKey || event.metaKey) return false;
            if (event.key === "Enter" && event.shiftKey) {
                event.preventDefault(); shift(true); form.requestSubmit(); return true;
            }
            if (event.key === "Tab" && !event.shiftKey) {
                if (complete()) return true;
                event.preventDefault();
                if (targets.length > 1) cycle();
                return true;
            }
            return false;
        }
        const onDown = event => { if (event.key === "Shift") shift(true); };
        const onUp = event => { if (event.key === "Shift" || !event.shiftKey) shift(false); };
        const onBlur = () => shift(false);
        const onFocusOut = event => { if (!form.contains(event.relatedTarget)) shift(false); };
        const onPointer = event => shift(Boolean(event.shiftKey));
        const onClick = () => cycle();
        const onButtonKey = event => {
            if (event.key === "Tab" && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey) {
                event.preventDefault(); cycle();
            }
        };
        form.addEventListener("keydown", onDown);
        form.addEventListener("pointerdown", onPointer);
        form.addEventListener("focusout", onFocusOut);
        window.addEventListener("keyup", onUp);
        window.addEventListener("blur", onBlur);
        button.addEventListener("click", onClick);
        button.addEventListener("keydown", onButtonKey);
        const observer = input && window.ResizeObserver ? new window.ResizeObserver(measurePrefix) : null;
        observer?.observe(button);
        input?.addEventListener("scroll", onInputScroll);
        render();
        return {target, select, handleKey, destroy() {
            if (!active) return;
            active = false;
            form.removeEventListener("keydown", onDown);
            form.removeEventListener("pointerdown", onPointer);
            form.removeEventListener("focusout", onFocusOut);
            window.removeEventListener("keyup", onUp);
            window.removeEventListener("blur", onBlur);
            button.removeEventListener("click", onClick);
            button.removeEventListener("keydown", onButtonKey);
            input?.removeEventListener("scroll", onInputScroll); observer?.disconnect();
        }};
    };
})();
