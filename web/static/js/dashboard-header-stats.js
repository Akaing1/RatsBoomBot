(() => {
    const container = document.querySelector("[data-dashboard-header-stats]");
    if (!container) return;

    const storageKey = `ratsboombot:dashboard-stat-visibility:${container.dataset.channelId || "channel"}`;
    const refreshUrl = container.dataset.refreshUrl;
    const refreshInterval = 60000;
    let hiddenStats = new Set();
    let refreshInProgress = false;
    let lastRefreshAt = Date.now();

    try {
        const stored = JSON.parse(window.localStorage.getItem(storageKey) || "[]");
        if (Array.isArray(stored)) hiddenStats = new Set(stored.filter(value => typeof value === "string"));
    } catch (_error) {
        hiddenStats = new Set();
    }

    function applyVisibility(button, hidden) {
        const value = button.querySelector("[data-dashboard-stat-value]");
        const label = button.querySelector("span")?.textContent.trim() || "Statistic";
        if (value) value.hidden = hidden;
        button.classList.toggle("number-hidden", hidden);
        button.setAttribute("aria-pressed", String(hidden));
        button.title = `${hidden ? "Show" : "Hide"} ${label} count`;
    }

    function formatUptime(startedAt) {
        const elapsed = Math.max(0, Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000));
        const hours = Math.floor(elapsed / 3600);
        const minutes = Math.floor((elapsed % 3600) / 60);
        const seconds = elapsed % 60;
        if (hours) return `${hours}h ${minutes}m`;
        if (minutes) return `${minutes}m ${seconds}s`;
        return `${seconds}s`;
    }

    function renderStreamStatus() {
        const streamStatus = container.querySelector("[data-stream-status]");
        const text = streamStatus?.querySelector("[data-stream-status-text]");
        if (!streamStatus || !text) return;
        text.textContent = streamStatus.classList.contains("state-live") && streamStatus.dataset.startedAt
            ? `Live · ${formatUptime(streamStatus.dataset.startedAt)}`
            : "Offline";
    }

    container.querySelectorAll("[data-dashboard-stat]").forEach(button => {
        const key = button.dataset.dashboardStat;
        applyVisibility(button, hiddenStats.has(key));
        button.addEventListener("click", () => {
            if (hiddenStats.has(key)) hiddenStats.delete(key);
            else hiddenStats.add(key);
            applyVisibility(button, hiddenStats.has(key));
            try {
                window.localStorage.setItem(storageKey, JSON.stringify(Array.from(hiddenStats)));
            } catch (_error) {
                // Keep the current choice for this page when storage is unavailable.
            }
        });
    });

    async function refreshStats() {
        if (!refreshUrl || refreshInProgress || document.hidden) return;
        refreshInProgress = true;
        try {
            const response = await fetch(refreshUrl, {headers: {Accept: "application/json"}, cache: "no-store"});
            if (!response.ok) return;
            const payload = await response.json();
            (Array.isArray(payload.stats) ? payload.stats : []).forEach(stat => {
                const button = container.querySelector(`[data-dashboard-stat="${CSS.escape(String(stat.key || ""))}"]`);
                const value = button?.querySelector("[data-dashboard-stat-value]");
                if (value) value.textContent = String(stat.display_value ?? "—");
            });
            const streamStatus = container.querySelector("[data-stream-status]");
            const streamStatusText = streamStatus?.querySelector("[data-stream-status-text]");
            if (streamStatus && streamStatusText && typeof payload.is_live === "boolean") {
                streamStatus.classList.toggle("state-live", payload.is_live);
                streamStatus.classList.toggle("state-offline", !payload.is_live);
                streamStatus.querySelector(".status-indicator")?.classList.toggle("online", payload.is_live);
                streamStatus.querySelector(".status-indicator")?.classList.toggle("offline", !payload.is_live);
                streamStatus.dataset.startedAt = payload.started_at || "";
                renderStreamStatus();
            }
            lastRefreshAt = Date.now();
        } catch (_error) {
            // Leave the last successful values visible until Twitch is reachable again.
        } finally {
            refreshInProgress = false;
        }
    }

    window.setInterval(refreshStats, refreshInterval);
    renderStreamStatus();
    window.setInterval(renderStreamStatus, 1000);
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden && Date.now() - lastRefreshAt >= refreshInterval) refreshStats();
    });
})();
