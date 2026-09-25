(() => {
    const container = document.querySelector("[data-dashboard-header-stats]");
    if (!container) return;
    const dashboard = container.closest(".channel-dashboard-layout") || document;
    const statsRow = container.closest(".dashboard-header-side");

    function updateDashboardStatsHeight() {
        if (statsRow) dashboard.style.setProperty("--dashboard-stats-height", `${statsRow.getBoundingClientRect().height}px`);
    }
    updateDashboardStatsHeight();
    if ("ResizeObserver" in window) {
        const observer = new ResizeObserver(updateDashboardStatsHeight);
        if (statsRow) observer.observe(statsRow);
    } else window.addEventListener("resize", updateDashboardStatsHeight);

    const storageKey = `ratsboombot:dashboard-stat-visibility:${container.dataset.channelId || "channel"}`;
    const refreshUrl = container.dataset.refreshUrl;
    const refreshInterval = 60000;
    const streamStatus = container.querySelector("[data-stream-status]");
    const viewerValue = container.querySelector('[data-dashboard-stat="viewers"] [data-dashboard-stat-value]');
    let actualViewerCount = viewerValue?.textContent || "—";
    let actualStreamStatus = {
        isLive: streamStatus?.classList.contains("state-live") || false,
        startedAt: streamStatus?.dataset.startedAt || ""
    };
    let previewActive = false;
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
        const text = streamStatus?.querySelector("[data-stream-status-text]");
        if (!streamStatus || !text) return;
        const isLive = streamStatus.classList.contains("state-live");
        const showTimer = !hiddenStats.has("stream_timer");
        text.textContent = isLive
            ? `Online${showTimer && streamStatus.dataset.startedAt ? ` · ${formatUptime(streamStatus.dataset.startedAt)}` : ""}`
            : "Offline";
        streamStatus.setAttribute("aria-pressed", String(showTimer));
        streamStatus.setAttribute("aria-label", `${showTimer ? "Hide" : "Show"} online timer`);
        streamStatus.title = `${showTimer ? "Hide" : "Show"} online timer`;
    }

    function applyStreamStatus(isLive, startedAt) {
        if (!streamStatus) return;
        streamStatus.classList.toggle("state-live", isLive);
        streamStatus.classList.toggle("state-offline", !isLive);
        streamStatus.querySelector(".status-indicator")?.classList.toggle("online", isLive);
        streamStatus.querySelector(".status-indicator")?.classList.toggle("offline", !isLive);
        streamStatus.dataset.startedAt = startedAt;
        renderStreamStatus();
    }

    // Browser-console preview only: no Twitch or server state is changed.
    window.dashboardLiveTest = {
        start(minutes = 0) {
            const elapsedMinutes = Number(minutes);
            if (!Number.isFinite(elapsedMinutes) || elapsedMinutes < 0) {
                throw new RangeError("Minutes must be a non-negative number.");
            }
            previewActive = true;
            applyStreamStatus(true, new Date(Date.now() - elapsedMinutes * 60000).toISOString());
            if (viewerValue) viewerValue.textContent = (Math.floor(Math.random() * 500) + 1).toLocaleString();
        },
        stop() {
            previewActive = false;
            applyStreamStatus(actualStreamStatus.isLive, actualStreamStatus.startedAt);
            if (viewerValue) viewerValue.textContent = actualViewerCount;
            void refreshStats();
        }
    };

    function saveVisibility() {
        try {
            window.localStorage.setItem(storageKey, JSON.stringify(Array.from(hiddenStats)));
        } catch (_error) {
            // Keep the current choice for this page when storage is unavailable.
        }
    }

    container.querySelector("[data-stream-status]")?.addEventListener("click", () => {
        if (hiddenStats.has("stream_timer")) hiddenStats.delete("stream_timer");
        else hiddenStats.add("stream_timer");
        renderStreamStatus();
        saveVisibility();
    });

    dashboard.querySelectorAll("[data-dashboard-stat]").forEach(button => {
        const key = button.dataset.dashboardStat;
        applyVisibility(button, hiddenStats.has(key));
        button.addEventListener("click", () => {
            if (hiddenStats.has(key)) hiddenStats.delete(key);
            else hiddenStats.add(key);
            applyVisibility(button, hiddenStats.has(key));
            saveVisibility();
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
                const statContainer = stat.key === "points_lost"
                    ? dashboard.querySelector("[data-dashboard-points-lost]")
                    : dashboard.querySelector(`[data-dashboard-stat="${CSS.escape(String(stat.key || ""))}"]`);
                const value = statContainer?.querySelector("[data-dashboard-stat-value]");
                const displayValue = String(stat.display_value ?? "—");
                if (stat.key === "viewers") actualViewerCount = displayValue;
                if (value && !(previewActive && stat.key === "viewers")) value.textContent = displayValue;
            });
            if (streamStatus && typeof payload.is_live === "boolean") {
                actualStreamStatus = {isLive: payload.is_live, startedAt: payload.started_at || ""};
                if (!previewActive) applyStreamStatus(actualStreamStatus.isLive, actualStreamStatus.startedAt);
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
