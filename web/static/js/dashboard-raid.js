(() => {
    const panel = document.getElementById("dashboard-raid");
    if (!panel) return;
    const element = name => document.getElementById(`dashboard-raid-${name}`);
    const capitalize = value => String(value).charAt(0).toUpperCase() + String(value).slice(1);
    let loading = false;

    async function refresh() {
        if (loading || document.hidden) return;
        loading = true;
        try {
            const response = await fetch(`/api/raid/${encodeURIComponent(panel.dataset.channel)}`, {cache: "no-store"});
            if (!response.ok) throw new Error("Raid unavailable");
            const {metrics} = await response.json();
            element("details").hidden = !metrics;
            element("title").textContent = metrics ? metrics.boss_name : "No raids yet";
            element("status").textContent = metrics
                ? [metrics.status, metrics.boss_tier, metrics.boss_type].map(capitalize).join(" · ")
                : "The next encounter will appear here when a raid spawns.";
            if (metrics) {
                element("hp").textContent = `${metrics.current_hp.toLocaleString()} / ${metrics.max_hp.toLocaleString()} HP`;
                element("bar").style.width = `${Math.max(0, Math.min(100, metrics.hp_percent))}%`;
                for (const key of ["unique_attackers", "total_attacks", "total_damage", "streams_used"]) {
                    element(key).textContent = metrics[key].toLocaleString();
                }
            }
            element("refresh").textContent = "Updates automatically every 15 seconds.";
        } catch {
            element("refresh").textContent = "Unable to refresh raid activity. Displayed information may be out of date; retrying automatically.";
        } finally {
            loading = false;
        }
    }
    setInterval(refresh, 15000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
})();
