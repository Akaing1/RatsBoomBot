(() => {
    const container = document.querySelector("[data-ad-status]");
    if (!container) return;

    const label = container.querySelector("[data-ad-status-text]");
    const panel = document.querySelector("[data-ad-panel]");
    const actionStatus = panel?.querySelector("[data-ad-action-status]");
    const actionButtons = Array.from(panel?.querySelectorAll("[data-ad-action]") || []);
    let refreshInProgress = false;
    let actionInProgress = false;
    const appearanceClasses = ["ad-neutral", "ad-idle", "ad-warning", "ad-running"];

    function formatDuration(totalSeconds) {
        const seconds = Math.max(0, Math.ceil(totalSeconds));
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const remainder = seconds % 60;
        if (hours) return `${hours}h ${minutes}m`;
        if (minutes) return `${minutes}m ${remainder}s`;
        return `${remainder}s`;
    }

    function setAppearance(appearance) {
        if (container.classList.contains(appearance)) return;
        container.classList.remove(...appearanceClasses);
        container.classList.add(appearance);
    }

    function render() {
        const now = Date.now();
        if (container.dataset.state === "running" && container.dataset.endsAt) {
            const remaining = (new Date(container.dataset.endsAt).getTime() - now) / 1000;
            label.textContent = remaining > 0 ? `Ends in ${formatDuration(remaining)}` : "Refreshing…";
            setAppearance("ad-running");
        } else if (container.dataset.state === "scheduled" && container.dataset.nextAdAt) {
            const remaining = (new Date(container.dataset.nextAdAt).getTime() - now) / 1000;
            label.textContent = remaining > 0 ? `Starts in ${formatDuration(remaining)}` : "Starting…";
            if (remaining <= 0) {
                setAppearance("ad-running");
            } else if (remaining < 60) {
                setAppearance("ad-warning");
            } else {
                setAppearance("ad-idle");
            }
        } else if (container.dataset.state === "offline") {
            setAppearance("ad-neutral");
        } else {
            setAppearance("ad-idle");
        }
        const state = container.dataset.state;
        const snoozes = container.dataset.snoozesAvailable;
        actionButtons.forEach(button => {
            button.disabled = actionInProgress || state === "offline" ||
                (button.dataset.adAction === "snooze" &&
                    (state !== "scheduled" || (snoozes !== "" && Number(snoozes) <= 0))) ||
                (button.dataset.adAction !== "snooze" && state === "running");
        });
    }

    function applyStatus(data) {
        Array.from(container.classList).filter(name => name.startsWith("state-")).forEach(name => container.classList.remove(name));
        container.classList.add(`state-${data.state}`);
        container.dataset.state = data.state;
        container.dataset.nextAdAt = data.next_ad_at || "";
        container.dataset.endsAt = data.ends_at || "";
        container.dataset.snoozesAvailable = data.snoozes_available ?? "";
        label.textContent = data.label;
        render();
    }

    async function runAction(action) {
        if (actionInProgress) return;
        if (action !== "snooze" && !window.confirm(`Start a ${action === "run-90" ? "90-second" : "3-minute"} ad now?`)) return;
        actionInProgress = true;
        actionStatus.textContent = "Working…";
        actionStatus.className = "dashboard-ad-action-status";
        render();
        const body = new FormData();
        body.set("action", action);
        body.set("csrf_token", panel.dataset.csrfToken);
        try {
            const response = await fetch(panel.dataset.actionUrl, {method: "POST", body, headers: {Accept: "application/json"}});
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || "Twitch could not complete that ad action.");
            if (data.status) applyStatus(data.status);
            actionStatus.textContent = data.message || "Ad action completed.";
            actionStatus.classList.add("success");
        } catch (error) {
            actionStatus.textContent = error.message || "Ad action failed.";
            actionStatus.classList.add("error");
        } finally {
            actionInProgress = false;
            render();
        }
    }

    async function refresh() {
        if (refreshInProgress) return;
        refreshInProgress = true;
        try {
            const response = await fetch("/channel/api/ad-status", {headers: {Accept: "application/json"}});
            if (response.ok) applyStatus(await response.json());
        } catch (error) {
            // Keep the last known schedule during transient network failures.
        } finally {
            refreshInProgress = false;
        }
    }

    render();
    actionButtons.forEach(button => button.addEventListener("click", () => runAction(button.dataset.adAction)));
    window.setInterval(render, 1000);
    window.setInterval(refresh, 30000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
})();
