(() => {
    const dialog = document.querySelector("[data-raid-browser]");
    const form = dialog?.querySelector("[data-raid-browser-search]");
    if (!form || !HTMLElement.prototype.showPopover) return;
    const controls = [];
    let opened = null;

    function close(restoreFocus = false) {
        if (!opened) return;
        const control = opened;
        opened = null;
        control.popup.hidePopover();
        control.popup.hidden = true;
        control.trigger.setAttribute("aria-expanded", "false");
        if (restoreFocus) control.trigger.focus({preventScroll: true});
    }

    for (const select of form.querySelectorAll("select")) {
        const wrapper = document.createElement("span");
        wrapper.className = "raid-browser-select";
        const trigger = document.createElement("button");
        trigger.type = "button";
        trigger.className = "raid-browser-select-trigger";
        trigger.setAttribute("role", "combobox");
        trigger.setAttribute("aria-haspopup", "listbox");
        trigger.setAttribute("aria-expanded", "false");
        const popup = document.createElement("div");
        popup.className = "raid-browser-tag-dropdown raid-browser-category-options raid-browser-select-options";
        popup.id = `raid-browser-select-${select.name}`;
        popup.setAttribute("popover", "manual");
        popup.setAttribute("role", "listbox");
        popup.hidden = true;
        const label = select.closest("label")?.firstChild?.textContent.trim() || select.name;
        popup.setAttribute("aria-label", label);
        trigger.setAttribute("aria-controls", popup.id);
        select.before(wrapper);
        wrapper.append(trigger, select);
        select.dataset.customSelect = "true";
        select.tabIndex = -1;
        select.setAttribute("aria-hidden", "true");
        dialog.append(popup);
        const control = {select, trigger, popup};
        controls.push(control);

        function sync() {
            const text = select.selectedOptions[0]?.textContent || "";
            trigger.textContent = text;
            trigger.title = text;
            trigger.setAttribute("aria-label", `${label}: ${text}`);
            trigger.disabled = select.disabled;
            if (opened === control) close();
        }
        function open() {
            if (select.disabled || !dialog.open) return;
            close();
            popup.replaceChildren();
            for (const option of select.options) {
                if (option.hidden) continue;
                const button = document.createElement("button");
                button.type = "button";
                button.setAttribute("role", "option");
                button.setAttribute("aria-selected", String(option.selected));
                button.textContent = option.textContent;
                button.disabled = option.disabled || option.parentElement.disabled === true;
                button.addEventListener("click", () => {
                    select.value = option.value;
                    close(true);
                    sync();
                    select.dispatchEvent(new Event("change", {bubbles: true}));
                });
                popup.append(button);
            }
            const rect = trigger.getBoundingClientRect();
            const below = window.innerHeight - rect.bottom - 12;
            const above = rect.top - 12;
            const upward = below < 120 && above > below;
            const height = Math.max(60, Math.min(280, upward ? above : below));
            Object.assign(popup.style, {left: `${rect.left}px`, width: `${rect.width}px`, maxHeight: `${height}px`,
                top: upward ? "auto" : `${rect.bottom + 4}px`, bottom: upward ? `${window.innerHeight - rect.top + 4}px` : "auto"});
            popup.hidden = false;
            popup.showPopover();
            opened = control;
            trigger.setAttribute("aria-expanded", "true");
            (popup.querySelector('[aria-selected="true"]:not(:disabled)') || popup.querySelector("button:not(:disabled)"))?.focus();
        }
        trigger.addEventListener("click", () => opened === control ? close(true) : open());
        trigger.addEventListener("keydown", event => {
            if (["ArrowDown", "ArrowUp"].includes(event.key)) { event.preventDefault(); open(); }
        });
        popup.addEventListener("keydown", event => {
            if (event.key === "Escape") {
                event.preventDefault(); event.stopImmediatePropagation(); close(true); return;
            }
            if (event.key === "Tab") { close(true); return; }
            if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
            event.preventDefault();
            const options = [...popup.querySelectorAll("button:not(:disabled)")];
            const current = options.indexOf(document.activeElement);
            const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1
                : Math.max(0, Math.min(options.length - 1, current + (event.key === "ArrowDown" ? 1 : -1)));
            options[next]?.focus(); options[next]?.scrollIntoView({block: "nearest"});
        });
        select.addEventListener("change", sync);
        new MutationObserver(sync).observe(select, {subtree: true, childList: true, attributes: true,
            attributeFilter: ["disabled", "label", "value", "selected"]});
        control.sync = sync;
        sync();
    }
    dialog.addEventListener("pointerdown", event => {
        if (opened && !opened.popup.contains(event.target) && !opened.trigger.contains(event.target)) close();
    });
    dialog.addEventListener("focusout", event => {
        if (opened && !opened.popup.contains(event.relatedTarget) && event.relatedTarget !== opened.trigger) close();
    });
    dialog.addEventListener("close", () => close());
    dialog.addEventListener("scroll", event => { if (opened && event.target !== opened.popup) close(); }, true);
    window.addEventListener("resize", () => close());
    form.addEventListener("reset", () => requestAnimationFrame(() => controls.forEach(control => control.sync())));
})();
