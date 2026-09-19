(() => {
    const container = document.querySelector("[data-ad-status]");
    if (!container) return;

    const label = container.querySelector("[data-ad-status-text]");
    let refreshInProgress = false;

    function formatDuration(totalSeconds) {
        const seconds = Math.max(0, Math.ceil(totalSeconds));
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const remainder = seconds % 60;
        if (hours) return `${hours}h ${minutes}m`;
        if (minutes) return `${minutes}m ${remainder}s`;
        return `${remainder}s`;
    }

    function render() {
        const now = Date.now();
        if (container.dataset.state === "running" && container.dataset.endsAt) {
            const remaining = (new Date(container.dataset.endsAt).getTime() - now) / 1000;
            label.textContent = remaining > 0 ? `Ad running · ${formatDuration(remaining)} remaining` : "Refreshing ad status…";
        } else if (container.dataset.state === "scheduled" && container.dataset.nextAdAt) {
            const remaining = (new Date(container.dataset.nextAdAt).getTime() - now) / 1000;
            label.textContent = remaining > 0 ? `Next ad in ${formatDuration(remaining)}` : "Ad starting…";
        }
    }

    function applyStatus(data) {
        container.className = `ad-status-row state-${data.state}`;
        container.dataset.state = data.state;
        container.dataset.nextAdAt = data.next_ad_at || "";
        container.dataset.endsAt = data.ends_at || "";
        label.textContent = data.label;
        render();
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
    window.setInterval(render, 1000);
    window.setInterval(refresh, 30000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
})();
