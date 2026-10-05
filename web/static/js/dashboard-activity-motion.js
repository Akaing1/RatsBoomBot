(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    const initialized = new WeakSet();
    const tabs = new WeakMap();
    const follows = new WeakMap();
    const rows = container => [...container.querySelectorAll("[data-activity-key], [data-message-id]")]
        .filter(row => !row.classList.contains("is-activity-removing"));
    const key = row => row.dataset.activityKey || row.dataset.messageId;
    const visible = container => !container.closest("[hidden]");

    function highlight(row, delay = 0) {
        if (reduced.matches) return;
        row.style.setProperty("--entry-highlight-delay", `${delay}ms`);
        row.classList.add("is-new-entry");
        window.setTimeout(() => row.classList.remove("is-new-entry"), delay + 950);
    }

    function preserveScroll(container, following, duration) {
        window.cancelAnimationFrame(follows.get(container));
        const top = container.getBoundingClientRect().top;
        const anchor = following ? null : rows(container).find(row => row.getBoundingClientRect().bottom > top);
        const anchorTop = anchor?.getBoundingClientRect().top;
        const until = performance.now() + duration;
        const follow = now => {
            if (!container.isConnected) return;
            if (following) container.scrollTop = 0;
            else if (anchor?.isConnected) container.scrollTop += anchor.getBoundingClientRect().top - anchorTop;
            if (now < until) follows.set(container, window.requestAnimationFrame(follow));
        };
        // A user's scroll gesture takes precedence over animation anchoring.
        const cancel = () => window.cancelAnimationFrame(follows.get(container));
        container.addEventListener("wheel", cancel, {once: true, passive: true});
        container.addEventListener("touchstart", cancel, {once: true, passive: true});
        follows.set(container, window.requestAnimationFrame(follow));
        window.setTimeout(() => {
            container.removeEventListener("wheel", cancel);
            container.removeEventListener("touchstart", cancel);
        }, duration + 50);
    }

    function animateRow(row, removing, delay = 0) {
        const height = row.getBoundingClientRect().height;
        if (!height || reduced.matches) {
            if (removing) row.remove();
            return;
        }
        const style = window.getComputedStyle(row);
        row.classList.remove("is-activity-appearing", "is-activity-removing");
        row.style.setProperty("--activity-row-height", `${height}px`);
        row.style.setProperty("--activity-padding-top", style.paddingTop);
        row.style.setProperty("--activity-padding-bottom", style.paddingBottom);
        row.style.setProperty("--activity-motion-delay", `${delay}ms`);
        row.classList.add(removing ? "is-activity-removing" : "is-activity-appearing");
        if (!removing) highlight(row, delay);
        if (removing) {
            row.inert = true;
            row.setAttribute("aria-hidden", "true");
        }
        const finish = () => {
            row.removeEventListener("animationend", ended);
            if (removing) row.remove();
            else row.classList.remove("is-activity-appearing");
        };
        const ended = event => { if (event.target === row) finish(); };
        row.addEventListener("animationend", ended);
        // Also finish if the tab becomes hidden or reduced motion changes mid-animation.
        window.setTimeout(finish, delay + 420);
    }

    function reconcile(container, render) {
        const previous = rows(container);
        const oldKeys = new Set(previous.map(key));
        const shouldAnimate = initialized.has(container) && visible(container) && !reduced.matches;
        initialized.add(container);
        render();
        if (!shouldAnimate) return;
        const current = rows(container);
        const currentKeys = new Set(current.map(key));
        const added = current.filter(row => !oldKeys.has(key(row)));
        const removed = previous.filter(row => !currentKeys.has(key(row)));
        const list = container.querySelector(".activity-list") || container;
        const empty = removed.length ? container.querySelector(".compact-empty-state") : null;
        if (empty) empty.hidden = true;
        removed.forEach((row, index) => {
            // Retain the removed row near its previous neighbors while it slides out.
            const next = previous.slice(previous.indexOf(row) + 1)
                .map(old => current.find(candidate => key(candidate) === key(old))).find(Boolean);
            list.insertBefore(row, next?.parentElement === list ? next : null);
            animateRow(row, true, Math.min(index * 45, 450));
        });
        added.forEach((row, index) => animateRow(row, false, Math.min(index * 45, 450)));
        if (empty) window.setTimeout(() => { if (empty.isConnected) empty.hidden = false; }, 870);
        return added.length || removed.length ? 870 : 0;
    }

    function enter(container, row, following) {
        if (reduced.matches || !visible(container)) return;
        animateRow(row, false);
        preserveScroll(container, following, 420);
    }

    function remove(container, row) {
        if (!row || row.classList.contains("is-activity-removing")) return;
        const following = container.scrollTop <= 24;
        if (!visible(container) || reduced.matches) { row.remove(); return; }
        animateRow(row, true);
        preserveScroll(container, following, 420);
    }

    function switchTab(panel) {
        tabs.get(panel)?.cancel();
        if (reduced.matches || !panel.animate) return;
        tabs.set(panel, panel.animate([
            {opacity: 0, transform: "perspective(600px) rotateX(-8deg) translateY(-6px)", transformOrigin: "top center"},
            {opacity: 1, transform: "none", transformOrigin: "top center"}
        ], {duration: 220, easing: "cubic-bezier(.2,.8,.2,1)"}));
    }

    window.dashboardActivityMotion = {reconcile, enter, remove, switchTab, preserveScroll, highlight};
})();
